# infra/variables.tf

# Variables definition to separate configuration from code.
# Declared here, actual values live in terraform.tfvars (gitignored).

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure tenant ID"
  type        = string
}

variable "resource_group_name" {
  description = "Name for the Azure Resource Group that contains all project resources"
  type        = string
  default     = "rg-nfl-lakehouse"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "southcentralus"
}

variable "project_name" {
  description = "Short identifier used to name all resources consistently (e.g. storage account, Databricks workspace)"
  type        = string
  default     = "nfllakehouse"
}

variable "catalog_name" {
  type    = string
  default = "nfl_lakehouse"   # Databricks recommended standard convention: {environment}.{team_name or domain_name}.{asset_name}
}
