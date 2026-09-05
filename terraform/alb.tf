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
