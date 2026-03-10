.PHONY: help up down restart logs status build update backup health clean db-shell api-key

COMPOSE = docker compose -f docker-compose.yml
COMPOSE_PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Development ─────────────────────────────────────────────

up: ## Start all services (dev)
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) restart

build: ## Rebuild Docker images
	$(COMPOSE) build

logs: ## Show logs (all services)
	$(COMPOSE) logs -f --tail=100

logs-api: ## Show API logs
	$(COMPOSE) logs -f --tail=100 api

logs-worker: ## Show worker logs
	$(COMPOSE) logs -f --tail=100 worker

logs-bot: ## Show bot logs
	$(COMPOSE) logs -f --tail=100 bot

status: ## Show service status
	$(COMPOSE) ps

# ── Production ──────────────────────────────────────────────

prod-up: ## Start production
	$(COMPOSE_PROD) up -d

prod-down: ## Stop production
	$(COMPOSE_PROD) down

prod-restart: ## Restart production
	systemctl restart aia-meetings

prod-logs: ## Production logs
	$(COMPOSE_PROD) logs -f --tail=100

# ── Database ────────────────────────────────────────────────

db-shell: ## Open PostgreSQL shell
	$(COMPOSE) exec db psql -U aia -d aia_meetings

db-migrate: ## Run database migrations
	$(COMPOSE) exec api alembic upgrade head

# ── Utilities ───────────────────────────────────────────────

api-key: ## Create a new API key
	@curl -sf -X POST http://localhost:8000/api/v1/auth/keys?name=cli | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"API Key: {d['api_key']}\")"

backup: ## Run backup
	bash deploy/scripts/backup.sh

health: ## Check health
	@curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "API is not responding"

update: ## Pull latest & redeploy
	bash deploy/scripts/update.sh

clean: ## Remove stopped containers, unused images
	docker compose down --remove-orphans
	docker system prune -f

test: ## Run tests
	$(COMPOSE) exec api pytest tests/ -v

shell: ## Open shell in API container
	$(COMPOSE) exec api bash
