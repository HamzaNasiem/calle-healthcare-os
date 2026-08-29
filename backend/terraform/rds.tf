resource "aws_security_group" "rds" {
  name        = "rds-sg-${var.clinic_id}"
  description = "Allow Postgres access from ECS tasks only"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Allow postgres port from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
}

resource "aws_db_instance" "main_db" {
  identifier           = "clinic-db-${var.clinic_id}"
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.t4g.micro"
  allocated_storage    = 20
  storage_encrypted    = true
  
  db_name              = "ai_receptionist"
  username             = var.db_username
  password             = var.db_password
  
  db_subnet_group_name = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  skip_final_snapshot  = false
  publicly_accessible  = false
}

resource "aws_db_instance" "audit_db" {
  identifier           = "clinic-audit-db-${var.clinic_id}"
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.t4g.micro"
  allocated_storage    = 20
  storage_encrypted    = true
  
  db_name              = "ai_receptionist_audit"
  username             = var.db_username
  password             = var.db_password
  
  db_subnet_group_name = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  skip_final_snapshot  = false
  publicly_accessible  = false
}
