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

  health_check_grace_period_seconds = 120 

  deployment_circuit_breaker {
  enable   = true
  rollback = true
}


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
