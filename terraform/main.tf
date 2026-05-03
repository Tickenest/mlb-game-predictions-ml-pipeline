terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket  = "mlb-predictions-terraform-state"
    key     = "mlb-predictions/terraform.tfstate"
    region  = "us-east-1"
    profile = "mlb-predictions-dev"
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "mlb-predictions-dev"
}

resource "random_id" "suffix" {
  byte_length = 4
}