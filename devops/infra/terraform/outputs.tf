output "server_ipv4" {
  value       = hcloud_server.app.ipv4_address
  description = "Создай A-запись domain -> этот IP до первого деплоя (иначе ACME не выпустит сертификат)."
}

output "ssh_command" {
  value = "ssh deploy@${hcloud_server.app.ipv4_address}"
}
