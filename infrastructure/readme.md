# OpenAlex Incremental Updater Infrastructure

Infrastructure for deploying the OpenAlex Incremental Updater infrastructure into an Azure tenant

## Setup

You will need to have access to the `destiny-evidence` terraform cloud (TFC) organisation. Then to run terraform plans, you can do the following

```sh
terraform login
```

Once you're logged in to terraform cloud, you can initialise terraform

```sh
terraform init
```

We identify a set of workspaces that this terraform can be applied to via tagging those workspaces in with `incremental-updater` in TFC. When you initialise terraform, you'll need to select one of those workspaces to plan/apply against.

Each of the workspaces represents a deployment of `incremental-updater` called an environment. If you're developing new infrastructure, you should select `incremental-updater-staging`\* or create your own workspace/environment to work in (see below). You **are not** blocked from applying changes to both `staging` and `production` environments, so go carefully.

\*currently the only non-production environment in which to test, though functionality to add your own test environment is coming soon.

To show available workspaces, run

```sh
terraform workspace list
```

to change workspace, run

```sh
terraform workspace select <WORKSPACE_NAME>
```

To plan infrastructure changes against a workspace and have them output to a file, run

```sh
terraform plan -out main.tfplan
```

To apply infrastructure changes to a workspace, run

```sh
terraform apply "main.tfplan"
```

## Creating a new deployment of OpenAlex Incremental Updater

This guide should be followed if you're setting up a new deployment of incremental updater from scratch. If you're not sure if you should be doing this, you probably shouldn't be!

You will need the following

- Access to the `destiny-evidence` TFC organisation
- An environment name for your deployment, this should be one of `development`, `staging`, `production` and is probably `staging`
- Access to the `Destiny Research and Development Subscription` subscription within the `University College London` Azure tenant

### Create your Terraform Cloud workspace

Create a new workspace in the `destiny-evidence` organisation in TFC with the following name, project, and tag

- Name = "incremental-updater-[YOUR ENVIRONMENT NAME]
- Project = "DESTINY"
- Tag = "incremental-updater"

This will allow TFC to link the terraform defined here to your TFC workspace when you run `terraform init`.

Apply the `Azure UCL Directory Authentication` and `Incremental Updater GitHub Actions` variable sets for GitHub-Actions-powered deployments and Azure tenant authentication to your workspace.

Configure all necessary inputs as variables, these are listed in the Terraform Docs below. You can pull the majority of these from other workspaces, but don't forget your unique environment name. Additionally, for temporary workspaces set yourself in the `owner` and `created_by` variables.

Configure your workspace as either a CLI workspace, or as a VCS workspace tied to your branch name.

You'll need to make sure that the Azure Enterprise Application that is references by object ID in the `TFC_AZURE_RUN_CLIENT_ID` variable has been granted the `Infrastructure Automation` role in the `Destiny Research and Development Subscription` subscription. This allows for the creation and assignment of necessary roles for the incremental updater infrastructure.

### Deploy out the container app image

Before you can use the deployment of openalex-incremental-updater, you will need to deploy out the correct image to the container app. You can manually deploy to the staging environment by using the GitHub Actions workflow dispatch from any branch with the actions

- Deploy staging openalex-incremental-updater to Azure Container Apps.
- Deploy staging refresh-requester to Azure Container Apps.

these also automatically run on a successful PR merge to the main branch. This will build an image from the head of the selected branch, tag it with the commit hash, push it to the Azure container registry and deploy it in the relevant environment. You must set GitHub environment-specific variables in order for this to work. Do this by going to `Settings` -> `Environments` -> `staging` (or your custom environment name) and adding the following variables

| Name                           | Value                                                                             |
| ------------------------------ | --------------------------------------------------------------------------------- |
| CONTAINER_APP_JOB_NAME_STAGING | The name of the Container App Job                                                 |
| CONTAINER_APP_NAME_STAGING     | The name of the Container App                                                     |
| RESOURCE_GROUP_STAGING         | The name of the resource group containing the Container App and Container App Job |

See also `deploy-staging-openalex-incremental-updater.yml` and `deploy-staging-refresh-requester.yml` in `.github/workflows` for more details on how these variables are used.

A simialr set of variables exists for the production environment, though this is deployed by promoting a successful staging deployment.

### After The First Apply

You will need to modify the container registry and authentication information for both the Container App and Container App Job. These should both be set to the following configuration:

