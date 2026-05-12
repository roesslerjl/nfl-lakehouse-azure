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

**NGS-derived columns retained from Bronze**
- `time_to_throw` — seconds from snap to throw (NGS)
- `ngs_air_yards` — intended air yards per NGS tracking (vs. actual)
- `was_pressure` — whether QB faced pressure (NGS)
- `route` — targeted receiver's route (NGS, sparse)
- `defense_coverage_type` — man/zone coverage (NGS, ~45% coverage)

#### Silver column manifest:
season, week, game_id, play_id
posteam, defteam
passer_player_name, passer_player_id, rusher_player_name, rusher_player_id, receiver_player_name
play_type, down, ydstogo, yardline_100
distance_bucket, score_differential, game_seconds_remaining
offense_formation, defense_coverage_type, coverage_available
personnel_rb, personnel_te, personnel_wr
play_concept, concept_label
pass_length, pass_location, run_location, run_gap
route, time_to_throw, ngs_air_yards
epa, wp, wpa, was_pressure, cpoe, qb_epa
success, high_leverage
posteam_timeouts_remaining, defteam_timeouts_remaining

---

### Gold — Analytics-Ready Tables (dbt models)

#### `gold.situational_epa` — play-level analytical table
One row per play. Primary source for dashboard drill-down queries.

Key columns: all Silver columns minus raw NGS fields, plus human-readable labels.

**Dashboard question:** In 3rd and long from Shotgun, how does QB X perform under pressure vs. no pressure across coverage types?

---

#### `gold.qb_efficiency` — one row per QB per season
Aggregated from `situational_epa`.

| Column | Description |
|---|---|
| season | NFL season year |
| passer_name | QB name |
| team | Team abbreviation |
| plays | Total dropbacks |
| epa_per_play | Average EPA per dropback |
| success_rate | % plays with epa > 0 |
| cpoe_avg | Avg completion % over expectation |
| pressure_epa | EPA per play under pressure |
| no_pressure_epa | EPA per play clean pocket |
| pressure_epa_delta | Difference (pocket presence metric) |
| high_leverage_epa | EPA in competitive game situations only |
| avg_time_to_throw | Avg seconds to release |
| avg_ngs_air_yards | Avg intended air yards |

**Dashboard question:** Which QBs maintain performance under pressure? 
Who are the most aggressive downfield passers by intended air yards?

---

#### `gold.team_situational` — one row per team per down/distance/season
Aggregated from `situational_epa`.

| Column | Description |
|---|---|
| season | NFL season year |
| posteam | Offensive team |
| down | 1-4 |
| distance_bucket | short / medium / long |
| play_type | run / pass |
| offense_formation | Shotgun / Under Center / Pistol |
| plays | Play count |
| epa_per_play | Average EPA |
| success_rate | % positive EPA plays |
| pass_rate | % pass plays in this situation |

**Dashboard question:** Which teams are most efficient on 2nd and medium? 
Who over-relies on passing in short yardage situations?

---

## MLflow Experiments

### Experiment 1 — Win Probability Model
**Goal:** Train a WP model from scratch and benchmark against the nflfastR 
baseline already embedded in the dataset (`wp` column).

**Features:** `down, ydstogo, yardline_100, score_differential, 
game_seconds_remaining, posteam_timeouts_remaining, defteam_timeouts_remaining`

**Target:** `wp`

**Models:** Logistic Regression baseline → XGBoost

**MLflow tracking:** params, RMSE, AUC, feature importance per run

**Story:** "I built a WP model from scratch and benchmarked it against the 
industry standard — the nflfastR model used by ESPN and NFL teams."

---

### Experiment 2 — Situation-Adjusted QB EPA
**Goal:** Control for situation to isolate true QB contribution above expectation.

**Features:** `down, distance_bucket, yardline_100, score_differential, 
was_pressure, offense_formation, defense_coverage_type, time_to_throw, 
ngs_air_yards`

**Target:** `epa`

**Model:** XGBoost regressor — predict expected EPA given situation, 
measure actual vs. expected per QB across seasons

**MLflow tracking:** RMSE, feature importance, per-QB residuals logged as 
artifacts

**Story:** "Same concept as CPOE but applied to EPA — controlling for 
situation to isolate quarterback value."

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

---

## Project Phases

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Repo structure, Bronze ingestion, EDA | Complete |
| 2 | Silver transformation pipeline | Complete |
| 3 | Azure + Terraform provisioning | Pending |
| 4 | Gold dbt models | Pending |
| 5 | Databricks SQL dashboard | Pending |
| 6 | MLflow Experiment 1 (WP model) | Pending |
| 7 | MLflow Experiment 2 (QB EPA) | Pending |
| 8 | MLflow Experiment 3 (Play clustering) | Pending |