.PHONY: local-up local-down local-status local-logs local-models test check

# LocalAI management
local-up:
	docker compose up -d
	@echo "Waiting for LocalAI to start..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -sf http://localhost:8081/v1/models > /dev/null 2>&1; then \
			echo "LocalAI is ready at http://localhost:8081"; \
			break; \
		fi; \
		echo "  waiting... ($$i/10)"; \
		sleep 3; \
	done

local-down:
	docker compose down

local-status:
	@docker compose ps 2>/dev/null || echo "LocalAI is not running"
	@echo ""
	@curl -sf http://localhost:8081/v1/models 2>/dev/null | python3 -m json.tool || echo "API not reachable"

local-logs:
	docker compose logs -f --tail=50

local-models:
	@curl -sf http://localhost:8081/models/available 2>/dev/null | python3 -m json.tool | head -60 || echo "API not reachable"

# Development
test:
	.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py

test-all:
	.venv/bin/pytest tests/ -v

check:
	.venv/bin/aicp --check
