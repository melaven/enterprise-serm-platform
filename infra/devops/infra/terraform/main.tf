terraform {
  required_version = ">= 1.6"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.48"
    }
  }

  # Remote state обязателен для команды (state содержит IP/ID; не храни локально в git).
  # backend "s3" {   # любой S3-совместимый (Hetzner Object Storage, R2, MinIO)
  #   bucket = "tenable-tfstate"
  #   key    = "production/terraform.tfstate"
  #   region = "eu-central"
  #   endpoints = { s3 = "https://fsn1.your-objectstorage.com" }
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_requesting_account_id  = true
  #   use_path_style              = true
  # }
}

provider "hcloud" {
  token = var.hcloud_token
}

locals {
  name   = "${var.project}-${var.environment}"
  labels = { project = var.project, env = var.environment, managed_by = "terraform" }
}

resource "hcloud_ssh_key" "admin" {
  name       = "${local.name}-admin"
  public_key = var.ssh_public_key
  labels     = local.labels
}

# Firewall на уровне гипервизора: 22 только админам, 80/443 — всем. Redis/Postgres наружу НЕ открыты.
resource "hcloud_firewall" "web" {
  name   = "${local.name}-fw"
  labels = local.labels

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.admin_cidrs
    description = "SSH admin"
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTP (ACME + redirect)"
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTPS"
  }
  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
    description = "HTTP/3"
  }
}

resource "hcloud_volume" "data" {
  name              = "${local.name}-data"
  size              = var.volume_size_gb
  location          = var.location
  format            = "ext4"
  delete_protection = var.environment == "production"
  labels            = local.labels
}

resource "hcloud_server" "app" {
  name               = local.name
  image              = "ubuntu-24.04"
  server_type        = var.server_type
  location           = var.location
  ssh_keys           = [hcloud_ssh_key.admin.id]
  firewall_ids       = [hcloud_firewall.web.id]
  delete_protection  = var.environment == "production"
  rebuild_protection = var.environment == "production"
  labels             = local.labels

  # Секреты приложения (.env) сюда НЕ кладём: user_data виден в метаданных сервера.
  # Их доставляет CI по SSH при деплое из GitHub Secrets.
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    deploy_public_key = var.deploy_public_key
    admin_public_key  = var.ssh_public_key
    volume_id         = hcloud_volume.data.id
    domain            = var.domain
  })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  lifecycle {
    ignore_changes = [user_data, image] # изменение cloud-init не должно пересоздавать прод-сервер
  }
}

resource "hcloud_volume_attachment" "data" {
  volume_id = hcloud_volume.data.id
  server_id = hcloud_server.app.id
  automount = false # монтируем сами в cloud-init (предсказуемый путь /srv/data)
}
