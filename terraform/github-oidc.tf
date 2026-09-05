########################### github oidc ###########################

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]
}

resource "aws_iam_role" "github_actions" {
  name = "github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }

        Action = "sts:AssumeRoleWithWebIdentity"

        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }

          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:Ahmad-Hamdy-Elhendawy/Multi-AZ-AWS-ECS-Fargate-RAG-Deployment:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}

########################### github actions permissions ###########################

resource "aws_iam_role_policy" "github_actions_test" {
  name = "github-actions-test"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "ECRPublicAuth",
        "Effect" : "Allow",
        "Action" : [
          "ecr-public:GetAuthorizationToken",
          "sts:GetServiceBearerToken",
          "ecs:RegisterTaskDefinition",
          "iam:PassRole",
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:DescribeTasks",
          "ecs:ListTasks"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "ECRPublicPush",
        "Effect" : "Allow",
        "Action" : [
          "ecr-public:BatchCheckLayerAvailability",
          "ecr-public:PutImage",
          "ecr-public:InitiateLayerUpload",
          "ecr-public:UploadLayerPart",
          "ecr-public:CompleteLayerUpload"
        ],
        "Resource" : "arn:aws:ecr-public::431451851290:repository/medical-rag"
      }
    ]
  })
}
