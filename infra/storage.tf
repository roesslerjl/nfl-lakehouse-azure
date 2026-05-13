# infra/storage.tf

# Storage account
# All Bronze, Silver, and Gold data lives here as files in containers.
resource "azurerm_storage_account" "main" {
  name                     = "${var.project_name}storage"  # must be globally unique, lowercase, no hyphens
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"  # Locally Redundant Storage — cheapest, sufficient for a dev project

  # This is what makes it ADLS Gen2 rather than plain Blob Storage.
  # Hierarchical namespace enables true directory semantics and Databricks compatibility.
  is_hns_enabled = true
}

# Container 
# All medallion layers (bronze/, silver/, gold/) live as paths inside this one container.
resource "azurerm_storage_container" "lakehouse" {
  name                  = "lakehouse"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"  # no public access (Databricks authenticates via Key Vault secret)
}
