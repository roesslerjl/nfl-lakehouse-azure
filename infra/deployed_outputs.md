# Deployed Infrastructure Outputs

Values produced by `terraform apply`. 
To update this file after any infrastructure change.

| Output | Value |
|---|---|
| Resource Group | `rg-nfl-lakehouse` |
| Location | `southcentralus` |
| Storage Account | `nfllakehousestorage` |
| Storage Container | `lakehouse` |
| Key Vault | `nfllakehouse-kv` |
| Databricks Workspace URL | `adb-7405614832902513.13.azuredatabricks.net` |
| ADLS Bronze Path | `abfss://lakehouse@nfllakehousestorage.dfs.core.windows.net/bronze` |
| ADLS Silver Path | `abfss://lakehouse@nfllakehousestorage.dfs.core.windows.net/silver` |
| ADLS Gold Path | `abfss://lakehouse@nfllakehousestorage.dfs.core.windows.net/gold` |
| SQL Warehouse HTTP Path | `/sql/1.0/warehouses/e23f37ca1e706f17` |

## dbt Connection Profile

Used when configuring `~/.dbt/profiles.yml` in Phase 4:

```yaml
nfl_lakehouse:
  target: dev
  outputs:
    dev:
      type: databricks
      host: adb-7405614832902513.13.azuredatabricks.net
      http_path: /sql/1.0/warehouses/e23f37ca1e706f17
      schema: gold
```
