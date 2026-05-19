# DEVLOG

Running log of build sessions. Updated after every session.

---

## 2026-05-10

### What I did
- Set up conda environment (nfl-lakehouse, Python 3.11)
- Installed Claude Code v2.1.138
- Initialized CLAUDE.md with full project context and learning guardrails

### What I learned
- Claude Code reads CLAUDE.md at the start of every session — it's persistent context
- `/init` analyzes repo structure to bootstrap the file
- Claude Code works alongside VS Code: terminal for prompts, VS Code to see changes

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