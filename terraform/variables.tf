variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "asia-northeast1"
  description = "Default GCP Region"
}

variable "environment" {
  type        = string
  default     = "stg"
  description = "Environment name (stg or prod)"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Cloud SQL postgres app user password"
}

variable "cors_origins" {
  type        = string
  default     = "*"
  description = "Allowed origins for CORS (comma-separated, default is '*')"
}

variable "db_tier" {
  type        = string
  default     = "db-f1-micro"
  description = "Cloud SQL database instance tier (e.g., db-f1-micro, db-custom-1-3840)"
}

