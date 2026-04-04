terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
    technitium = {
      source  = "darkhonor/technitium"
      version = "~> 1.1"
    }
  }

  # State path is overridden via TF_CLI_ARGS_init or -backend-config on the runner.
  # Locally the default terraform.tfstate should be used.
  backend "local" {}
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "technitium" {
  alias           = "aah"
  server_url      = var.technitium_aah_server_url
  api_token       = var.technitium_aah_api_token
  skip_tls_verify = true
}

# Add additional site providers here as Technitium instances are deployed:
#
# provider "technitium" {
#   alias           = "lcy"
#   server_url      = var.technitium_lcy_server_url
#   api_token       = var.technitium_lcy_api_token
#   skip_tls_verify = true
# }
