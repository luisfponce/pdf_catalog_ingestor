# Contributing

Thank you for improving the catalog ingestor. Contributions should be narrow, reproducible, and
safe to publish.

## Prerequisites

- Python 3.12 or newer
- Git
- Docker with Compose for container and PostgreSQL validation

## Set up a development environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Run the fast checks before making a change:

```bash
ruff check .
pytest
```

The PostgreSQL integration test runs when `TEST_DATABASE_URL` is set. A local example is:

```bash
docker compose up -d postgres
TEST_DATABASE_URL=postgresql+psycopg://catalog:catalog@localhost:5432/catalog pytest tests/test_db.py
```

## Development workflow

1. Update `main` and create a short-lived branch named `feat/...`, `fix/...`, `docs/...`, or
   `chore/...`.
2. Reproduce behavior with a focused synthetic test.
3. Use red-green-refactor: observe the failure, make the smallest correct change, then clean up.
4. Run focused tests during development and the full Ruff and pytest checks before opening a pull
   request.
5. Rebase onto current `main`, resolve conflicts locally, and rerun validation.

Commit messages follow Conventional Commits, for example
`fix(parser): stop descriptions at usage boundaries`. Keep implementation and its tests in the
same commit when they form one behavioral change. Do not force-push `main`; use
`--force-with-lease` only on your own pull-request branch after a rebase.

## Pull requests

Explain the problem, behavioral impact, and validation performed. Keep unrelated formatting,
generated artifacts, and dependency changes separate. Reviews prioritize correctness, provenance,
data safety, and regression coverage.

Never commit:

- `.env` files, credentials, access tokens, or private connection strings;
- source catalog PDFs or copied catalog prose;
- extracted or third-party product images;
- real generated catalog JSON;
- fixtures that are not synthetic or independently authored.

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
