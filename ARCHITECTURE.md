# Architecture Decision Record

This document captures key architecture decisions for the NFL Analytics Lakehouse.
It is a living document and a primary interview artifact.

---

## ADR-001: Cloud Platform — Azure
**Decision:** Azure over AWS or GCP  
**Reason:** Aligns with existing EY certifications (Azure Administrator, Fabric Data Engineer) and client environment familiarity.

---

## ADR-002: Data Source — nfl-data-py
**Decision:** nfl-data-py Python package over nflfastR (R)  
**Reason:** Python-native stack eliminates R dependency; same underlying data.

---

## ADR-003: Medallion Architecture
**Decision:** Bronze / Silver / Gold Delta Lake layers  
**Reason:** Industry standard for lakehouse pattern; directly relevant to Databricks customer conversations.

---

## ADR-004: dbt for Gold Layer
**Decision:** dbt-databricks adapter for Silver → Gold SQL modeling  
**Reason:** dbt proficiency is a common customer ask Databricks SEs field; demonstrates awareness of modern data stack patterns.

---

*Additional decisions to be recorded as the project progresses.*