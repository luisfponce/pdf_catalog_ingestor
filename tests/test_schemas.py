import json

import pytest
from pydantic import ValidationError

from catalog_ingestor.schemas import CanonicalProduct, CatalogDocument, SourceRef


def test_product_requires_non_blank_identity():
    with pytest.raises(ValidationError, match="product name is required"):
        CanonicalProduct(
            name="   ",
            source=SourceRef(document_name="synthetic_catalog.pdf", page=1),
            raw_text="synthetic fixture",
        )


def test_catalog_json_serialization_creates_parent_directories(tmp_path):
    catalog = CatalogDocument(source_pdf="synthetic_catalog.pdf", products=[])
    output_path = tmp_path / "nested" / "catalog.json"

    catalog.save_json(output_path)

    assert json.loads(output_path.read_text(encoding="utf-8"))["source_pdf"] == (
        "synthetic_catalog.pdf"
    )
