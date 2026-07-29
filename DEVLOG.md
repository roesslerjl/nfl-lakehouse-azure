# DEVLOG

Running log of build sessions. Updated after every session.

---

## 2026-05-10

### What I did
- Set up conda environment (nfl-lakehouse, Python 3.11)

### What I learned
- VS Code alongside terminal: terminal for running scripts, VS Code to review changes

### What's next
- Create ARCHITECTURE.md
- Write first data exploration notebook (nfl-data-py, local, no cloud)

## 2026-05-10 (continued)

### What I did
- Loaded 2023 NFL play-by-play via nfl-data-py: 48,771 rows, 397 columns
- Audited null counts on key analytical columns
- Filtered to run/pass plays (34,628) and ran first EPA analysis

### What I learned
- EPA, WP, and WPA are already pre-calculated in the dataset — models build on top of them
- defense_coverage_type missing 55%+ of rows — unreliable as model feature
- Passing EPA (+0.014) > Rushing EPA (-0.007) — confirms established analytics finding
- 4th down high EPA is survivorship bias, not inherent value — important interview nuance
- 3rd down negative EPA driven by failed conversions destroying expected points

### What's next
- More exploration cells: EPA by formation and down/distance situation
- Then define Bronze layer schema and start repo structure

## 2026-05-10 (continued)

### What I did
- Ran personnel grouping analysis on offense_personnel column
- Discovered formation data only has 3 values (Shotgun, Under Center, Pistol)
- Identified why: Next Gen Stats tracking coverage gaps

### What I learned
- offense_personnel includes ALL players including linemen (C, G, T) — 
  standard NFL groupings only count skill positions (RB, TE, WR)
- Personnel naming convention: 1RB/1TE/3WR = "11 personnel", 
  1RB/2TE/2WR = "12 personnel" etc.
- 11 personnel is most common (14,533 plays), positive EPA (+0.003)
- 2 RB sets generate negative EPA (-0.089) — heavy formations destroy value
- Parsing offense_personnel string into structured columns is Silver layer work —
  requires regex to extract RB/TE/WR counts and ignore linemen
- Raw string groupings are not analytically useful without transformation

### What's next
- Commit exploration notebook
- Set up repo folder structure (infra/, src/, dbt/, tests/)
- Write first Bronze ingestion script

---

## 2026-05-12

### What I did
- Designed full Silver transformation pipeline with schema-driven approach (Gold → Silver → Bronze)
- Built `src/transforms/transform_pbp.py`: filters to run/pass, casts types, derives columns
- Built `config/play_concept_map.py`: rule-based formation+direction → concept label taxonomy
- Wrote full architecture document (ARCHITECTURE.md) covering all medallion layers, Gold tables, MLflow experiments
- Provisioned Azure infrastructure via Terraform: ADLS Gen2, Databricks workspace (Premium), Serverless SQL Warehouse, Key Vault
- Uploaded Bronze and Silver Parquet files to ADLS Gen2 via `az storage blob upload-batch`
- Configured Unity Catalog External Location with managed identity for credential-free ADLS access
- Verified Databricks Serverless SQL Warehouse can read Silver data from ADLS end to end

### What I learned
- Schema-driven design: design Silver to serve Gold, not just to fix Bronze — avoids rework
- `terraform.tfvars` overrides `variables.tf` defaults — always check both when debugging
- Azure for Students subscription has 6 vCPU regional limit and physical capacity shortages for Dv2/DSv3 in southcentralus
- Serverless SQL Warehouses bypass Azure VM quota entirely — runs on Databricks-managed infrastructure
- Serverless SQL Warehouses don't support `spark.conf.set` for storage credentials — Unity Catalog External Locations are required
- Unity Catalog External Location + managed identity = credential-free, production-grade ADLS access
- `az storage blob upload-batch --auth-mode key` is the fastest way to push local Parquet to ADLS

### What's next
- Phase 4: dbt Gold models (situational_epa, qb_efficiency, team_situational)
- Set up dbt-databricks project and profiles.yml using deployed_outputs.md values

---

## 2026-05-18 / 2026-05-19

