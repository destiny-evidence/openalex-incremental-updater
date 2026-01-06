data "azurerm_container_registry" "destiny_shared_infra" {
  name                = var.container_registry_name
  resource_group_name = var.container_registry_resource_group_name
}

data "azurerm_storage_account" "incremental_updater_storage_account" {
  name                = var.storage_blob_account
  resource_group_name = data.azurerm_container_registry.destiny_shared_infra.resource_group_name
}

data "azurerm_key_vault" "incremental_updater_key_vault" {
  name                = var.key_vault_name
  resource_group_name = data.azurerm_container_registry.destiny_shared_infra.resource_group_name
}

# If your application has already been deployed
# Use a data resource instead https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/resource_group
resource "azurerm_resource_group" "incremental_updater_resource_group" {
  name     = "rg-${var.app_name}-${var.environment}"
  location = var.region
  tags = {
    "Budget Code" = var.budget_code
    "Created by"  = var.owner_name
    "Owner"       = var.owner_email
    "Environment" = var.environment
    "Region"      = var.region_friendly_name
  }
}

resource "azurerm_role_assignment" "github_actions_sp_contributor_role" {
  scope                = azurerm_resource_group.incremental_updater_resource_group.id
  role_definition_name = "Contributor"
  principal_id         = var.github_actions_service_principal_object_id
}

resource "azurerm_network_security_group" "incremental_updater_nsg" {
  name                = "nsg-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
  tags = {
    "Created by"  = var.owner_name
    "Environment" = var.environment_description
    "Owner"       = var.owner_email
  }
}

resource "azurerm_virtual_network" "incremental_updater_vnet" {
  name                = "vnet-${var.app_name}-${var.environment}"
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
  address_space       = ["10.0.0.0/21"]

  tags = {
    "Created by"  = var.owner_name
    "Environment" = var.environment_description
    "Owner"       = var.owner_email
  }
}

resource "azurerm_subnet" "incremental_updater_subnet" {
  name                 = "subnet-${var.app_name}-${var.environment}"
  resource_group_name  = azurerm_resource_group.incremental_updater_resource_group.name
  virtual_network_name = azurerm_virtual_network.incremental_updater_vnet.name
  address_prefixes     = ["10.0.0.0/21"]

  delegation {
    name = "containerappenv"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/action"
      ]
    }
  }
}

resource "azurerm_subnet_network_security_group_association" "incremental_updater_subnet_nsg_association" {
  subnet_id                 = azurerm_subnet.incremental_updater_subnet.id
  network_security_group_id = azurerm_network_security_group.incremental_updater_nsg.id
}

# Create a user assigned identity for the incremental updater app and app job.
# This is the identity used when authenticating to other Azure services from within the container app and container app job
resource "azurerm_user_assigned_identity" "incremental_updater_user_assigned_identity" {
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  name                = "${var.app_name}-${var.environment}-identity"
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
}

resource "azurerm_role_assignment" "keyvault_secrets_user" {
  scope                = data.azurerm_key_vault.incremental_updater_key_vault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = data.azurerm_container_registry.destiny_shared_infra.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
}

resource "azurerm_role_assignment" "blob_contributor" {
  scope                = data.azurerm_storage_account.incremental_updater_storage_account.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
}

resource "azurerm_log_analytics_workspace" "incremental_updater_log_analytics_workspace" {
  name                = "log-analytics-updater-${var.environment}"
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  local_authentication_enabled = true
}

resource "azurerm_container_app_environment" "container_app_env" {
  location                 = azurerm_resource_group.incremental_updater_resource_group.location
  name                     = "destiny-incremental-updater-env"
  resource_group_name      = azurerm_resource_group.incremental_updater_resource_group.name
  infrastructure_subnet_id = azurerm_subnet.incremental_updater_subnet.id
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.incremental_updater_log_analytics_workspace.id
  tags = {
    "Budget Code" = var.budget_code
    "Created by"  = var.owner_name
    "Environment" = var.environment_description
    "Owner"       = var.owner_email
  }
}

