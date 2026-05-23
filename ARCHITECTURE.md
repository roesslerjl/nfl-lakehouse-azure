# NFL Analytics Lakehouse — Architecture Document

## Vision

A production-grade NFL analytics lakehouse on Azure Databricks that approaches the analytical depth of NFL Next Gen Stats using publicly available play-by-play data. The project demonstrates the full Databricks platform stack — ingestion, transformation, SQL modeling, and ML tracking — while producing genuine football insights that a real NFL analytics department would find useful.

The analytical ambition: NGS tracks what happened physically. This project answers *why it worked* — situational efficiency, QB value above expectation, and play concept prediction from pre-snap reads.
---

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Cloud | Azure | Primary cloud platform |
| Infrastructure | Terraform | Provisions all Azure resources |
| Storage | ADLS Gen2 | Raw and processed data storage |
| Data Platform | Azure Databricks | Compute, notebooks, jobs |
| Table Format | Delta Lake | ACID transactions, time travel, schema enforcement |
| Processing | PySpark | Bronze → Silver transformations |
| SQL Modeling | dbt (dbt-databricks) | Silver → Gold aggregations |
| ML Tracking | MLflow | Experiment tracking, model registry |
| Governance | Unity Catalog | Data lineage, access control |
| Dashboard | Databricks SQL | Analytics serving layer |
| Data Source | nfl-data-py | 3 seasons of NFL play-by-play (2023-2025) |

---

## Architecture: Medallion Layers

### Bronze — Raw Ingestion
- Source: nfl-data-py Python package
- Granularity: one row per play, all 397 source columns retained
- No transformations, no filtering — schema-on-read
- Written as Parquet locally, Delta Lake in production
- Partitioned by season
- Script: `src/ingestion/ingest_pbp.py`

### Silver — Cleaned, Typed, Enriched
- Granularity: one row per run/pass play (special teams excluded)
- ~35-40 columns selected from Bronze 397
- Script: `src/transforms/transform_pbp.py`

#### Transformations applied:
**Filtering**
- Keep `play_type` in `['run', 'pass']` only
- Drop kneels, spikes, special teams

**Type casting**
- `down` → integer
- `epa`, `wp`, `wpa` → float
- `was_pressure` → integer (null → 0)

**Null handling**
- `defense_coverage_type` nulls flagged via `coverage_available` boolean
  rather than dropped — sparse NGS tracking data is retained with honest flagging
- `was_pressure` null → 0 (no tracking data = no pressure recorded)

**Derived columns**
- `distance_bucket` — short (≤3 yards), medium (4-7), long (8+)
- `success` — binary: 1 if `epa > 0`, else 0
- `high_leverage` — binary: 1 if `wp` between 0.2 and 0.8
- `coverage_available` — binary: 1 if `defense_coverage_type` is not null
- `personnel_rb`, `personnel_te`, `personnel_wr` — parsed from 
  `offense_personnel` string via regex (linemen excluded per NFL convention)
- `play_concept` — derived string combining formation + pass/run direction + 
  length. e.g. `Shotgun_ShortRight`, `UnderCenter_DeepLeft`
- `concept_label` — rule-based mapping from `play_concept` to football-readable 
  route/scheme label. e.g. `Shotgun_ShortMiddle` → `Slant/Crossing`. 
  Defined in `config/play_concept_map.py`. Phase 1 of play concept taxonomy;
  refined by MLflow clustering experiment in Phase 3.

**Drive columns retained from Bronze**
- `fixed_drive` — drive number within a game. `fixed_drive` is used over `drive`
  because nfl-data-py corrects tracking inconsistencies in the fixed variant.
  Required to group plays into drives in `mart_drives`.
- `fixed_drive_result` — drive outcome: Touchdown, Field Goal, Punt, Turnover,
  End of Half, etc. Primary metric for drive efficiency analysis in Gold.

**Additional Bronze columns retained**
- `yards_gained` — actual yards gained on the play (positive or negative).
  Required for drive yardage totals, player yards, and team rushing/passing
  yards across all Gold marts.

