output "web_app_url" {
  description = "PWA / static UI (nginx)."
  value       = "http://localhost:${var.frontend_port}"
}

output "backend_api_url" {
  description = "Direct API (for extension pointing at host)."
  value       = "http://localhost:${var.backend_port}/api"
}

output "network_name" {
  value = docker_network.playbook.name
}
