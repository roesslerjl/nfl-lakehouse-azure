# infra/main.tf

# Define Terraform providers (cloud SDKs).
# azurerm (Azure resources) and databricks
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.0"
    }
    # Time is required for timeout requests
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
  }
}

# Azurerm provider authenticates using Azure CLI session (az login).
# No credentials in code, picked up from the CLI automatically.
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

# The Databricks provider is configured after the workspace exists.
# Points at the workspace URL that azurerm creates.
provider "databricks" {
  host = azurerm_databricks_workspace.main.workspace_url
}

# Resource Group: top-level container for all Azure resources in this project.
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}