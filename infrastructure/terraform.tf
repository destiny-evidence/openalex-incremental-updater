terraform {
  required_version = ">= 1.0"

  cloud {
    organization = "destiny-evidence"
    workspaces {
        project = "DESTINY"
        tags = ["incremental-updater"]
    }
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.47.0"
    }

    azuread = {
        source = "hashicorp/azuread"
        version = "3.3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {
}
