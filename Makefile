# Local Docker helpers (GNU Make). On Windows use Git Bash or WSL, or the docker commands below.
COMPOSE_DEV := docker compose -f docker-compose.dev.yml
COMPOSE_PROD := docker compose -f docker-compose.prod.yml
WEB := tehnikagoda_web_dev

.PHONY: help up down logs ps test check coverage backup seed health restart monitor monitor-down

help:
	@echo "Targets:"
	@echo "  make up         - build & start dev stack"
	@echo "  make down       - stop dev stack"
	@echo "  make restart    - recreate web + celery"
	@echo "  make logs       - follow web logs"
	@echo "  make ps         - container status"
	@echo "  make test       - Django tests in web container"
	@echo "  make coverage   - tests + coverage report (fail_under=65)"
	@echo "  make check      - manage.py check"
	@echo "  make health     - curl /healthz/"
	@echo "  make backup     - pg_dump via scripts/backup.sh"
	@echo "  make seed       - run seed_db.py in web container"
	@echo "  make monitor    - start Uptime Kuma on :3001"
	@echo "  make monitor-down - stop Uptime Kuma"

up:
	$(COMPOSE_DEV) up --build -d

down:
	$(COMPOSE_DEV) down

restart:
	$(COMPOSE_DEV) up -d --force-recreate web celery_worker

logs:
	$(COMPOSE_DEV) logs -f web

ps:
	$(COMPOSE_DEV) ps

test:
	docker exec $(WEB) python manage.py test --verbosity=1

coverage:
	docker exec $(WEB) pip install -q coverage
	docker exec $(WEB) coverage run manage.py test --verbosity=1
	docker exec $(WEB) coverage report

check:
	docker exec $(WEB) python manage.py check

health:
	curl -sf http://127.0.0.1:8000/healthz/ && echo

backup:
	COMPOSE_FILE=docker-compose.dev.yml bash scripts/backup.sh

seed:
	docker exec $(WEB) python seed_db.py

monitor:
	docker compose -f docker-compose.monitoring.yml up -d

monitor-down:
	docker compose -f docker-compose.monitoring.yml down
