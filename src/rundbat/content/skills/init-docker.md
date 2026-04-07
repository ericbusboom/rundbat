# init-docker

Scaffold a `docker/` directory for the project with Dockerfile,
docker-compose.yml, and Justfile.

## Steps

1. Read `rundbat.yaml` for app name, framework, and services
2. Detect framework from project files if not configured
3. Generate `docker/Dockerfile` for the detected framework
4. Generate `docker/docker-compose.yml` with configured services
5. Generate `docker/Justfile` with standard recipes
6. Generate `docker/.env.example` from dotconfig (secrets redacted)