**NGS-derived columns retained from Bronze**
- `time_to_throw` — seconds from snap to throw (NGS)
- `ngs_air_yards` — intended air yards per NGS tracking (vs. actual)
- `was_pressure` — whether QB faced pressure (NGS)
- `route` — targeted receiver's route (NGS, sparse)
- `defense_coverage_type` — man/zone coverage (NGS, ~45% coverage)

#### Silver column manifest:
season, week, game_id, play_id, fixed_drive, fixed_drive_result, yards_gained
offense_team, defense_team
passer_name, passer_id, rusher_name, rusher_id, receiver_name, receiver_id
play_type, down, yards_to_go, yards_from_end_zone
distance_bucket, score_differential, game_seconds_remaining
offense_formation, defense_coverage_type, coverage_available
personnel_rb, personnel_te, personnel_wr
play_concept, concept_label
pass_length, pass_location, run_location, run_gap
route, time_to_throw, intended_air_yards
expected_points_added, win_probability, win_probability_added, was_pressure, completion_pct_over_expected, qb_expected_points_added
success, high_leverage, quarter, two_minute
offense_timeouts_remaining, defense_timeouts_remaining

---

### Gold — Analytics-Ready Tables (dbt models)

The Gold layer is built in dbt using a three-layer structure:

```
staging/        ← thin translation layer from Silver (renames, source definition)
intermediate/   ← joins and assembly (no raw source references)
marts/          ← final analytics tables exposed to the dashboard and ML models
```

#### Mart Overview

| Mart | Grain | Primary use |
|---|---|---|
| `mart_plays` | 1 row per play | Arbitrary drill-down queries — the analytical engine |
| `mart_drives` | 1 row per drive | Drive efficiency, scoring drives, field position |
| `mart_player_game` | 1 row per player per game | Player performance box scores |
| `mart_team_game` | 1 row per team per game | Team offense/defense per game |
| `mart_player_season` | 1 row per player per season | Season-level rankings and trends |
| `mart_team_season` | 1 row per team per season | Season standings and efficiency ratings |
| `dim_players` | 1 row per player per season | Position lookups — enables positional queries across all play marts |

#### `mart_plays` — the analytical engine
Wide, fully denormalized play-level table. Every play carries all its context
(team names, player names, situation, EPA, NGS columns) so arbitrary analytical
queries require zero joins at query time.

**Example question this answers:** "Jordan Love's expected_points_added per play
on deep balls between weeks 1-10 vs. 10-18"

#### `mart_drives` — drive-level summaries
Aggregated from `mart_plays`. One row per drive per game.
Answers questions about drive efficiency, scoring rates, and field position.

#### `mart_player_game` / `mart_player_season`
Aggregated from `mart_plays`. Player performance stats at game and season grain.
Season mart is the primary ranking surface for the dashboard.

#### `mart_team_game` / `mart_team_season`
Aggregated from `mart_plays`. Team offense and defense stats at game and season grain.

---

## MLflow Experiments

### Experiment 1 — Win Probability Model
**Goal:** Given a game situation mid-drive, predict whether the possession team will win. Binary classifier (posteam_won).

**Features:** `down, yards_to_go, yards_from_end_zone, score_differential, game_seconds_remaining, offense_timeouts_remaining, defense_timeouts_remaining`

**Target:** `posteam_won` (1 = possession team won, 0 = lost) — derived from `result` + `home_team` in Silver

**Models:** Logistic Regression (C grid: 0.01, 0.1, 1.0, 10.0) and XGBoost (n_estimators × max_depth × learning_rate grid = 8 combos)

**MLflow tracking:** parent run per model type; child run per hyperparameter combo. `mlflow.evaluate()` logs ROC AUC, accuracy, precision, recall, confusion matrix automatically. `mlflow.log_table()` logs per-prediction error table for post-hoc situational analysis. Feature importance logged as CSV artifact on best run.

**Result:** XGBoost best AUC ~0.84. Earlier in the game = harder predictions (less information resolved). Feature importance shows `game_seconds_remaining` and `score_differential` dominate.

