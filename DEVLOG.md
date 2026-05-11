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