### What I did
- Redesigned Gold layer architecture from scratch — replaced the original three-table design with a proper mart structure
- Built full dbt project structure: staging → intermediate → marts
- Added `stg_pbp.sql` and `sources.yml` — Silver source registration and staging translation layer
- Built `int_plays_enriched.sql` — intermediate assembly layer deriving primary_player_name/id
- Built `mart_plays.sql` — wide, fully denormalized play-level analytical engine
- Built `mart_drives.sql` — drive-level aggregations with starting field position via window function
- Built `mart_player_game.sql` and `mart_player_season.sql` — role-based player performance (passer / rusher / receiver)
- Built `mart_team_game.sql` and `mart_team_season.sql` — combined offense + defense stats per team per game/season
- Built full roster pipeline: `ingest_rosters.py` + `transform_rosters.py` → `dim_players.sql`
- Installed dbt_utils package for surrogate key generation
- Updated `dbt_project.yml` with correct model paths and per-layer materialization defaults
- Refactored Silver transform significantly:
  - Added human-readable column renames (RENAME_MAP) — `epa` → `expected_points_added`, `posteam` → `offense_team`, etc.
  - Added `quarter`, `two_minute`, `red_zone` derived columns
  - Added `fixed_drive`, `fixed_drive_result`, `yards_gained`, `receiver_player_id` to Silver schema
  - Fixed base paths in `config/settings.py` — removed hardcoded `/pbp` so multiple data sources can share the same Bronze/Silver root
- Documented 13 architectural decisions (ADR-006 through ADR-019) in ARCHITECTURE.md

### What I learned
- Staging layer should be a thin translation layer only — no logic, no joins, just a clean source reference
- Intermediate layer earns its place when logic is consumed by 3+ downstream models — centralise once, not three copies
- Season-level rates must be recomputed from raw counts, never by averaging game-level rates — a 10-play game and a 50-play game would be weighted equally otherwise
- `mart_plays` as a wide, denormalized play-level table enables arbitrary slice-and-dice queries without joins at query time
- Player dimension table (`dim_players`) is essential for positional filtering — player IDs are the reliable join key, not names
- Role-based player mart grain (passer/rusher/receiver per game) preserves analytical clarity — passing EPA and rushing EPA for the same player should not be merged
- `fixed_drive` is preferred over `drive` in nfl-data-py — corrects tracking inconsistencies in the raw column
- Factual derivations (quarter, red_zone, two_minute) belong in Silver — pure math with one correct answer. Analytical derivations with business judgement belong in Gold
- Base paths in settings.py should be dataset-agnostic — each script appends its own subdirectory

### What's next
- Set up `~/.dbt/profiles.yml` with Databricks connection details
- Upload refreshed Silver Parquet files to ADLS Gen2
- Run `dbt run` against Databricks SQL Warehouse
- Phase 5: Databricks SQL dashboard

---

## 2026-05-19

### What I did
- Configured `~/.dbt/profiles.yml` with Databricks SQL Warehouse connection (catalog fixed from `main` → `nfllakehouse_databricks`)
- Verified dbt connection: `dbt debug` all checks passed
- Re-uploaded refreshed Silver Parquet (6 files — pbp + rosters × 3 seasons) to ADLS Gen2
- Created `nfllakehouse_databricks.silver` schema in Unity Catalog
- Converted Silver Parquet to Delta in-place using `DeltaTable.convertToDelta()` and registered both tables
- Fixed three bugs discovered during `dbt run`:
  - `int_plays_enriched.sql` missing `fixed_drive` and `fixed_drive_result` in pass-through columns
  - `mart_team_game.sql` trailing comma in `defense_stats` CTE and `pass_plays_allowed` missing from `combined` CTE
  - `mart_drives.sql` ambiguous `game_id` reference in `generate_surrogate_key` — qualified as `ds.game_id`
- All 10 Gold models built successfully in Unity Catalog (`gold` schema)
- Documented ADR-020: Databricks Workflows as future orchestration layer (deferred to post-Phase 5)

### What I learned
- `DeltaTable.convertToDelta()` converts existing Parquet to Delta in-place — just adds a `_delta_log`, no data rewrite
- When running `dbt run --select <model>`, upstream views are NOT rebuilt unless you use the `+` prefix — stale view definitions cause silent column-not-found errors
- `generate_surrogate_key` uses raw column name strings in the SQL it generates — qualify with table alias when the final SELECT has a join to avoid ambiguous reference errors
- Databricks Workflows is the native orchestration answer for this stack; full automation requires moving ingestion/transform scripts into Databricks via Repos

### What's next
- Phase 5: Databricks SQL dashboard
  - Player performance explorer (position, team, season, situation filters)
  - Team efficiency rankings (offense + defense EPA per play)
  - Drive efficiency analysis
  - Situational tendencies (formation, personnel, down/distance)

---

## 2026-05-19 (evening) / 2026-05-20