**Story:** "I built a WP classifier from scratch — given a 3rd-and-7 from your own 25 with 4 minutes left and down by 3, what are the odds you win? 84% AUC. I used MLflow to grid-search two model types and log evaluation tables that let me slice predictions by game situation to understand where the model struggles."

---

### Experiment 2 — Situation-Adjusted QB EPA
**Goal:** Control for situation to isolate true QB contribution above expectation.

**Features (numeric):** `yards_to_go, yards_from_end_zone, score_differential, game_seconds_remaining, time_to_throw, intended_air_yards, personnel_rb, personnel_te, personnel_wr`

**Features (categorical):** `down, distance_bucket, offense_formation, defense_coverage_type, pass_length`

**Target:** `qb_expected_points_added`

**Model:** XGBoost regressor with `SelectFromModel` feature selection step in pipeline (see ADR-027). Predict expected EPA given situation; residuals per QB across seasons = situation-adjusted value above expectation.

**MLflow tracking:** RMSE, feature importance, permutation importance logged as artifact, per-QB residuals logged as artifact.

**Story:** "Same concept as CPOE but applied to EPA — controlling for situation to isolate quarterback value. Sparse NGS columns (time_to_throw, coverage type) required a feature selection step to prevent noise from degrading the model."

---

### Experiment 3 — Play Concept Clustering & Classification
**Goal:** Evolve the rule-based `concept_label` taxonomy into a 
data-driven play concept model.

**Phase 1 (Silver):** Rule-based mapping in `config/play_concept_map.py`

**Phase 2 (MLflow):** KMeans clustering on play features to validate 
and refine rule-based labels. Manual cluster inspection and labeling.

**Phase 3 (MLflow):** XGBoost classifier trained on labeled clusters 
to predict play concept from pre-snap features only — formation, personnel, down, distance, game situation.

**Features:** offense_formation, personnel_rb, personnel_te, personnel_wr, pass_length, pass_location, run_location, down, distance_bucket, route

**MLflow tracking:** inertia curve, silhouette score, cluster assignments, classifier accuracy, confusion matrix

**Story:** "Started with a rule-based play concept taxonomy, validated it with unsupervised clustering, then built a pre-snap classifier — predicting what a team is likely to run before the ball is snapped."

---

## Infrastructure (Terraform)

Provisions:
- Azure Resource Group
- ADLS Gen2 storage account + container
- Azure Databricks workspace
- Azure Key Vault (secrets: storage account key, Databricks token)
- Databricks cluster definition
- Unity Catalog metastore + catalog

Location: `infra/`

---

## Key Design Decisions

**ADR-001: Azure over AWS/GCP**
Aligns with existing certifications and client environment familiarity.

**ADR-002: nfl-data-py over nflfastR**
Python-native stack eliminates R dependency. Same underlying data.

**ADR-003: Medallion Architecture**
Industry standard lakehouse pattern. Directly mirrors Databricks 
customer conversations.

**ADR-004: dbt for Gold layer**
dbt proficiency is a common customer ask Databricks SEs field. 
Demonstrates modern data stack awareness.

**ADR-005: Retain sparse NGS columns with null flagging**
`defense_coverage_type` (~45% coverage) and tracking columns are 
retained with honest null flags rather than dropped. Dropping sparse 
columns prematurely destroys analytical value — the 45% of plays with 
coverage data is still a large, useful dataset.

**ADR-006: Play concept taxonomy as two-phase design**
Rule-based mapping (Phase 1) provides immediate analytical value and 
a labeled baseline. MLflow clustering (Phase 3) validates and refines 
it. This mirrors how production ML systems evolve from heuristics to 
learned models.

**ADR-007: Gold designed to serve specific analytical questions**
Gold tables prioritize real-world NFL team utility over exhaustive 
coverage. Situational EPA, QB efficiency, and team tendencies are 
metrics actual analytics departments use. Personnel grouping analysis 
was explicitly deprioritized as analytically commoditized.

