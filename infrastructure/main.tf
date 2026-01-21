data "azurerm_container_registry" "destiny_shared_infra" {
  name                = var.container_registry_name
  resource_group_name = var.destiny_shared_infra_resource_group_name
}

data "azurerm_storage_account" "incremental_updater_storage_account" {
  name                = var.storage_blob_account
  resource_group_name = var.destiny_shared_infra_resource_group_name
}

data "azurerm_key_vault" "incremental_updater_key_vault" {
  name                = var.key_vault_name
  resource_group_name = var.destiny_shared_infra_resource_group_name
}

# If your application has already been deployed
# Use a data resource instead https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/resource_group
resource "azurerm_resource_group" "incremental_updater_resource_group" {
  name     = "rg-${local.app_name}-${var.deployment_environment}"
  location = var.region
  tags = {
    "Budget Code" = var.budget_code
    "Created by"  = var.owner_name
    "Owner"       = var.owner_email
    "Environment" = var.deployment_environment
    "Region"      = var.region_friendly_name
  }
}

resource "azurerm_role_assignment" "github_actions_sp_contributor_role" {
  scope                = azurerm_resource_group.incremental_updater_resource_group.id
  role_definition_name = "Contributor"
  principal_id         = var.github_actions_service_principal_object_id
}

resource "azurerm_network_security_group" "incremental_updater_nsg" {
  name                = "nsg-${local.app_name}-${var.deployment_environment}"
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
  tags = {
    "Created by"  = var.owner_name
    "Environment" = var.environment_description
    "Owner"       = var.owner_email
  }
}

resource "azurerm_virtual_network" "incremental_updater_vnet" {
  name                = "vnet-${local.app_name}-${var.deployment_environment}"
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
  name                 = "subnet-${local.app_name}-${var.deployment_environment}"
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

resource "azurerm_user_assigned_identity" "incremental_updater_user_assigned_identity" {
  location            = azurerm_resource_group.incremental_updater_resource_group.location
  name                = "${local.app_name}-${var.deployment_environment}-identity"
  resource_group_name = azurerm_resource_group.incremental_updater_resource_group.name
}

resource "azurerm_role_assignment" "keyvault_secrets_user" {
  scope                = data.azurerm_key_vault.incremental_updater_key_vault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
}

resource "azurerm_role_assignment" "blob_contributor" {
  scope                = data.azurerm_storage_account.incremental_updater_storage_account.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
}

module "container_app_incremental_updater" {
  source                          = "app.terraform.io/destiny-evidence/container-app/azure"
  version                         = "1.8.2"
  app_name                        = local.app_name
  environment                     = var.deployment_environment
  container_registry_id           = data.azurerm_container_registry.destiny_shared_infra.id
  container_registry_login_server = data.azurerm_container_registry.destiny_shared_infra.login_server
  resource_group_name             = azurerm_resource_group.incremental_updater_resource_group.name
  region                          = azurerm_resource_group.incremental_updater_resource_group.location
  infrastructure_subnet_id        = azurerm_subnet.incremental_updater_subnet.id
  cpu = 4
  memory = "8Gi"
  max_replicas = 1
  min_replicas = 0

  # The necessaary `AZURE_CLIENT_ID` environment variable is set by the container app module.
  env_vars = [
    {
        name        = "OPENALEX_API_KEY"
        secret_name = "openalex-api-key" #pragma: allowlist secret
    },
    {
        name        = "USER_EMAIL"
        value       = var.owner_email
    },
    {
        name        = "CORS_ORIGINS"
        value       = join(",", var.cors_origins)
    },
    {
        name        = "AZURE_AUTH_ENVIRONMENT_ID"
        value       = var.azure_auth_environment_id
    },
    {
        name        = "APP_REGISTRATION_APP_ID"
        value       = var.app_registration_app_id
    },
    {
        name        = "APP_REGISTRATION_SECRET"
        secret_name = "app-registration-secret" #pragma: allowlist secret
    },
    {
        name        = "TENANT_ID"
        value       = var.tenant_id
    },
    {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
    },
    {
        name  = "AZURE_MANAGED_IDENTITY_CLIENT_ID"
        value = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
    },
    {
        name        = "STORAGE_BLOB_ACCOUNT"
        value       = var.storage_blob_account
    },
    {
        name        = "STORAGE_BLOB_CONTAINER"
        value       = var.storage_blob_container
    },
    {
        name        = "LOG_LEVEL"
        value       = var.log_level
    }
  ]

  secrets = [
    {
    name  = "openalex-api-key" #pragma: allowlist secret
    value = var.openalex_api_key
    },
    {
    name = "app-registration-secret" #pragma: allowlist secret
    value = var.app_registration_secret
    }
  ]

  # Ingress changes will be ignored to avoid messing up manual custom domain config.
  # See https://github.com/hashicorp/terraform-provider-azurerm/issues/21866#issuecomment-1755381572.
  ingress = {
    allow_insecure_connections = false
    external_enabled           = false
    target_port                = 8000
    transport                  = "auto"
    traffic_weight = {
      latest_revision = true
      percentage      = 100
    }
  }

  readiness_probe = {
    failure_count_threshold = 3
    initial_delay           = 0
    interval_seconds        = 10
    path                    = "/health-check/"
    port                    = 8000
    success_count_threshold = 1
    timeout                 = 5
    transport               = "HTTP"
  }
  startup_probe = {
    failure_count_threshold = 3
    initial_delay           = 0
    interval_seconds        = 10
    path                    = "/health-check/"
    port                    = 8000
    timeout                 = 5
    transport               = "HTTP"
  }

  http_scale_rules = [
    {
      name               = "http-scaler"
      concurrent_requests = "10"
    }
  ]

  tags = {
    "Budget Code" = var.budget_code
    "Created by"  = var.owner_name
    "Owner"       = var.owner_email
    "Environment" = var.deployment_environment
    "Region"      = var.region_friendly_name
  }

  identity = {
    id           = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.id
    principal_id = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.principal_id
    client_id    = azurerm_user_assigned_identity.incremental_updater_user_assigned_identity.client_id
  }
}

resource "azurerm_container_app_job" "incremental_updater_app_job" {
  name                         = "${local.app_job_name}-${var.deployment_environment}"
  container_app_environment_id = module.container_app_incremental_updater.container_app_env_id
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
      name   = "${local.app_job_name}-${var.deployment_environment}"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      env {
        name        = "API_ENDPOINT"
        value       = "https://${module.container_app_incremental_updater.container_app_fqdn}"
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
        value       = var.storage_blob_container
      }
      env {
        name        = "TOKEN_ENDPOINT"
        value       = "https://${module.container_app_incremental_updater.container_app_fqdn}/api/v1/auth_token"
      }
      env {
        name        = "STORAGE_BLOB_ACCOUNT_KEY"
        secret_name = "storage-blob-account-key" #pragma: allowlist secret
      }
      env {
        name        = "REPOSITORY_ENDPOINT"
        value       = var.repository_endpoint
      }
      env {
        name        = "request_timeout"
        value       = "18000"
      }
      env {
        name        = "polling_interval"
        value       = "5.0"
      }
    }
  }
}
