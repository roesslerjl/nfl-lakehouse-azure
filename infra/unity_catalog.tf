# infra/unity_catalog.tf
# Root of the UC storage chain. UC accesses ADLS as THIS identity —
# never as the querying user. 

resource "azurerm_databricks_access_connector" "uc" {
  name                = "ac-nfl-lakehouse-uc"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  identity {
    type = "SystemAssigned"
  }
}

# Storage Blon contributor role which will be assigne dto the Access Connector to be able to reach into the ADLS Gen2
resource "azurerm_role_assignment" "uc_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.uc.identity[0].principal_id
}

data "databricks_current_user" "me" {}

resource "azurerm_storage_container" "uc_managed" {
  name                  = "uc-managed"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

# RBAC propagation: UC validates the credential on create and will 403
# if the role assignment hasn't landed yet.
resource "time_sleep" "rbac_propagation" {
  depends_on      = [azurerm_role_assignment.uc_blob]
  create_duration = "60s"
}

resource "databricks_storage_credential" "uc" {
  name    = "sc-nfl-lakehouse"
  comment = "Managed identity for nfl-lakehouse UC storage"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.uc.id
  }

  depends_on = [time_sleep.rbac_propagation]
}

resource "databricks_external_location" "uc_managed" {
  name            = "el-nfl-lakehouse-managed"
  url             = "abfss://${azurerm_storage_container.uc_managed.name}@${azurerm_storage_account.main.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.uc.name
  comment         = "Managed location root for the nfl catalog"
}

# Without CREATE_MANAGED_STORAGE, the catalog below fails with an error
# that reads like an ADLS problem and isn't.
resource "databricks_grants" "uc_managed" {
  external_location = databricks_external_location.uc_managed.id

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["CREATE_MANAGED_STORAGE", "CREATE_EXTERNAL_TABLE", "READ_FILES", "WRITE_FILES"]
  }
}

resource "databricks_catalog" "nfl" {
  name          = var.catalog_name
  storage_root  = databricks_external_location.uc_managed.url
  comment       = "NFL Analytics Lakehouse — managed location on ${azurerm_storage_account.main.name}"
  force_destroy = true
  isolation_mode = "ISOLATED"

  depends_on = [databricks_grants.uc_managed]
}

# Default isolation is OPEN , visible to every workspace on the metastore.
# ISOLATED + explicit binding is required to restrict visibility across workspaces
resource "databricks_workspace_binding" "nfl" {
  securable_name = databricks_catalog.nfl.name
  securable_type = "catalog"
  workspace_id   = azurerm_databricks_workspace.main.workspace_id
  binding_type   = "BINDING_TYPE_READ_WRITE"
}

resource "databricks_schema" "layers" {
  for_each      = toset(["bronze", "silver", "gold"])
  catalog_name  = databricks_catalog.nfl.name
  name          = each.key
  force_destroy = true
}