**ADR-008: `mart_plays` as the analytical engine**
The play-level mart is wide and fully denormalized — every play carries all its
context (team, player, situation, EPA, NGS columns) so arbitrary slice-and-dice
queries require zero joins at query time. This directly supports the platform's
goal of answering any player or team question at any level of granularity.
Rollup marts (player, team, season) are conveniences for the dashboard,
not the primary analytical surface.

**ADR-009: Three-layer dbt structure (staging → intermediate → marts)**
Staging translates Silver to dbt world (column renames, source definition, no
business logic). Intermediate handles joins and assembly. Marts are the final
exposed tables. This separation makes debugging deterministic — each layer has
a single responsibility, so a data quality issue is traceable to exactly one layer.

**ADR-010: Python config as source of truth for business logic**
`play_concept_map.py` drives the `play_concept` and `concept_label` columns
during the Silver transform. dbt Gold models consume these columns as-is —
business logic is not re-implemented in SQL. Changing the taxonomy means
editing one Python file and re-running Silver; Gold picks it up automatically.

**ADR-011: Human-readable column names enforced at Silver**
All abbreviated or source-system column names (e.g. `posteam`, `epa`, `cpoe`)
are renamed to full descriptive names (e.g. `offense_team`, `expected_points_added`,
`completion_pct_over_expected`) in the Silver transform via an explicit RENAME_MAP.
This means every layer above Silver — dbt, ML, dashboard — works with self-documenting
column names. The rename is applied after all derived column logic so intermediate
calculations still reference original Bronze names.

**ADR-012: Factual derivations belong in Silver, analytical derivations in Gold**
Silver is the appropriate home for columns that are mathematically unambiguous
derivations of existing fields — there is one correct answer and no business
judgement involved. `quarter` (derived from game_seconds_remaining) and
`two_minute` (final 2 mins of Q2/Q4) fall into this category alongside
`distance_bucket`. Analytical derivations that involve a design choice
(e.g. what threshold defines "success" or "high leverage") also currently
live in Silver but could reasonably be debated. This rule provides a
decision framework for future derived columns: if it's pure math, it's Silver;
if it encodes a business choice, it belongs in Gold intermediate.

**ADR-013: Retain intermediate layer despite minimal column count**
`int_plays_enriched.sql` derives only two columns (`primary_player_name`,
`primary_player_id`), but the intermediate layer is kept because both columns
are consumed by three separate marts (mart_plays, mart_player_game,
mart_player_season). Centralising the CASE WHEN logic once in intermediate
is preferable to repeating it across marts — a single change propagates
everywhere. If the intermediate layer ever grows to zero dependents, it
should be removed. `game_half` was explicitly rejected as an intermediate
column because it is trivially derivable from `quarter` at query time
and adds no storage value.

**ADR-014: Mart-level materialization strategy**
All mart models are materialized as `table` in Databricks. Marts are the
primary query surface for the dashboard and ML pipelines — query speed
takes priority over build time. Views were rejected because repeated
dashboard queries against a view re-execute the full SQL on every request,
which is unacceptable at mart_plays scale (~150k+ rows across 3 seasons).
Incremental materialization is reserved for production scale; `table` is
appropriate for the current dataset size and rebuild cadence.

**ADR-015: Surrogate key on all mart tables**
All mart models include a surrogate key column (`mart_key`) generated via
`dbt_utils.generate_surrogate_key()` from the natural composite key of each
mart. For mart_plays this is `['game_id', 'play_id']`. A single-column
unique identifier simplifies joins between marts, enables reliable dbt
uniqueness tests, and makes dashboard tooling and ML feature pipelines
easier to work with than composite keys.

**ADR-016: Season-level marts reference game-level marts, not play-level data**
mart_player_season and mart_team_season reference their game-level counterparts
(mart_player_game, mart_team_game) rather than int_plays_enriched directly.
This enforces a clean dependency chain: plays → game → season. Each layer
aggregates from the layer below it. Season-level rates are recomputed from
summed game-level counts (see ADR-017), never by averaging game-level rates.
QB efficiency metrics (cpoe, intended_air_yards) are weighted by pass_plays
so high-volume games contribute proportionally to season averages.

