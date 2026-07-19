.PHONY: install-backend test-backend check-backend install-frontend typecheck-frontend build-frontend compose-up compose-down

install-backend:
	cd backend && python -m pip install -r requirements.txt

test-backend:
	cd backend && pytest

check-backend:
	cd backend && python manage.py check

install-frontend:
	cd frontend && npm install

typecheck-frontend:
	cd frontend && npm run typecheck

build-frontend:
	cd frontend && npm run build

compose-up:
	docker compose up --build

compose-down:
	docker compose down

