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
