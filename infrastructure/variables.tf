variable "app_name" {
  description = "Name of the app being deployed."
  default = "incremental-updater"
  type = string
}

variable "app_job_name" {
  description = "Name of the app job being deployed."
  default = "job-openalex-refresh"
  type = string
}

variable "container_registry_name" {
  description = "Name of the container registry where incremental updater images are pushed."
  type = string
}

variable "container_registry_resource_group_name" {
  description = "Name of the container registry resource group."
  type = string
}

variable "github_actions_service_principal_object_id" {
  description = "The Object ID of the Azure Service Principal used by GitHub Actions to deploy the Incremental Updater App and App Job."
  type = string
}

variable "environment" {
  description = "Environment for the Incremental Updater App and App Job, should be either development, staging or production."
  default     = "development"
  type = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
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

variable "environment_description" {
  description = "Description of the environment the incremental updater App and App Job is deployed to."
  default     = "warm"
  type        = string
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

variable "azure_auth_environment_id_development" {
  description = "The Azure authentication environment ID for the Incremental Updater App."
  default = null
  type = string
  validation {
    condition     = (
      (var.azure_auth_environment_id_development != null ? 1 : 0) +
      (var.azure_auth_environment_id_staging != null ? 1 : 0) +
      (var.azure_auth_environment_id_production != null ? 1 : 0)
    ) == 1
    error_message = "Exactly one azure_auth_environment_id variable must be set (non-null)."
  }
}
variable "azure_auth_environment_id_staging" {
  description = "The Azure authentication environment ID for the Incremental Updater App in staging."
  default = null
  type = string
}
variable "azure_auth_environment_id_production" {
  description = "The Azure authentication environment ID for the Incremental Updater App in production."
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

variable "storage_blob_container_development" {
  description = "The Storage Blob Container name for the Incremental Updater App in development."
  type = string
  default = null
  validation {
    condition     = (
      (var.storage_blob_container_development != null ? 1 : 0) +
      (var.storage_blob_container_staging != null ? 1 : 0) +
      (var.storage_blob_container_production != null ? 1 : 0)
    ) == 1
    error_message = "Exactly one storage_blob_container variable must be set (non-null)."
  }
}
variable "storage_blob_container_staging" {
  description = "The Storage Blob Container name for the Incremental Updater App in staging."
  type = string
  default = null
}
variable "storage_blob_container_production" {
  description = "The Storage Blob Container name for the Incremental Updater App in production."
  type = string
  default = null
}

variable "log_level" {
    description = "Log level for the Incremental Updater App."
    default     = "INFO"
    type       = string
}

variable "repository_endpoint_development" {
  description = "The Repository Endpoint for the development Incremental Updater App."
  default = null
  type = string
  validation {
    condition     = (
      (var.repository_endpoint_development != null ? 1 : 0) +
      (var.repository_endpoint_staging != null ? 1 : 0) +
      (var.repository_endpoint_production != null ? 1 : 0)
    ) == 1
    error_message = "Exactly one repository_endpoint variable must be set (non-null)."
  }
}
variable "repository_endpoint_staging" {
  description = "The Repository Endpoint for the Incremental Updater App in staging."
  default = null
  type = string
}
variable "repository_endpoint_production" {
  description = "The Repository Endpoint for the Incremental Updater App in production."
  default = null
  type = string
}

locals {
  azure_auth_environment_id_evaluated = (
    var.environment == "development" ? var.azure_auth_environment_id_development :
    var.environment == "staging" ? var.azure_auth_environment_id_staging :
    var.azure_auth_environment_id_production
  )
  storage_blob_container_id_evaluated = (
    var.environment == "development" ? var.storage_blob_container_development :
    var.environment == "staging" ? var.storage_blob_container_staging :
    var.storage_blob_container_production
  )
  repository_endpoint_id_evaluated = (
    var.environment == "development" ? var.repository_endpoint_development :
    var.environment == "staging" ? var.repository_endpoint_staging :
    var.repository_endpoint_production
  )
}
