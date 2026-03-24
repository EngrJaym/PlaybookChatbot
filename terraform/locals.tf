locals {
  root = abspath("${path.module}/${var.project_root}")

  env_raw = fileexists("${local.root}/.env") ? file("${local.root}/.env") : ""

  env_lines = [
    for line in split("\n", local.env_raw) :
    trimspace(line)
    if trimspace(line) != "" && !startswith(trimspace(line), "#") && strcontains(trimspace(line), "=")
  ]

  env_lines_no_data_dir = [
    for line in local.env_lines : line
    if !startswith(trimspace(line), "DATA_DIR=")
  ]

  docker_env = concat(
    [
      for line in local.env_lines_no_data_dir : line
      if can(regex("^[A-Za-z_][A-Za-z0-9_]*=.", line))
    ],
    ["DATA_DIR=/data"]
  )
}
