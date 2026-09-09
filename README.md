# Young Living Catalog Ingestor

[![CI][ci-badge]][ci-workflow]
[![Python 3.12+][python-badge]][python]
[![Docker][docker-badge]][docker]
[![MIT license][license-badge]](LICENSE)

A deterministic Python PDF catalog extraction pipeline that converts supported product layouts
into canonical structured JSON, normalized WebP images, and optional PostgreSQL records using
PyMuPDF, Pydantic, and Docker.

> [!IMPORTANT]
> This parser is layout-specific and evolving. It does not infer data from unknown layouts. This
> independent project is not affiliated with, endorsed by, or sponsored by Young Living Essential
> Oils, LC. Product names and trademarks belong to their respective owners.

## Features

- Reconstructs positioned PDF text into strict product-card cells with PyMuPDF
- Parses names, scientific names, descriptions, ingredients, usage, SKUs, and package sizes
- Validates a canonical product contract with Pydantic
- Associates embedded product images spatially and normalizes them to WebP
- Retains page, bounding-box, raw-text, confidence, and warning provenance
- Writes JSON on every extraction and optionally replaces the source document in PostgreSQL
- Audits unsupported pages instead of guessing records
- Uses independently authored synthetic fixtures for public regression coverage

## Supported scope

The current adapter supports text-layer PDFs that use the known four-cell catalog layout and
contain `SKU TAMAÑO` or `SKU CANTIDAD` markers. The parser handles both single- and multi-variant
cards and quantity/package formats covered by the test suite.

Scanned PDFs, optical character recognition (OCR), arbitrary tables, and unrelated catalog layouts
are not supported. Pages without a recognized marker layout produce no products and appear in
`metadata.page_audit` as skipped where applicable. Low-confidence records are retained with
warnings rather than silently discarded.

## Architecture

```mermaid
flowchart LR
    PDF[User-supplied PDF] --> Layout[PyMuPDF positioned text and images]
    Layout --> Cells[Strict four-cell reconstruction]
    Cells --> Parser[Layout-specific deterministic parser]
    Parser --> Models[Pydantic canonical models]
    Models --> JSON[JSON and WebP artifacts]
    Models -->|optional --save-db| PG[(PostgreSQL)]
```

`extract_catalog()` is the reusable pipeline boundary. The Typer command invokes it directly,
writes the canonical JSON document, and persists products only when `--save-db` is present.

## Quick start

Prerequisites are Docker Engine and Docker Compose. No source catalogs are distributed with this
repository; use only PDFs you are authorized to process.

```bash
cp .env.example .env
mkdir -p data/input data/output
docker compose up -d postgres
docker compose run --rm app init-db
```

Place an authorized catalog at `data/input/catalog.pdf`, then extract JSON, images, and PostgreSQL
records:

```bash
docker compose run --rm app extract /data/input/catalog.pdf --save-db
```

PostgreSQL persistence is optional. For JSON and image output only, omit `--save-db`:

```bash
docker compose run --rm app extract /data/input/catalog.pdf
```

Generated artifacts are written through the host mount:

```text
data/output/catalog.json
data/output/images/*.webp
```

The image and Compose service both run the application as a non-root user. Compose defaults to
UID/GID `1000:1000` so mounted output remains host-writable; set `UID` and `GID` in the command
environment when your host account uses different IDs.

## Usage

Show the available commands:

```bash
docker compose run --rm app --help
docker compose run --rm app extract --help
```

The output follows `CatalogDocument` and `CanonicalProduct`. A complete invented example is tracked
at [`data/samples/catalog.sample.json`](data/samples/catalog.sample.json):

```json
{
  "source_pdf": "synthetic_catalog.pdf",
  "products": [
    {
      "name": "SAMPLE PRODUCT",
      "category": "other",
      "variants": [{"sku": "000001", "size_value": 15, "size_unit": "ml"}],
      "source": {"document_name": "synthetic_catalog.pdf", "page": 1},
      "raw_text": "SAMPLE PRODUCT\nSKU TAMAÑO\n000001 15 ml"
    }
  ]
}
```

Review `warnings`, `extraction_confidence`, and `metadata.page_audit` before treating output as
production data. To inspect persisted variants:

```bash
docker compose exec postgres psql -U catalog -d catalog -c \
  "SELECT p.name, v.sku, v.size_value, v.size_unit, p.image_path FROM products p LEFT JOIN product_variants v ON v.product_id = p.id ORDER BY p.source_page, p.name;"
```

## Canonical data

Each product separates:

- source-derived fields such as name, description, ingredients, usage, and variants;
- media and provenance such as image metadata, PDF filename, page, and card bounding box;
- extraction metadata such as confidence, warnings, and future derived tags.

Variants are separate because one product card can contain multiple SKU and size combinations.
PostgreSQL stores documents, products, and product variants in separate tables. Ingredients, usage
modes, warnings, and image metadata remain JSONB so the early schema can evolve without pretending
that every source layout has the same detail.

## Configuration

| Variable | Docker default | Local default | Required | Purpose |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://catalog:catalog@postgres:5432/catalog` | `postgresql+psycopg://catalog:catalog@localhost:5432/catalog` | Only for database commands | SQLAlchemy PostgreSQL connection URL |
| `OUTPUT_DIR` | `/data/output` | `data/output` | No | JSON and normalized image destination |

`.env.example` contains development-only local values. `Settings` loads `.env` automatically and
ignores unrelated keys. Never commit `.env`; use secret storage and non-default credentials outside
local development. Compose overrides the local database hostname because containers reach the
database as `postgres`.

## Local development

Docker is the primary runtime path. Contributors can use an editable Python installation:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
yl-catalog --help
ruff check .
pytest
python -m build
```

The normal test suite uses synthetic data. To include the PostgreSQL replacement/integrity test:

```bash
docker compose up -d postgres
TEST_DATABASE_URL=postgresql+psycopg://catalog:catalog@localhost:5432/catalog pytest tests/test_db.py
```

## Data and legal policy

The repository intentionally ignores `.env`, `data/input/**`, `data/output/**`, all PDFs, and
extracted WebP images. It tracks only compact, invented JSON examples and fixtures. Do not open a
pull request containing source catalogs, copied descriptions, generated product output, or product
artwork.

You are responsible for obtaining permission to process, store, and use each source document and
its extracted content. The MIT license covers repository code and independently authored project
materials only. It does not grant rights to third-party catalogs, product copy, images, brands, or
trademarks.

## Community

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, GitHub Flow, tests, and data-safety rules.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.
- Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).
- Use synthetic reproductions in public bug reports.

## Roadmap

- Add isolated parser adapters for additional layout families
- Produce richer extraction-quality reports and review workflows
- Add OCR as an explicit, separately tested fallback for scanned documents
- Define upload limits, asynchronous jobs, retention, authentication, and concurrency before adding
  an HTTP API

## License

Repository code is available under the [MIT License](LICENSE), copyright 2026 Luis F. Ponce. The
license does not apply to user-supplied or other third-party catalog content.

[ci-badge]: https://github.com/%3Cgithub-owner%3E/youngliving-catalog-ingestor/actions/workflows/ci.yml/badge.svg
[ci-workflow]: https://github.com/%3Cgithub-owner%3E/youngliving-catalog-ingestor/actions/workflows/ci.yml
[docker]: https://www.docker.com/
[docker-badge]: https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white
[license-badge]: https://img.shields.io/badge/license-MIT-blue.svg
[python]: https://www.python.org/downloads/
[python-badge]: https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white
