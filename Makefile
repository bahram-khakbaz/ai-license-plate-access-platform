.PHONY: help init models build up down restart logs status backup clean

help:
	@echo "Available commands:"
	@echo "  make init      - Create local folders and .env from .env.example"
	@echo "  make models    - Download or verify AI model files"
	@echo "  make build     - Build Docker image"
	@echo "  make up        - Start application"
	@echo "  make down      - Stop application"
	@echo "  make restart   - Restart application"
	@echo "  make logs      - Follow application logs"
	@echo "  make status    - Show container status"
	@echo "  make backup    - Backup runtime database and config"
	@echo "  make clean     - Stop and remove containers"

init:
	@mkdir -p data uploads exports logs backups models
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; else echo ".env already exists"; fi

models:
	bash scripts/download-models.sh

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

status:
	docker compose ps

backup:
	bash scripts/backup.sh

clean:
	docker compose down --remove-orphans
