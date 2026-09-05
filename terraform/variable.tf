variable "region" {
  description = "AWS region for the infrastructure"
  type        = string
  default     = "eu-north-1"
}

variable "GROQ_API_KEY" {
  description = "Groq API"
  type        = string
}

variable "GROQ_MODEL" {
  type        = string
}

variable "HOST" {
  type        = string
}

variable "PORT" {
  type        = number
}