**ADR-017: Raw counts stored alongside rates in game-level marts**
Game-level marts store both raw counts (e.g. `successful_plays`, `pass_plays`)
and derived rates (e.g. `success_rate`, `pass_rate`). Raw counts are required
by season-level marts to correctly recompute rates from totals rather than
averaging game-level rates. Averaging rates across games produces incorrect
results when play counts vary — a 5-play game and a 50-play game would be
weighted equally. Storing raw counts at game level makes correct season
aggregation possible without re-reading play-level data.

**ADR-018: Roster data follows the same Bronze → Silver → Gold medallion pattern**
No shortcuts to Silver, even for simple lookup data. Consistent pipeline
patterns across all data sources make the project easier to reason about,
debug, and extend. The Bronze layer retains the raw roster file exactly as
nfl-data-py returns it; Silver selects and cleans the relevant columns.

**ADR-019: `dim_players` grain is player_id + season, not player_id alone**
Players change teams across seasons. A single-row-per-player design would
produce incorrect joins when a player's team changes between years — a TE
who played for the Eagles in 2023 and the Cowboys in 2024 needs two rows.
Joining play data to dim_players uses season + player_id so every join is
accurate to the season the play occurred in.

**ADR-020: Databricks Workflows as the orchestration layer (not yet implemented)**

The current pipeline is fully manual: ingestion and transform scripts run locally, Silver
is uploaded to ADLS via CLI, and `dbt run` is executed by hand. This works for development
but is not repeatable or production-grade.

Decision: when orchestration is implemented, use **Databricks Workflows** as the DAG
orchestrator. Workflows is native to the Databricks platform, has first-class dbt support,
requires no additional services, and is a strong portfolio talking point.

The planned task chain is:
1. Python task — `ingest_pbp.py` + `ingest_rosters.py` (Bronze)
2. Python task — `transform_pbp.py` + `transform_rosters.py` (Silver)
3. Notebook task — register/refresh Silver Delta tables in Unity Catalog
4. dbt task — `dbt run` (Gold)

Prerequisite: ingestion and transform scripts must move from local execution into
Databricks. The recommended path is connecting the GitHub repo via **Databricks Repos**
so Workflows pulls scripts directly from source control — no manual uploads, no DBFS
copying.

Alternatives considered: Azure Data Factory (heavier, more complex, separate service),
Apache Airflow (requires self-hosting or managed MWAA, overkill for this project).

Status: **deferred** — to be implemented after Phase 5 (dashboard).

**ADR-021: Win Probability target is binary classification, not WP regression**

The dataset already contains a pre-calculated `wp` column from nflfastR. Training a model to predict `wp` is training another surrogate of the same surrogate — circular, and not analytically interesting. Instead the WP experiment predicts `posteam_won` (1/0), the actual game outcome. This answers the real question: given a game situation, did the possession team end up winning? Binary classification also enables ROC AUC as a single interpretable metric and produces a posterior probability that is directly usable in-game analytics contexts. `posteam_won` is derived from `result > 0` (home team won) and `posteam == home_team` in the Silver transform so the label is available in `mart_plays`.

**ADR-022: Model class wraps a full sklearn Pipeline**

`WinProbabilityModel` (and future experiment model classes) encapsulate the full sklearn Pipeline — preprocessor + estimator — rather than exposing the pipeline externally or logging just the estimator. This means the MLflow artifact is self-contained: loading the run's model artifact gives you a complete, deployable object that handles raw feature input with no pre-processing setup on the caller's side. It also means `mlflow.evaluate()` can call the logged artifact directly without extra wiring. The class exposes `fit()`, `predict_proba()`, `get_fit_summary()`, and `get_feature_importances()` as a stable interface regardless of the underlying model type.

**ADR-023: Parent/child MLflow run hierarchy for grid search**

