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
  }
}

provider "azurerm" {
  features {}
}
