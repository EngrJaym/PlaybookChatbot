provider "docker" {
  # Set var.docker_host on Windows Docker Desktop if needed, e.g. npipe:////./pipe/docker_engine
  host = var.docker_host != "" ? var.docker_host : null
}
