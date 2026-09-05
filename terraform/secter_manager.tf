resource "aws_secretsmanager_secret" "groq_api_key" {
  name = "groq-api-key"
}

resource "aws_secretsmanager_secret_version" "groq_api_key" {
  secret_id     = aws_secretsmanager_secret.groq_api_key.id
  secret_string = var.GROQ_API_KEY
}
