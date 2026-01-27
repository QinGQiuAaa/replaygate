.PHONY: up down demo

up:
	docker compose up -d --build

down:
	docker compose down

demo:
	powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
