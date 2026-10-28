variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Hetzner Cloud API token (Read & Write). Передавать через TF_VAR_hcloud_token, не коммитить."
}

variable "project" {
  type    = string
  default = "tenable"
}

variable "environment" {
  type    = string
  default = "production"
  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "environment: production | staging."
  }
}

variable "location" {
  type        = string
  default     = "fsn1"
  description = "Дата-центр Hetzner (fsn1, nbg1, hel1 — EU)."
}

variable "server_type" {
  type        = string
  default     = "cx32"
  description = "Тип сервера. Проверь актуальные имена/цены: `hcloud server-type list`."
}

variable "volume_size_gb" {
  type        = number
  default     = 40
  description = "Отдельный диск под данные (Redis AOF, Postgres при self-hosted)."
}

variable "ssh_public_key" {
  type        = string
  description = "Публичный ключ администратора (ed25519)."
}

variable "admin_cidrs" {
  type        = list(string)
  description = "CIDR, которым разрешён SSH (22). Например [\"203.0.113.10/32\"]. 0.0.0.0/0 запрещён."
  validation {
    condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
    error_message = "Укажи конкретные CIDR администраторов, не 0.0.0.0/0."
  }
}

variable "deploy_public_key" {
  type        = string
  description = "Публичный ключ ТОЛЬКО для CI-деплоя (отдельная пара; приватный — в GitHub Secrets)."
}

variable "domain" {
  type        = string
  description = "FQDN API (A/AAAA запись на выходной IP). Caddy выпустит TLS-сертификат автоматически."
}
