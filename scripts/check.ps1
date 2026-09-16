$ErrorActionPreference = "Stop"

python -m ruff check app tests main.py
python -m ruff format --check app tests main.py
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
alembic heads
alembic current

Push-Location frontend
try {
    npm run typecheck
    npm run lint
    npm run test
    npm run build
} finally {
    Pop-Location
}
