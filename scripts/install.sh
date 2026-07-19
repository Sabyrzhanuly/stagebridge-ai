#!/usr/bin/env bash
set -euo pipefail

echo "=== DB Control Center — Install ==="

# Check Docker
if ! command -v docker &>/dev/null; then
  echo "ERROR: docker not found. Install Docker first."
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "ERROR: docker compose not found."
  exit 1
fi

cd "$(dirname "$0")/.."

# Generate .env if missing
if [ ! -f .env ]; then
  echo "Generating .env from .env.example..."
  cp .env.example .env

  # Generate Fernet key
  FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
  if [ -n "$FERNET_KEY" ]; then
    sed -i "s|FERNET_KEY=.*|FERNET_KEY=$FERNET_KEY|" .env
    echo "Generated FERNET_KEY"
  else
    echo "WARNING: Could not generate FERNET_KEY. Install cryptography: pip install cryptography"
    echo "Then run: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    echo "And update FERNET_KEY in .env manually."
  fi
else
  echo ".env already exists, skipping."
fi

# Build and start
echo "Building images..."
docker compose build

echo "Starting services..."
docker compose up -d

echo "Waiting for services to be healthy..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker compose exec -T backend alembic upgrade head 2>/dev/null || echo "Alembic migrations skipped (empty or not configured)"

# Seed admin
echo ""
echo "Creating admin user..."
read -p "Admin username [admin]: " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}
read -p "Admin email [admin@localhost]: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
read -sp "Admin password: " ADMIN_PASS
echo ""

docker compose exec -T backend python -c "
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base
from app.models.user import User
from app.services.auth_service import hash_password

engine = create_engine(settings.app_db_url_sync)
Base.metadata.create_all(engine)

with Session(engine) as s:
    existing = s.execute(select(User).where(User.username == '${ADMIN_USER}')).scalar_one_or_none()
    if existing:
        print(f'User ${ADMIN_USER} already exists')
    else:
        u = User(username='${ADMIN_USER}', email='${ADMIN_EMAIL}', password_hash=hash_password('${ADMIN_PASS}'), role='admin')
        s.add(u)
        s.commit()
        print(f'Admin user ${ADMIN_USER} created')
"

echo ""
echo "=== Installation complete ==="
echo "Frontend: http://localhost"
echo "API:      http://localhost:8000/api/health"
echo "RabbitMQ: http://localhost:15672 (guest/guest)"
