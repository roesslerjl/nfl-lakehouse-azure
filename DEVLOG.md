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