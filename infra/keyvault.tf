# infra/keyvault.tf

# Key Vault
# Stores the storage account key and Databricks token so neither ever appears in code or environment variables.
# Databricks mounts ADLS Gen2 using the storage key retrieved from Key Vault at runtime.
resource "azurerm_key_vault" "main" {
  name                = "${var.project_name}-kv"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = var.tenant_id
  sku_name            = "standard"  # standard vs premium — premium adds HSM-backed keys, overkill here

  # Soft delete retains deleted secrets for 30 days before permanent removal.
  # Protects against accidental deletion of the storage key.
  soft_delete_retention_days = 30
}

# Grant your account permission to read/write secrets in this vault.
# Without this, even I myself can't access secrets by default.
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault_access_policy" "admin" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "Set", "List", "Delete"]
}

# Store the storage account key as a secret.
# Databricks will retrieve this at mount time instead of hardcoding credentials.
resource "azurerm_key_vault_secret" "storage_key" {
  name         = "storage-account-key"
  value        = azurerm_storage_account.main.primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.admin]
}
