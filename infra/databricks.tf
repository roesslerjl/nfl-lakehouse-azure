# infra/databricks.tf

# Databricks workspace — the web UI and compute environment where notebooks,
# jobs, and SQL warehouses run. 
# ADLS Gen2 is the "storage" it reads from and writes to.
resource "azurerm_databricks_workspace" "main" {
  name                = "${var.project_name}-databricks"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # Premium SKU required — Standard is deprecated as of 2026.
  # Premium also unlocks Unity Catalog and row-level security.
  sku = "premium"

  tags = {
    project = var.project_name
  }
}

# Serverless SQL Warehouse — compute for dbt Gold models and Databricks SQL dashboard.
#
# NOTE: Classic cluster provisioning was attempted first but failed for two reasons:
#   1. Azure for Students subscription has a 6 vCPU regional limit in southcentralus
#   2. DSv3 and Dv2 VM families showed physical capacity shortages ("SkuNotAvailable")
#      even within available quota — a datacenter supply issue, not a quota issue.
#
# Serverless SQL Warehouses bypass both problems: they run on Databricks-managed
# infrastructure outside the customer's Azure subscription, so no VM quota or
# capacity constraints apply. This is also the current Databricks best practice
# for SQL workloads and dbt integration.
#
# In a production environment with proper VM quota, a classic cluster would be used
# for PySpark notebook workloads alongside the SQL Warehouse for dbt/SQL.
resource "databricks_sql_endpoint" "main" {
  name                      = "nfl-lakehouse-warehouse"
  cluster_size              = "2X-Small"   # smallest tier, sufficient for ~100k row dataset
  warehouse_type            = "PRO"        # PRO tier enables serverless compute
  enable_serverless_compute = true
  auto_stop_mins            = 10           # suspend after 10min idle — only pay when running
}
