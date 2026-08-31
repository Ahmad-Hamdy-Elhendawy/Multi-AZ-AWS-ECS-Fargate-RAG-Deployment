###### S3 - ALB ACCESS LOGS ######

resource "aws_s3_bucket" "lb_logs" {
  bucket = "lb-logs-please-be-uniqe-123412352"
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "lb-logs"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket_policy" "lb_logs_policy" {
  bucket = aws_s3_bucket.lb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowALBLogDelivery"
        Effect = "Allow"

        Principal = {
          Service = "logdelivery.elasticloadbalancing.amazonaws.com"
        }

        Action = "s3:PutObject"

        Resource = "${aws_s3_bucket.lb_logs.arn}/lb-logs/AWSLogs/*"
      }
    ]
  })
}
