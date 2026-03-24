resource "docker_network" "playbook" {
  name = "playbookchatbot_tf"
}

resource "docker_image" "backend" {
  name = "playbookchatbot-backend:tf"
  build {
    context    = "${local.root}/backend"
    dockerfile = "Dockerfile"
  }
  triggers = {
    dockerfile = filesha256("${local.root}/backend/Dockerfile")
    req        = filesha256("${local.root}/backend/requirements.txt")
  }
}

resource "docker_image" "frontend" {
  name = "playbookchatbot-frontend:tf"
  build {
    context    = "${local.root}/frontend"
    dockerfile = "Dockerfile"
    build_args = {
      VITE_API_URL = "/api"
    }
  }
  triggers = {
    dockerfile = filesha256("${local.root}/frontend/Dockerfile")
    nginx      = filesha256("${local.root}/frontend/nginx.conf")
    pkg        = filesha256("${local.root}/frontend/package.json")
  }
}

resource "docker_container" "backend" {
  name  = "playbook_backend"
  image = docker_image.backend.image_id

  restart = "unless-stopped"

  ports {
    internal = 8001
    external = var.backend_port
    ip       = "0.0.0.0"
  }

  volumes {
    host_path      = "${local.root}/backend/credentials"
    container_path = "/app/credentials"
    read_only      = true
  }

  volumes {
    host_path      = "${local.root}/data"
    container_path = "/data"
    read_only      = true
  }

  env = local.docker_env

  networks_advanced {
    name    = docker_network.playbook.name
    aliases = ["backend"]
  }

  healthcheck {
    test         = ["CMD", "curl", "-f", "-s", "http://localhost:8001/"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 10
    start_period = "60s"
  }
}

resource "docker_container" "frontend" {
  name  = "playbook_frontend"
  image = docker_image.frontend.image_id

  restart = "unless-stopped"
  depends_on = [
    docker_container.backend
  ]

  ports {
    internal = 80
    external = var.frontend_port
    ip       = "0.0.0.0"
  }

  networks_advanced {
    name = docker_network.playbook.name
  }
}
