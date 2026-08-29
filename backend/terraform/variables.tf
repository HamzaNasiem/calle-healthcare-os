variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "clinic_id" {
  description = "Unique identifier for the clinic (e.g., 'clinic-001')"
  type        = string
}

variable "db_username" {
  description = "Master username for PostgreSQL databases"
  type        = string
  default     = "dev_user"
}

variable "db_password" {
  description = "Master password for PostgreSQL databases"
  type        = string
  sensitive   = true
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository containing the API image"
  type        = string
}
