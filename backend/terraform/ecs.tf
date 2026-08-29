resource "aws_security_group" "ecs_tasks" {
  name        = "ecs-tasks-sg-${var.clinic_id}"
  description = "Allow inbound from API Gateway VPC Link ONLY"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Allow traffic from VPC Link"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.vpc_link.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name        = "internal.clinic${var.clinic_id}"
  description = "Internal DNS for ECS"
  vpc         = module.vpc.vpc_id
}

resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id
    dns_records {
      ttl  = 10
      type = "SRV"
    }
  }
}

resource "aws_ecs_cluster" "main" {
  name = "clinic-cluster-${var.clinic_id}"
}

resource "aws_ecs_task_definition" "api" {
  family                   = "api-${var.clinic_id}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  
  container_definitions = jsonencode([{
    name  = "api-container"
    image = "${var.ecr_repository_url}:latest"
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
    }]
    environment = [
      { name = "DATABASE_URL", value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.main_db.endpoint}/ai_receptionist" },
      { name = "AUDIT_DATABASE_URL", value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.audit_db.endpoint}/ai_receptionist_audit" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/api-${var.clinic_id}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "api-service-${var.clinic_id}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn   = aws_service_discovery_service.api.arn
    container_port = 8000
    container_name = "api-container"
  }
}

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "clinic-vpc-link-${var.clinic_id}"
  security_group_ids = [aws_security_group.vpc_link.id]
  subnet_ids         = module.vpc.public_subnets
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "clinic-api-${var.clinic_id}"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "ecs_integration" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "HTTP_PROXY"
  integration_uri  = aws_service_discovery_service.api.arn
  
  integration_method = "ANY"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.main.id
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.ecs_integration.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.http_api.api_endpoint
}
