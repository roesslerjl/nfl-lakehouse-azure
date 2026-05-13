# infra/outputs.tf

# Outputs are values Terraform prints after a successful apply.
# Useful for wiring up the next layer like pasting the workspace URL
# into my browser, or the storage URL into config/settings.py.

output "resource_group_name" {
  description = "Name of the Azure Resource Group"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "Name of the ADLS Gen2 storage account"
  value       = azurerm_storage_account.main.name
}

output "storage_container_name" {
  description = "Name of the lakehouse container inside the storage account"
  value       = azurerm_storage_container.lakehouse.name
}

output "adls_bronze_path" {
  description = "ABFSS path for the Bronze layer — paste this into STORAGE_ROOT in .env for production"
  value       = "abfss://lakehouse@${azurerm_storage_account.main.name}.dfs.core.windows.net/bronze"
}

output "databricks_workspace_url" {
  description = "Databricks workspace URL — open this in your browser to access the UI"
  value       = azurerm_databricks_workspace.main.workspace_url
}

output "key_vault_name" {
  description = "Name of the Azure Key Vault storing the storage account key"
  value       = azurerm_key_vault.main.name
}

output "sql_warehouse_http_path" {
  description = "HTTP path for the Serverless SQL Warehouse — paste into dbt connection profile"
  value       = databricks_sql_endpoint.main.jdbc_url
}
