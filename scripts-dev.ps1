param(
  [ValidateSet("install-backend", "test-backend", "check-backend", "install-frontend", "typecheck-frontend", "build-frontend", "compose-up", "compose-down")]
  [string]$Command
)

switch ($Command) {
  "install-backend" { Push-Location backend; python -m pip install -r requirements.txt; Pop-Location }
  "test-backend" { Push-Location backend; pytest; Pop-Location }
  "check-backend" { Push-Location backend; python manage.py check; Pop-Location }
  "install-frontend" { Push-Location frontend; npm install; Pop-Location }
  "typecheck-frontend" { Push-Location frontend; npm run typecheck; Pop-Location }
  "build-frontend" { Push-Location frontend; npm run build; Pop-Location }
  "compose-up" { docker compose up --build }
  "compose-down" { docker compose down }
}

