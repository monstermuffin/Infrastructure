terraform {
  cloud {
    organization = "muffn_io"

    workspaces {
      name = "infra-main"
    }
  }

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.106"
    }
    technitium = {
      source  = "darkhonor/technitium"
      version = "~> 1.1"
    }
    kenske-technitium = {
      source  = "kenske/technitium"
      version = "~> 0.2.2"
    }
  }

}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "proxmox" {
  endpoint  = var.proxmox_virtual_environment_endpoint
  username  = var.proxmox_virtual_environment_username
  password  = var.proxmox_virtual_environment_password
  api_token = var.proxmox_virtual_environment_api_token
  insecure  = var.proxmox_virtual_environment_insecure

  dynamic "ssh" {
    for_each = (
      var.proxmox_virtual_environment_ssh_agent ||
      var.proxmox_virtual_environment_ssh_password != null ||
      var.proxmox_virtual_environment_ssh_private_key != null ||
      var.proxmox_virtual_environment_password != null
    ) ? [1] : []

    content {
      agent       = var.proxmox_virtual_environment_ssh_agent
      password    = try(coalesce(var.proxmox_virtual_environment_ssh_password, var.proxmox_virtual_environment_password), null)
      private_key = var.proxmox_virtual_environment_ssh_private_key
      username    = coalesce(var.proxmox_virtual_environment_ssh_username, var.proxmox_virtual_environment_username)

      dynamic "node" {
        for_each = local.proxmox_provider_ssh_nodes
        content {
          address = node.value.address
          name    = node.value.name
        }
      }
    }
  }
}

provider "technitium" {
  alias           = "aah"
  server_url      = var.technitium_aah_server_url
  api_token       = var.technitium_aah_api_token
  skip_tls_verify = true
}
provider "technitium" {
  alias           = "lcy"
  server_url      = var.technitium_lcy_server_url
  api_token       = var.technitium_lcy_api_token
  skip_tls_verify = true
}

provider "kenske-technitium" {
  alias = "aah"
  host  = format("%s:5380", trimsuffix(replace(var.technitium_aah_server_url, "https://", "http://"), "/"))
  token = var.technitium_aah_api_token
}

provider "kenske-technitium" {
  alias = "lcy"
  host  = format("%s:5380", trimsuffix(replace(var.technitium_lcy_server_url, "https://", "http://"), "/"))
  token = var.technitium_lcy_api_token
}
