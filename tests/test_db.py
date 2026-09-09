import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from catalog_ingestor.db import (
    DocumentRow,
    ProductRow,
    VariantRow,
    make_session_factory,
    persist_catalog,
)
from catalog_ingestor.schemas import CanonicalProduct, ProductVariant, SourceRef


def _product(name: str, sku: str) -> CanonicalProduct:
    return CanonicalProduct(
        name=name,
        variants=[ProductVariant(sku=sku, size_value=5, size_unit="ml", raw_size="5 ml")],
        source=SourceRef(document_name="integration.pdf", page=1),
        raw_text=f"{name}\nSKU TAMAÑO\n{sku} 5 ml",
    )


def test_postgres_catalog_replacement_deletes_variants_first():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    filename = f"pytest-{uuid4()}.pdf"
    engine, Session = make_session_factory(database_url)
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip("test PostgreSQL is unavailable")

    try:
        persist_catalog(database_url, filename, [_product("FIRST", "100001")])
        persist_catalog(database_url, filename, [_product("SECOND", "100002")])

        with Session() as session:
            document = session.query(DocumentRow).filter_by(filename=filename).one()
            products = session.query(ProductRow).filter_by(document_id=document.id).all()
            assert [product.name for product in products] == ["SECOND"]
            variants = session.scalars(
                select(VariantRow).where(VariantRow.product_id == products[0].id)
            ).all()
            assert [variant.sku for variant in variants] == ["100002"]
    finally:
        with Session.begin() as session:
            document = session.query(DocumentRow).filter_by(filename=filename).one_or_none()
            if document:
                product_ids = select(ProductRow.id).where(ProductRow.document_id == document.id)
                session.query(VariantRow).filter(VariantRow.product_id.in_(product_ids)).delete(
                    synchronize_session=False,
                )
                session.query(ProductRow).filter_by(document_id=document.id).delete(
                    synchronize_session=False,
                )
                session.delete(document)
        engine.dispose()
