variable "project_root" {
  type        = string
  description = "Absolute or relative path to PlaybookChatbot repo root (parent of backend/, frontend/)."
  default     = ".."
}

variable "docker_host" {
  type        = string
  description = "Docker daemon address. Linux default: unix socket. Windows Docker Desktop: npipe:////./pipe/docker_engine"
  default     = ""
}

variable "backend_port" {
  type    = number
  default = 8001
}

variable "frontend_port" {
  type    = number
  default = 80
}