- `Image source` set to `Azure Container Registry`
- `Authentication` set to `Managed Identity`
- `Identity` set to `incremental-updater-ENV-identity` (where `ENV` is `development`,`staging` or `production`)
- `Subscription` set to the relevant Azure subscription containing the container registry
- `Registry` set to the correct path for the container registry, usually `acr-name.azurecr.io`
- `Image` set to the relevant image. For this package, that's either `openalex-incremental-updater` or `refresh-requester` for the Container App and Container App Job, respectively
- `Image tag` set to the latest available shortened commit hash in the GitHub repository.

Once these are set, future PR merges will automatically deploy to staging environments as described above. Production deployments are triggered by manual promotion of staging deployments, but that's entirely via GitHub Actions.

### Cleaning up

We can also destroy things!

Removing the lifecycle protection block of your database in `main.tf` if necessary.

Then, queue up a destroy

```sh
terraform apply --destroy
```

You can also run

```sh
terraform destroy
```

for a little more ceremony, where you will be asked in a serious tone to confirm the destroy action with a `yes`.

Delete your TFC workspace. You're all done!

### Storage redundancy, backups and recovery process

#### Storage Account

The storage account uses Locally-Redundant Storage (LRS), which means data is replicated three times within a single data center in the primary region. It does not replicate across availability zones.

As the data is transient, no further backup or recovery processes are in place. If data in the storage account is lost, it will need to be regenerated by re-running the processes that created it.

### Generating Terraform Docs

Docs generated with [terraform-docs](github.com/terraform-docs/terraform-docs). Run the following from this directory.

```sh
terraform-docs markdown --output-file readme.md .
```

<!-- BEGIN_TF_DOCS -->

## Requirements

