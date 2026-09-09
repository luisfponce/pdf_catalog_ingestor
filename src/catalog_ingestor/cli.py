from pathlib import Path
from typing import Annotated

import typer
from rich import print

from .config import Settings
from .db import init_db, persist_catalog
from .pipeline import extract_catalog

app = typer.Typer(no_args_is_help=True)


@app.command("init-db")
def init_database():
    settings = Settings()
    init_db(settings.database_url)
    print("[green]PostgreSQL schema ready.[/green]")


@app.command("extract")
def extract(
    pdf: Annotated[Path, typer.Argument(exists=True, readable=True)],
    save_db: Annotated[
        bool,
        typer.Option("--save-db", help="Persist extracted products to PostgreSQL"),
    ] = False,
) -> None:
    settings = Settings()
    catalog = extract_catalog(pdf, settings.output_dir)
    output = settings.output_dir / f"{pdf.stem}.json"
    catalog.save_json(output)
    print(f"[green]Extracted {len(catalog.products)} product candidates[/green]")
    print(f"JSON: {output}")
    print(f"Images: {settings.output_dir / 'images'}")
    if save_db:
        persist_catalog(settings.database_url, pdf.name, catalog.products)
        print("[green]Saved to PostgreSQL.[/green]")


if __name__ == "__main__":
    app()
