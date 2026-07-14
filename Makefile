# Contract Triage — one-command local stack.
#
#   make install   one-time: create the Python venv + install frontend deps
#   make up         bring up the whole stack (Langfuse + MinIO + DevUI + API + frontend)
#   make down       stop the container stack (keeps volumes)
#   make clean      stop the container stack and delete its volumes
#   make e2e        run the Playwright walkthrough against a running stack
#
# `make up` empties the triage store (fresh inbox), starts the Langfuse + MinIO
# containers (detached), then runs the three app processes — DevUI (:8080),
# API (:8000), frontend (:3000) — in the
# foreground. Ctrl-C stops the app processes; the containers keep running so a
# restart is fast. Use `make down` to stop them (or `make clean` to wipe data).

# Recipes are written as self-contained shell commands (backslash-continued
# blocks) so they work on stock macOS make (GNU Make 3.81, no .ONESHELL).
SHELL := bash
.DEFAULT_GOAL := help

COMPOSE := docker compose -f e2e/docker-compose.langfuse.yml
AGENT_DIR := app/agent
FRONTEND_DIR := app/frontend

.PHONY: help install preflight reset-db infra up down clean e2e ps logs

help:
	@echo "Contract Triage — make targets:"
	@echo "  make install   one-time: Python venv + frontend deps"
	@echo "  make up         bring up the whole stack (empties the DB, then containers + DevUI + API + frontend)"
	@echo "  make infra      bring up only the Langfuse + MinIO containers (detached)"
	@echo "  make reset-db   empty the triage store (DB + uploads) for a fresh inbox"
	@echo "  make down       stop the container stack (keep volumes)"
	@echo "  make clean      stop the container stack and delete volumes"
	@echo "  make e2e         run the Playwright walkthrough against a running stack"
	@echo "  make ps          show container status"
	@echo "  make logs        tail container logs"

# One-time dependency install. Needs uv (https://docs.astral.sh/uv) and Node >= 20.19.
install:
	cd $(AGENT_DIR) && uv venv --python 3.12 && source .venv/bin/activate && uv pip install -e . --prerelease=allow
	cd $(FRONTEND_DIR) && npm install
	@echo "✓ deps installed — set OPENAI_API_KEY in app/agent/.env, then run 'make up'"

# Fail early with guidance if no LLM API key is configured. Triage is a real LLM
# call, so `make up` refuses to start rather than boot a stack that can't triage.
# Accepts a key in the environment or in app/agent/.env (OpenAI or Azure OpenAI).
preflight:
	@if [ -t 2 ]; then R=$$'\033[31m'; Y=$$'\033[33m'; B=$$'\033[1m'; D=$$'\033[2m'; X=$$'\033[0m'; else R=; Y=; B=; D=; X=; fi; \
	env_file=$(AGENT_DIR)/.env; \
	if [ ! -f "$$env_file" ]; then \
	  printf '\n%s%s✗  No %s file.%s\n'                                                  "$$B" "$$R" "$$env_file" "$$X" >&2; \
	  printf '%s   Triage is a real LLM call — make up needs a key in that file.%s\n\n'  "$$D" "$$X" >&2; \
	  printf '   Create it, then set your real key:\n' >&2; \
	  printf '       %scp %s/.env.example %s%s\n'                                        "$$Y" "$(AGENT_DIR)" "$$env_file" "$$X" >&2; \
	  printf '       %s# then set OPENAI_API_KEY=sk-...%s\n\n'                            "$$D" "$$X" >&2; \
	  exit 1; \
	fi; \
	key=$$(grep -hE '^[[:space:]]*(OPENAI|AZURE_OPENAI)_API_KEY[[:space:]]*=' "$$env_file" | tail -n1 \
	       | sed -E -e 's/^[^=]*=[[:space:]]*//' -e 's/[[:space:]]*$$//' -e 's/^"//' -e 's/"$$//'); \
	case "$$key" in ""|sk-...|sk-xxx*|sk-your*|your-*|changeme*|REPLACE*|"<"*) bad=1 ;; \
	  *) if [ $${#key} -lt 20 ]; then bad=1; else bad=0; fi ;; esac; \
	if [ "$$bad" = 1 ]; then \
	  printf '\n%s%s✗  No usable LLM API key in %s.%s\n'                                 "$$B" "$$R" "$$env_file" "$$X" >&2; \
	  printf '%s   The file exists but OPENAI_API_KEY is missing or still a placeholder.%s\n\n' "$$D" "$$X" >&2; \
	  printf '   Set a real key in %s%s%s:\n'                                            "$$B" "$$env_file" "$$X" >&2; \
	  printf '       %sOPENAI_API_KEY=sk-...%s   %s← your actual key, not the placeholder%s\n\n' "$$Y" "$$X" "$$D" "$$X" >&2; \
	  printf '%s   Azure OpenAI works too: AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT.%s\n\n' "$$D" "$$X" >&2; \
	  exit 1; \
	fi

# Wipe the durable triage store so every `make up` boots a clean, empty inbox.
# The API recreates the schema via init_db() on boot; results, reviewer
# decisions and user-created contracts (plus their uploaded PDFs) are cleared.
# Paths mirror TRIAGE_DB_PATH / CONTRACT_UPLOAD_DIR in e2e/stack.env.
reset-db:
	rm -f  $(AGENT_DIR)/.data/triage.db $(AGENT_DIR)/.data/triage.db-wal $(AGENT_DIR)/.data/triage.db-shm
	rm -rf $(AGENT_DIR)/.data/uploads
	@echo "✓ triage store emptied — fresh inbox on boot"

# Langfuse trace stack + both MinIO object stores (detached, waits for health).
infra:
	$(COMPOSE) up -d --wait
	@echo "✓ containers up — Langfuse http://localhost:3001 (admin@northgate.local / langfuse-admin)"

# Full stack: containers + the three app processes. Ctrl-C tears the apps down.
# reset-db empties the triage store first so every boot starts with a clean inbox.
up: preflight reset-db infra
	@echo "▶ starting DevUI (:8080), API (:8000), frontend (:3000) — Ctrl-C to stop"; \
	e2e/run-api.sh & api_pid=$$!; \
	( source e2e/stack.env && cd $(AGENT_DIR) && source .venv/bin/activate && DEVUI_PORT=8080 python -m contract_triage.devui_app ) & devui_pid=$$!; \
	e2e/run-frontend.sh & fe_pid=$$!; \
	trap 'kill $$api_pid $$devui_pid $$fe_pid 2>/dev/null || true' EXIT INT TERM; \
	wait || true

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v

# Playwright walkthrough — drives an already-running stack (start it with `make up`).
e2e:
	cd e2e && npm install && npm test

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f
