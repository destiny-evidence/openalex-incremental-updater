variable "container_registry_name" {
  description = "Name of the container registry where incremental updater images are pushed."
  type = string
}

variable "destiny_shared_infra_resource_group_name" {
  description = "Name of the Destiny Shared Infrastructure resource group."
  type = string
}

variable "github_actions_service_principal_object_id" {
  description = "The Object ID of the Azure Service Principal used by GitHub Actions to deploy the Incremental Updater App and App Job."
  type = string
}

variable "deployment_environment" {
  description = "Environment for the Incremental Updater App and App Job, should be either development, staging or production."
  default     = "development"
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.deployment_environment)
    error_message = "Environment must be one of 'development', 'staging' or 'production'."
  }
}

variable "owner_name" {
  description = "Name of the owner of the incremental updater app."
  type = string
}

variable "budget_code" {
  description = "Budget code for the incremental updater app."
  type = string
  sensitive = true
}

variable "owner_email" {
  description = "Email of the owner of the incremental updater app."
  type = string
}

variable "region" {
  description = "Azure region the App and App Job is deployed to."
  default     = "swedencentral"
  type = string
}

variable "region_friendly_name" {
  description = "Friendly name of the region the incremental updater App and App Job is deployed to."
  default     = "Sweden Central"
  type = string
}

variable "cors_origins" {
    description = "List of allowed CORS origins for the Incremental Updater App."
    type        = list(string)
    default     = ["http://localhost:3000"]
}

variable "openalex_api_key" {
  description = "API key for OpenAlex."
  type = string
  sensitive   = true
}

variable "azure_auth_environment_id" {
  description = "The Azure authentication environment ID for the Incremental Updater App, either development, staging or production."
  default = null
  type = string
}

variable "app_registration_app_id" {
  description = "The App Registration Application ID for the Incremental Updater App."
  type = string
}

variable "app_registration_secret" {
  description = "The App Registration Secret for the Incremental Updater App."
  type = string
  sensitive   = true
}

variable "key_vault_name" {
  description = "The Key Vault name for the Incremental Updater App."
  type = string
  sensitive = true
}


variable "tenant_id" {
  description = "The Tenant ID for the Incremental Updater App."
  type = string
}

variable "storage_blob_account" {
  description = "The Storage Blob Account name for the Incremental Updater App."
  type = string
}

variable "storage_blob_account_key" {
  description = "The Storage Blob Account Key for the Incremental Updater App."
  type = string
  sensitive   = true
}

variable "storage_blob_container" {
  description = "The Storage Blob Container name for the Incremental Updater App. Chosed based on environment: development, staging or production."
  type = string
  default = null
}

variable "log_level" {
    description = "Log level for the Incremental Updater App."
    default     = "INFO"
    type       = string
}

variable "repository_endpoint" {
  description = "The DESTINY Repository Endpoint URL for the development Incremental Updater App. Environment-specific variable."
  default = null
  type = string
}

locals {
  app_name = "incremental-updater"
  app_job_name = "job-openalex-refresh"
  minimum_resource_tags = {
    "Created by"  = var.owner_name
    "Environment" = var.deployment_environment
    "Owner"       = var.owner_email
    "Region" = var.region_friendly_name
  }
  extended_resource_tags = merge(local.minimum_resource_tags, {
    "Budget code" = var.budget_code
  })
}