### What I did
- Renamed `players_dim.sql` → `dim_players.sql` for naming consistency
- Cleaned up `.gitignore`: removed malformed line, added `CLAUDE.md` and `HANDOFF.md` as local-only files
- Removed all tooling references from `DEVLOG.md` — project docs are tool-agnostic
- Started Phase 5: Databricks SQL Lakeview dashboard
- Created `NFL Analytics Lakehouse` dashboard in Databricks SQL
- Built Page 1 — Team Efficiency Rankings:
  - Bar chart: offensive EPA/play by team, sorted descending
  - Table: full team stats (offense + defense) side by side
  - Season filter wired to both widgets — single selection updates entire page
- Added QB Deep Dive dataset to Databricks (mart_plays filtered to pass plays) — ready to build Page 2 next session

### What I learned
- Lakeview dashboard filter widgets added via the funnel icon in the toolbar — not inside chart widget settings
- Dashboard-level filters auto-wire to all widgets using the same dataset
- `avg()` in SQL ignores NULL values automatically — no special CASE WHEN needed to exclude nulls from averages
- `HAVING` filters after aggregation (post-GROUP BY); `WHERE` filters before — you cannot reference column aliases in HAVING, must use the original expression e.g. `HAVING count(*) > 100`
- `GROUP BY` gives `count(*)` its per-group context — without it, count would span the entire table

### What's next
- Page 2: QB Deep Dive
  - Query: aggregate mart_plays (pass plays) to one row per QB per season
  - Metrics: EPA/dropback, CPOE, pressure rate faced, EPA under pressure, deep ball rate/EPA, avg time to throw
  - Filters: season, week (game level), QB name, pass_length, down
- Pages 3-5: Player Explorer, Situational Tendencies, Drive Efficiency

---

## 2026-05-21 / 2026-05-23

### What I did

**Phase 5 — Dashboard (Pages 2 & 3)**
- Built Page 2 — QB Deep Dive:
  - Dual-axis bar chart: EPA/dropback (bar) and CPOE (line) per QB, season-filtered
  - Stats table: EPA/dropback, CPOE, pressure rate faced, EPA under pressure, deep ball rate, deep ball EPA, avg time to throw
  - `HAVING count(*) > 100` filter to exclude QBs with too few dropbacks to be meaningful
  - Season filter wired to both widgets
- Built Page 3 — Player Performance Explorer:
  - Scatter plot: EPA/play (x) vs. yards/play (y), colored by position, sized by play count
  - Player detail table with season-level stats (EPA, yards, success rate, plays)
  - Filters: season, position group (pass/run), player name
  - Deduplication issue: Caleb Williams appeared twice (one row as passer, one as rusher in mart_player_season). Resolved by filtering scatter to primary role or using `WHERE role = 'passer'` depending on the selected position group

**Phase 6 — ML Experiments scaffold**
- Rebuilt `src/ml/` from scratch in a production-grade structure with a per-experiment subfolder per experiment:
  ```
  src/ml/
  ├── ml_config.py                   # all constants, feature lists, param grids, experiment paths
  ├── shared/
  │   ├── features.py                # data loading + train/test split per experiment
  │   ├── preprocessing.py           # sklearn ColumnTransformer builders, RareCategoryGrouper
  │   └── mlflow_utils.py            # get_or_create_experiment, log_run, log_feature_importance
  ├── win_probability/
  │   ├── model.py                   # WinProbabilityModel class wrapping sklearn Pipeline
  │   └── train.py                   # grid search + mlflow.evaluate() + mlflow.log_table()
  ├── qb_epa/                        # (next)
  └── play_clustering/               # (next)
  ```
- Built `ml_config.py` — single source of truth for all feature lists, target columns, param grids, and MLflow experiment paths. Named `ml_config.py` (not `config.py`) to avoid shadowing the root `config/` package
- Built `shared/features.py` — `load_mart_plays()`, `get_wp_features()`, `get_qb_epa_features()`, `get_clustering_features()`
- Built `shared/preprocessing.py`:
  - `RareCategoryGrouper` custom transformer — collapses infrequent categories into "Other" before OHE (min_freq=0.02)
  - `build_wp_preprocessor()` — numeric-only ColumnTransformer
  - `build_qb_epa_preprocessor()` — numeric + per-column categorical transformers
  - `build_clustering_preprocessor()` — returns (preprocessor, X_combined) for unsupervised pipeline
- Built `shared/mlflow_utils.py` — `get_or_create_experiment()`, `log_run()`, `log_feature_importance()`
- Built `win_probability/model.py` — `WinProbabilityModel` class:
  - Wraps full sklearn Pipeline (preprocessor + estimator) so the logged artifact is self-contained
  - Supports `"logreg"` and `"xgboost"` model types
  - `fit()` builds and trains pipeline; `predict_proba()`, `get_fit_summary()`, `get_feature_importances()` as public interface
