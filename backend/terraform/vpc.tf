module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "clinic-vpc-${var.clinic_id}"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  database_subnets = ["10.0.11.0/24", "10.0.12.0/24"]
  
  enable_nat_gateway = false
  enable_vpn_gateway = false
  
  create_database_subnet_group = true
}

resource "aws_security_group" "vpc_link" {
  name        = "vpc-link-sg-${var.clinic_id}"
  description = "Allow traffic from API Gateway to VPC Link"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Allow API Gateway HTTP API"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