| Name                                                                     | Version |
| ------------------------------------------------------------------------ | ------- |
| <a name="requirement_terraform"></a> [terraform](#requirement_terraform) | >= 1.0  |
| <a name="requirement_azuread"></a> [azuread](#requirement_azuread)       | 3.3.0   |
| <a name="requirement_azurerm"></a> [azurerm](#requirement_azurerm)       | 4.47.0  |

## Providers

| Name                                                         | Version |
| ------------------------------------------------------------ | ------- |
| <a name="provider_azurerm"></a> [azurerm](#provider_azurerm) | 4.47.0  |

## Modules

| Name                                                                                                                                   | Source                                                | Version |
| -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------- |
| <a name="module_container_app_incremental_updater"></a> [container_app_incremental_updater](#module_container_app_incremental_updater) | app.terraform.io/destiny-evidence/container-app/azure | 1.8.2   |

## Resources

| Name                                                                                                                                                                                                                      | Type        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| [azurerm_container_app_job.incremental_updater_app_job](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/container_app_job)                                                                | resource    |
| [azurerm_network_security_group.incremental_updater_nsg](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/network_security_group)                                                          | resource    |
| [azurerm_resource_group.incremental_updater_resource_group](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/resource_group)                                                               | resource    |
| [azurerm_role_assignment.blob_contributor](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/role_assignment)                                                                               | resource    |
| [azurerm_role_assignment.github_actions_sp_contributor_role](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/role_assignment)                                                             | resource    |
| [azurerm_role_assignment.keyvault_secrets_user](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/role_assignment)                                                                          | resource    |
| [azurerm_subnet.incremental_updater_subnet](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/subnet)                                                                                       | resource    |
| [azurerm_subnet_network_security_group_association.incremental_updater_subnet_nsg_association](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/subnet_network_security_group_association) | resource    |
| [azurerm_user_assigned_identity.incremental_updater_user_assigned_identity](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/user_assigned_identity)                                       | resource    |
| [azurerm_virtual_network.incremental_updater_vnet](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/resources/virtual_network)                                                                       | resource    |
| [azurerm_container_registry.destiny_shared_infra](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/data-sources/container_registry)                                                                  | data source |
| [azurerm_key_vault.incremental_updater_key_vault](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/data-sources/key_vault)                                                                           | data source |
| [azurerm_storage_account.incremental_updater_storage_account](https://registry.terraform.io/providers/hashicorp/azurerm/4.47.0/docs/data-sources/storage_account)                                                         | data source |

## Inputs

| Name                                                                                                                                                            | Description                                                                                                                       | Type           | Default                                         | Required |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------- | ----------------------------------------------- | :------: |
| <a name="input_app_registration_app_id"></a> [app_registration_app_id](#input_app_registration_app_id)                                                          | The App Registration Application ID for the Incremental Updater App.                                                              | `string`       | n/a                                             |   yes    |
| <a name="input_app_registration_secret"></a> [app_registration_secret](#input_app_registration_secret)                                                          | The App Registration Secret for the Incremental Updater App.                                                                      | `string`       | n/a                                             |   yes    |
| <a name="input_azure_auth_environment_id"></a> [azure_auth_environment_id](#input_azure_auth_environment_id)                                                    | The Azure authentication environment ID for the Incremental Updater App, either development, staging or production.               | `string`       | `null`                                          |    no    |
| <a name="input_budget_code"></a> [budget_code](#input_budget_code)                                                                                              | Budget code for the incremental updater app.                                                                                      | `string`       | n/a                                             |   yes    |
| <a name="input_container_registry_name"></a> [container_registry_name](#input_container_registry_name)                                                          | Name of the container registry where incremental updater images are pushed.                                                       | `string`       | n/a                                             |   yes    |
| <a name="input_cors_origins"></a> [cors_origins](#input_cors_origins)                                                                                           | List of allowed CORS origins for the Incremental Updater App.                                                                     | `list(string)` | <pre>[<br/> "http://localhost:3000"<br/>]</pre> |    no    |
| <a name="input_deployment_environment"></a> [deployment_environment](#input_deployment_environment)                                                             | Environment for the Incremental Updater App and App Job, should be either development, staging or production.                     | `string`       | `"development"`                                 |    no    |
| <a name="input_destiny_shared_infra_resource_group_name"></a> [destiny_shared_infra_resource_group_name](#input_destiny_shared_infra_resource_group_name)       | Name of the Destiny Shared Infrastructure resource group.                                                                         | `string`       | n/a                                             |   yes    |
| <a name="input_environment_description"></a> [environment_description](#input_environment_description)                                                          | Description of the environment the incremental updater App and App Job is deployed to.                                            | `string`       | `"warm"`                                        |    no    |
| <a name="input_github_actions_service_principal_object_id"></a> [github_actions_service_principal_object_id](#input_github_actions_service_principal_object_id) | The Object ID of the Azure Service Principal used by GitHub Actions to deploy the Incremental Updater App and App Job.            | `string`       | n/a                                             |   yes    |
| <a name="input_key_vault_name"></a> [key_vault_name](#input_key_vault_name)                                                                                     | The Key Vault name for the Incremental Updater App.                                                                               | `string`       | n/a                                             |   yes    |
| <a name="input_log_level"></a> [log_level](#input_log_level)                                                                                                    | Log level for the Incremental Updater App.                                                                                        | `string`       | `"INFO"`                                        |    no    |
| <a name="input_openalex_api_key"></a> [openalex_api_key](#input_openalex_api_key)                                                                               | API key for OpenAlex.                                                                                                             | `string`       | n/a                                             |   yes    |
| <a name="input_owner_email"></a> [owner_email](#input_owner_email)                                                                                              | Email of the owner of the incremental updater app.                                                                                | `string`       | n/a                                             |   yes    |
| <a name="input_owner_name"></a> [owner_name](#input_owner_name)                                                                                                 | Name of the owner of the incremental updater app.                                                                                 | `string`       | n/a                                             |   yes    |
| <a name="input_region"></a> [region](#input_region)                                                                                                             | Azure region the App and App Job is deployed to.                                                                                  | `string`       | `"swedencentral"`                               |    no    |
| <a name="input_region_friendly_name"></a> [region_friendly_name](#input_region_friendly_name)                                                                   | Friendly name of the region the incremental updater App and App Job is deployed to.                                               | `string`       | `"Sweden Central"`                              |    no    |
| <a name="input_repository_endpoint"></a> [repository_endpoint](#input_repository_endpoint)                                                                      | The DESTINY Repository Endpoint URL for the development Incremental Updater App. Environment-specific variable.                   | `string`       | `null`                                          |    no    |
| <a name="input_storage_blob_account"></a> [storage_blob_account](#input_storage_blob_account)                                                                   | The Storage Blob Account name for the Incremental Updater App.                                                                    | `string`       | n/a                                             |   yes    |
| <a name="input_storage_blob_account_key"></a> [storage_blob_account_key](#input_storage_blob_account_key)                                                       | The Storage Blob Account Key for the Incremental Updater App.                                                                     | `string`       | n/a                                             |   yes    |
| <a name="input_storage_blob_container"></a> [storage_blob_container](#input_storage_blob_container)                                                             | The Storage Blob Container name for the Incremental Updater App. Chosed based on environment: development, staging or production. | `string`       | `null`                                          |    no    |
| <a name="input_tenant_id"></a> [tenant_id](#input_tenant_id)                                                                                                    | The Tenant ID for the Incremental Updater App.                                                                                    | `string`       | n/a                                             |   yes    |

## Outputs

No outputs.

<!-- END_TF_DOCS -->
