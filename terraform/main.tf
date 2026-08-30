# s3 removed from tf state
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

provider "aws" {
  region = var.region
}

###### VPC ######

resource "aws_vpc" "main" {
  cidr_block       = "10.0.0.0/16"
  instance_tenancy = "default"

  tags = {
    Name = "main"
  }
}

###### PUBLIC SUBNETS ######

resource "aws_subnet" "public_subnet_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-1"
  }
}

resource "aws_subnet" "public_subnet_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-2"
  }
}

###### PRIVATE SUBNETS ######

resource "aws_subnet" "private_subnet_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "${var.region}a"

  tags = {
    Name = "private-1"
  }
}

resource "aws_subnet" "private_subnet_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.4.0/24"
  availability_zone = "${var.region}b"

  tags = {
    Name = "private-2"
  }
}

###### INTERNET GATEWAY ######

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "main"
  }
}

###### PUBLIC ROUTE TABLE ######

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "public"
  }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_subnet_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_subnet_2.id
  route_table_id = aws_route_table.public.id
}

###### NAT GATEWAY ######

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "nat-eip"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_subnet_1.id

  depends_on = [
    aws_internet_gateway.main
  ]

  tags = {
    Name = "main-nat"
  }
}

###### PRIVATE ROUTE TABLE ######

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "private"
  }
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_subnet_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_subnet_2.id
  route_table_id = aws_route_table.private.id
}

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

###### ALB ######

resource "aws_lb" "main_alb" {
  name               = "main-alb"
  internal           = false
  load_balancer_type = "application"

  subnets = [
    aws_subnet.public_subnet_1.id,
    aws_subnet.public_subnet_2.id
  ]

  security_groups = [
    aws_security_group.alb_sg.id
  ]

  enable_deletion_protection = false

  access_logs {
    bucket  = aws_s3_bucket.lb_logs.id
    prefix  = "lb-logs"
    enabled = true
  }

  tags = {
    Environment = "production"
    Name        = "main-alb"
  }
}

resource "aws_lb_listener" "lb_listener" {
  load_balancer_arn = aws_lb.main_alb.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.medical_task_tg.arn
  }
}

###### TARGET GROUP ######

resource "aws_lb_target_group" "medical_task_tg" {
  name        = "medical-task-tg"
  port        = 8501
  protocol    = "HTTP"
  target_type = "ip"

  vpc_id = aws_vpc.main.id
}

###### ECS CLUSTER ######

resource "aws_ecs_cluster" "medical_rag_cluster" {
  name = "medical-rag-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

###### CLOUDWATCH LOG GROUP ######

resource "aws_cloudwatch_log_group" "medical_rag" {
  name              = "/ecs/medical-rag"
  retention_in_days = 7
}

###### ECS TASK EXECUTION ROLE ######

resource "aws_iam_role" "ecs_task_execution" {
  name = "ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role = aws_iam_role.ecs_task_execution.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

###### ECS TASK DEFINITION ######

resource "aws_ecs_task_definition" "medical_rag_task" {
  family = "medical-rag"

  requires_compatibilities = [
    "FARGATE"
  ]

  network_mode = "awsvpc"

  execution_role_arn = aws_iam_role.ecs_task_execution.arn

  cpu    = "1024"
  memory = "2048"

  container_definitions = jsonencode([
    {
      name      = "medical-rag-container"
      image     = "public.ecr.aws/c0w4z1m9/medical-rag:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8501
          hostPort      = 8501
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.medical_rag.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

###### ECS SERVICE ######

resource "aws_ecs_service" "medical_rag_ecs" {
  name = "medical-rag-ecs"

  cluster = aws_ecs_cluster.medical_rag_cluster.id

  task_definition = aws_ecs_task_definition.medical_rag_task.arn

  desired_count = 2

  launch_type = "FARGATE"
  depends_on = [aws_lb_listener.lb_listener]

  network_configuration {
    subnets = [
      aws_subnet.private_subnet_1.id,
      aws_subnet.private_subnet_2.id
    ]

    security_groups = [
      aws_security_group.ecs_sg.id
    ]

    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.medical_task_tg.arn
    container_name   = "medical-rag-container"
    container_port   = 8501
  }
}

###### SECURITY GROUPS ######

resource "aws_security_group" "alb_sg" {
  name   = "alb-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group" "ecs_sg" {
  name   = "ecs-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb_sg.id

  cidr_ipv4 = "0.0.0.0/0"

  from_port = 80
  to_port   = 80

  ip_protocol = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id = aws_security_group.alb_sg.id

  referenced_security_group_id = aws_security_group.ecs_sg.id

  from_port = 8501
  to_port   = 8501

  ip_protocol = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id = aws_security_group.ecs_sg.id

  referenced_security_group_id = aws_security_group.alb_sg.id

  from_port = 8501
  to_port   = 8501

  ip_protocol = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_egress_https" {
  security_group_id = aws_security_group.ecs_sg.id
  cidr_ipv4          = "0.0.0.0/0"
  from_port          = 443
  to_port            = 443
  ip_protocol        = "tcp"
  description        = "Allow HTTPS outbound for AWS service APIs"
}

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
            "token.actions.githubusercontent.com:sub" = "repo:Ahmad-Hamdy-Elhendawy@210468353/aws-ecs-fargate-rag-cicd-deployment@1351505767:ref:refs/heads/main"
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