# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Production-grade data lakehouse for NFL analytics on Azure Databricks. Data source is
NFL play-by-play data via the `nfl-data-py` Python package. Architected as an
enterprise-grade deployment demonstrating Databricks platform expertise.

**Full stack:**
- Infrastructure as code via Terraform
- Medallion architecture on Delta Lake (Bronze / Silver / Gold)
- PySpark transformation pipelines
- dbt (dbt-databricks adapter) for Silver → Gold SQL modeling
- MLflow-tracked ML models
- Databricks SQL analytics dashboard

## CRITICAL: How to Work With Me

**Before implementing anything non-trivial, you MUST:**
1. Explain what you're about to do and why
2. Describe the approach you're taking and any alternatives considered
3. Wait for explicit confirmation before writing code

**I am learning this stack.** Every implementation decision should be explainable.
If I can't defend a design choice in an interview, we went too fast.

When I ask "how does X work" — explain it before showing code.
When I ask "build X" — propose an approach first, then implement after I confirm.

## Tech Stack

| Layer | Tool |
|---|---|
| Cloud | Azure (Databricks, ADLS Gen2, Key Vault) |
| IaC | Terraform (`infra/`) |
| Data platform | Azure Databricks + Delta Lake |
| Processing | PySpark |
| SQL modeling | dbt (dbt-databricks adapter) |
| ML tracking | MLflow |
| Analytics | Databricks SQL |
| Data source | nfl-data-py (Python) |

## Architecture

### Medallion Layers
- **Bronze** — raw ingestion f