resource "azurerm_container_app" "incremental_updater_app" {
  name                         = "app-${var.app_name}-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.container_app_env.id
  resource_group_name          = azurerm_resource_group.incremental_updater_resource_group.name
  revision_mode                = "Single"
  tags = {
    "Created by" = var.owner_name
    "Environment"  = var.environment_description
    "Owner"        = var.owner_email
    "Region"      = var.region_friendly_name
  }
  workload_profile_name = "Consumption"
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.id]
  }

  secret {
    name  = "openalex-api-key" #pragma: allowlist secret
    value = var.openalex_api_key
  }

  secret {
    name = "app-registration-secret" #pragma: allowlist secret
    value = var.app_registration_secret
  }

  ingress {
    allow_insecure_connections = false
    client_certificate_mode    = "ignore"
    external_enabled           = false
    target_port                = 8000
    transport                  = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  template {
    max_replicas                     = 1
    min_replicas                     = 0
    revision_suffix                  = ""
    termination_grace_period_seconds = 0
    container {
      cpu    = 4
      memory = "8Gi"
      name   = "${var.app_name}-${var.environment}"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      env {
        name        = "OPENALEX_API_KEY"
        secret_name = "openalex-api-key" #pragma: allowlist secret
      }
      env {
        name        = "USER_EMAIL"
        value       = var.owner_email
      }
      env {
        name        = "CORS_ORIGINS"
        value       = join(",", var.cors_origins)
      }
      env {
        name        = "AZURE_AUTH_ENVIRONMENT_ID"
        value       = local.azure_auth_environment_id_evaluated
      }
      env {
        name        = "APP_REGISTRATION_APP_ID"
        value       = var.app_registration_app_id
      }
      env {
        name        = "APP_REGISTRATION_SECRET"
        secret_name = "app-registration-secret" #pragma: allowlist secret
      }
      env {
        name        = "TENANT_ID"
        value       = var.tenant_id
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
      }
      env {
        name  = "AZURE_MANAGED_IDENTITY_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
      }
      env {
        name        = "STORAGE_BLOB_ACCOUNT"
        value       = var.storage_blob_account
      }
      env {
        name        = "STORAGE_BLOB_CONTAINER"
        value       = local.storage_blob_container_id_evaluated
      }
      env {
        name        = "LOG_LEVEL"
        value       = var.log_level
      }
      readiness_probe {
        failure_count_threshold = 3
        host                    = ""
        initial_delay           = 0
        interval_seconds        = 10
        path                    = "/health-check/"
        port                    = 8000
        success_count_threshold = 1
        timeout                 = 5
        transport               = "HTTP"
      }
      startup_probe {
        failure_count_threshold = 3
        host                    = ""
        initial_delay           = 0
        interval_seconds        = 10
        path                    = "/health-check/"
        port                    = 8000
        timeout                 = 5
        transport               = "HTTP"
      }
    }
    http_scale_rule {
      concurrent_requests = "10"
      name                = "http-scaler"
    }
  }
}

resource "azurerm_container_app_job" "incremental_updater_app_job" {
  name                         = "${var.app_job_name}-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.container_app_env.id
  resource_group_name          = azurerm_resource_group.incremental_updater_resource_group.name
  location                     = azurerm_resource_group.incremental_updater_resource_group.location
  replica_retry_limit          = 3
  replica_timeout_in_seconds   = 36000
  tags = {
    "Created by" = var.owner_name
    "Environment"  = var.environment_description
    "Owner"       = var.owner_email
    "Region"       = var.region_friendly_name
  }
  secret {
    name  = "storage-blob-account-key" #pragma: allowlist secret
    value = var.storage_blob_account_key
  }
  workload_profile_name = "Consumption"
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.id]
  }
  schedule_trigger_config {
    cron_expression          = "0 8 * * *"
    parallelism              = 1
    replica_completion_count = 1
  }
  template {
    container {
      cpu    = 0.5
      memory = "1Gi"
      name   = "${var.app_job_name}-${var.environment}"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      env {
        name        = "API_ENDPOINT"
        value       = "https://${azurerm_container_app.incremental_updater_app.ingress[0].fqdn}"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
      }
      env {
        name = "AZURE_MANAGED_IDENTITY_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
      }
      env {
        name        = "STORAGE_BLOB_ACCOUNT"
        value       = var.storage_blob_account
      }
      env {
        name        = "STORAGE_BLOB_CONTAINER"
        value       = local.storage_blob_container_id_evaluated
      }
      env {
        name        = "TOKEN_ENDPOINT"
        value       = "https://${azurerm_container_app.incremental_updater_app.ingress[0].fqdn}/api/v1/auth_token"
      }
      env {
        name        = "STORAGE_BLOB_ACCOUNT_KEY"
        secret_name = "storage-blob-account-key" #pragma: allowlist secret
      }
      env {
        name        = "REPOSITORY_ENDPOINT"
        value       = local.repository_endpoint_id_evaluated
      }
      env {
        name        = "request_timeout"
        value       = "18000"
      }
      env {
        name        = "polling_interval"
        value       = "5.0"
      }
      liveness_probe {
        failure_count_threshold = 3
        host                    = ""
        initial_delay           = 30
        interval_seconds        = 240
        path                    = "/health/"
        port                    = 8080
        timeout                 = 5
        transport               = "HTTP"
      }
      readiness_probe {
        failure_count_threshold = 3
        host                    = ""
        initial_delay           = 0
        interval_seconds        = 60
        path                    = "/health/"
        port                    = 8080
        success_count_threshold = 1
        timeout                 = 5
        transport               = "HTTP"
      }
      startup_probe {
        failure_count_threshold = 3
        host                    = ""
        initial_delay           = 0
        interval_seconds        = 60
        path                    = "/health/"
        port                    = 8080
        timeout                 = 5
        transport               = "HTTP"
      }
    }
  }
}