- Built `win_probability/train.py` — production-grade grid search:
  - Parent/child MLflow run hierarchy: one parent per model type, one child per hyperparameter combo
  - `mlflow.evaluate()` for structured evaluation tables (ROC AUC, accuracy, confusion matrix logged automatically)
  - `mlflow.log_table()` for per-prediction error table (predicted proba, label, correct flag) — enables post-hoc error analysis by game situation
  - Best model's feature importance logged as CSV artifact on the best child run

**Silver schema update for posteam_won**
- Added `posteam_won` derived column to `transform_pbp.py`:
  - Derives `home_won` from `result > 0`, `posteam_is_home` from `posteam == home_team`
  - Combines to `posteam_won = (posteam_is_home & home_won) | (~posteam_is_home & ~home_won)` → cast to int8
  - `result` and `home_team` dropped after derivation (not in final Silver schema)
- Re-uploaded refreshed Silver Parquet to ADLS Gen2
- Deleted stale `_delta_log` before reconverting to Delta — required because Databricks caches the old transaction log schema
- Dropped and recreated Silver table in Unity Catalog to force schema refresh
- Restarted SQL Warehouse to clear metadata cache (Serverless caches table schema at connection time)
- Updated dbt models to pass through `posteam_won`:
  - `stg_pbp.sql` — changed from `SELECT *` to explicit column list including `posteam_won`
  - `int_plays_enriched.sql` — added to passthrough columns
  - `mart_plays.sql` — added in Game Outcome section
- Ran `dbt run` — all 10 models rebuilt successfully with `posteam_won` in `mart_plays`

**Running the WP experiment in Databricks**
- Connected GitHub repo via Databricks Git Folders (Repos)
- Added `%pip install xgboost` cell at top of training notebook — xgboost not pre-installed on Serverless
- Added `%restart_python` cell after pip installs to clear module cache between runs
- Confirmed `sys.path` pointed to Git folder (not Drafts) before importing project modules
- Ran full WP grid search: 4 logistic regression variants + 8 XGBoost variants = 12 child runs logged
- WP XGBoost best AUC: ~0.84 — strong binary classifier

### What I learned
- Databricks Serverless SQL Warehouse caches `SELECT *` expansion at view-creation time, not query time — adding a column to Silver and rebuilding the view is not enough. Must use an explicit column list in `stg_pbp.sql` to force the new column through
- `_delta_log` must be deleted before calling `DeltaTable.convertToDelta()` after a Silver Parquet rebuild — otherwise Databricks finds the existing log and uses its stale schema
- SQL Warehouse metadata cache persists after table DROP+CREATE — must stop/restart the warehouse to clear it
- `posteam_won` should be a binary target (posteam_won=1/0) not continuous WP regression — the WP column in the dataset is a pre-built surrogate from nflfastR, so building another surrogate is circular. Predicting the actual game outcome (who won?) is the real analytical question
- `posteam_won` is a float64 in Parquet (Delta stores int8, Parquet round-trips differ) — must cast to int before training or sklearn raises `ValueError: Unknown label type continuous`
- MLflow experiment names must be absolute Databricks workspace paths (`/Users/<email>/experiment_name`) — relative names cause silent experiment creation failures
- `config.py` name collides with root `config/` package — `from config import X` picks up the package, not the file. Renamed to `ml_config.py`
- `mlflow.evaluate()` logs ROC AUC, accuracy, precision, recall, and a confusion matrix automatically when `model_type="classifier"` — no manual metric logging needed beyond fit diagnostics
- `mlflow.log_table()` logs a DataFrame as a JSON artifact, queryable in the MLflow UI "Evaluation" tab — enables filtering predictions by game situation to understand where the model struggles
- Parent/child run hierarchy: `mlflow.start_run(nested=True)` inside another active run creates a child run. Parent summarizes the experiment; children capture individual hyperparameter combos. MLflow UI renders this as an expandable tree
- Feature selection not needed for WP (7 features, all signal) — deferred to QB EPA where sparse NGS columns (time_to_throw, intended_air_yards, defense_coverage_type) may add noise

### What's next
- Phase 7 — QB EPA experiment:
  - `qb_epa/model.py` — XGBoost regressor with SelectFromModel feature selection step in pipeline
  - `qb_epa/train.py` — same parent/child run structure; log permutation importance as artifact
  - Coverage audit showed 9 usable coverage types, only ~125 null pass plays out of ~60k — much better than the original EDA 55% null estimate (those nulls were from non-pass plays)
- Pages 4-5 of dashboard (Situational Tendencies, Drive Efficiency) — can be done in parallel with ML