Grid search across hyperparameter combos is logged as a two-level hierarchy: one parent run per model type (e.g. `wp_logreg`, `wp_xgboost`), one child run per hyperparameter combination. The parent run summarizes the experiment (logs `best_auc`); each child run is self-contained with its params, metrics, model artifact, evaluation tables, and feature importance. This mirrors how production ML teams use MLflow — the parent is the "experiment session," children are individual trials. The MLflow UI renders this as an expandable tree that makes comparison straightforward without polluting the top-level experiment view with every variant.

**ADR-024: `mlflow.evaluate()` over manual metric logging for evaluation**

`mlflow.evaluate()` is called on each child run after the model artifact is logged. It loads the artifact, runs predictions on `eval_data`, and logs ROC AUC, accuracy, precision, recall, F1, and a confusion matrix automatically as structured evaluation tables. This replaces manual `mlflow.log_metrics({"auc": ...})` calls and produces richer, queryable evaluation data in the MLflow UI. Additionally, `mlflow.log_table()` logs a per-prediction DataFrame (features + predicted proba + label + correct flag) that enables post-hoc slicing by game situation — e.g. filtering to rows where `game_seconds_remaining < 120` to see model performance in two-minute-drill situations.

**ADR-025: `ml_config.py` naming to avoid root package collision**

The ML config file is named `ml_config.py`, not `config.py`. The root of the repo contains a `config/` directory (a Python package for `settings.py` and `play_concept_map.py`). When Python resolves `from config import X`, it finds the package first and raises `ImportError`. Renaming to `ml_config.py` sidesteps this entirely. All ML modules import from `ml_config` explicitly.

**ADR-026: Explicit column list in `stg_pbp.sql` (not `SELECT *`)**

Databricks Serverless SQL Warehouse caches the column expansion of `SELECT *` at view-creation time, not at query time. When a new column is added to Silver (`posteam_won`), the `stg_pbp` view must be dropped and recreated. Even after recreation, the Serverless warehouse may serve the old schema until the warehouse is restarted. The fix is to use an explicit column list in `stg_pbp.sql` — this makes the view definition explicit and avoids the caching problem entirely. Any future Silver schema changes require updating the staging view's column list, which is a small cost for reliable schema propagation.

**ADR-027: Feature selection in QB EPA experiment, not WP**

The WP model uses 7 hand-picked situational features — all are known strong signals (down, distance, score, time, timeouts). Feature selection adds no value here. The QB EPA model includes sparse NGS columns (`time_to_throw`, `intended_air_yards`, `defense_coverage_type`) that have significant null rates and may add noise rather than signal. The appropriate place to handle this is a `SelectFromModel` step in the sklearn Pipeline between the preprocessor and the XGBoost estimator. The selected feature mask is logged as a permutation importance artifact so the selection can be inspected and audited.

**ADR-028: MLflow models registered in Unity Catalog under the Gold schema**

MLflow model artifacts for production experiments are registered in Unity Catalog using a three-level namespace: `nfllakehouse_databricks.gold.<model_name>` (e.g. `nfllakehouse_databricks.gold.qb_epa`). Registering under the Gold schema co-locates model artifacts with the Delta tables they are derived from, making the relationship between data and model explicit in the same governance layer. Unity Catalog applies the same lineage tracking, access control, and discoverability to registered models as it does to tables — a model registered here is auditable and permissioned consistently with the rest of the platform. This follows the Databricks-recommended path of UC Model Registry over the legacy workspace model registry, which has no lineage integration and is being deprecated in favour of UC. The `@champion` alias is set on the best-performing version after each experiment run so downstream consumers can always load the current best model by alias without hardcoding a run ID.

---

## Project Phases

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Repo structure, Bronze ingestion, EDA | Complete |
| 2 | Silver transformation pipeline | Complete |
| 3 | Azure + Terraform provisioning | Complete |
| 4 | Gold dbt models + Unity Catalog deployment | Complete |
| 5 | Databricks SQL dashboard (Pages 1-3) | Complete (Pages 4-5 pending) |
| 6 | MLflow Experiment 1 (WP model) | Complete |
| 7 | MLflow Experiment 2 (QB EPA) | Next |
| 8 | MLflow Experiment 3 (Play clustering) | Pending |