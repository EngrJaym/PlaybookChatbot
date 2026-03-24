# Terraform (Docker) — Pattern A

## Kailangan mo muna

1. **Docker** (Docker Desktop sa Windows) — running.
2. **Terraform** ≥ 1.3 — [install](https://developer.hashicorp.com/terraform/install).
3. Sa repo root: may **`./.env`** (optional pero recommended), **`./data/`**, at **`./backend/credentials/`** (kahit may `.gitkeep` lang).

## Mga command

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## Pagkatapos ng `apply`

- Web UI: `http://localhost` (port 80)
- API (extension / direct): `http://localhost:8001/api`

## Windows: ayaw kumonekta ng Terraform sa Docker

Gumawa ng `terraform.tfvars`:

```hcl
docker_host = "npipe:////./pipe/docker_engine"
```

## Tandaan

- Ito ay **kapareho ng layunin** ng `docker-compose.yml` pero pinapatakbo sa pamamagitan ng Terraform + Docker provider.
- Huwag sabay na mag-run ng parehong stack: **itigil** muna ang `docker compose` containers (`docker compose down`) bago mag-`terraform apply`, para walang conflict sa port **80** / **8001** o sa pangalan ng container.
