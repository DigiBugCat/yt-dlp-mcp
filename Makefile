.DEFAULT_GOAL := help

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

COMPOSE := docker compose -f backend/docker-compose.yml

.PHONY: help
help:
	@echo "yt-dlp-mcp"
	@echo ""
	@echo "Docker:"
	@echo "  make build              Build app image"
	@echo "  make up                 Start app (no tunnel)"
	@echo "  make up-tunnel          Start app + cloudflared (requires valid CF_TUNNEL_TOKEN)"
	@echo "  make down               Stop containers"
	@echo "  make ps                 Show container status"
	@echo "  make logs-app           Tail app logs"
	@echo "  make logs-tunnel        Tail cloudflared logs"
	@echo "  make health             Check /healthz inside container"
	@echo "  make mcp-smoke          Call MCP tools from inside container"
	@echo ""
	@echo "Terraform (Tunnel + DNS):"
	@echo "  make tf-init            terraform init"
	@echo "  make tf-apply           terraform apply (requires CF account/zone vars)"
	@echo "  make tf-destroy         terraform destroy"
	@echo "  make deploy             Run backend/scripts/deploy.sh (apply + write CF_TUNNEL_TOKEN + up-tunnel)"
	@echo "  make destroy            Run backend/scripts/destroy.sh (down + destroy)"
	@echo ""
	@echo "Notes:"
	@echo "  - Uses .env automatically via docker compose."
	@echo "  - For tunnel creation, set CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_ZONE_ID, DOMAIN, SUBDOMAIN, and auth vars."

.PHONY: build
build:
	$(COMPOSE) build app

.PHONY: up
up:
	$(COMPOSE) up -d app

.PHONY: up-tunnel
up-tunnel:
	$(COMPOSE) up -d app cloudflared

.PHONY: down
down:
	$(COMPOSE) down

.PHONY: ps
ps:
	$(COMPOSE) ps

.PHONY: logs-app
logs-app:
	$(COMPOSE) logs -f --tail=200 app

.PHONY: logs-tunnel
logs-tunnel:
	$(COMPOSE) logs -f --tail=200 cloudflared

.PHONY: health
health:
	$(COMPOSE) exec -T app curl -fsS http://127.0.0.1:3000/healthz

.PHONY: mcp-smoke
mcp-smoke:
	$(COMPOSE) exec -T app python - <<-'PY'
	import asyncio
	from fastmcp import Client

	async def main() -> None:
	    async with Client("http://127.0.0.1:3000/mcp") as client:
	        tools = await client.list_tools()
	        print("TOOLS", [t.name for t in tools])
	        r = await client.call_tool("transcribe", {"url": "https://example.com/video"})
	        print("TRANSCRIBE", r.data)
	        job_id = r.data.get("job_id") if isinstance(r.data, dict) else None
	        if job_id:
	            s = await client.call_tool("job_status", {"job_id": job_id})
	            print("JOB_STATUS", s.data)

	asyncio.run(main())
	PY

.PHONY: tf-init
tf-init:
	backend/scripts/terraformw.sh -chdir=terraform init -upgrade

.PHONY: tf-apply
tf-apply:
	backend/scripts/terraformw.sh -chdir=terraform apply

.PHONY: tf-destroy
tf-destroy:
	backend/scripts/terraformw.sh -chdir=terraform destroy

.PHONY: deploy
deploy:
	backend/scripts/deploy.sh

.PHONY: destroy
destroy:
	backend/scripts/destroy.sh
