import json
from pathlib import Path

from catalog_ingestor.parser import _candidate_name, _parse_variants
from catalog_ingestor.schemas import CanonicalProduct, CatalogDocument


def test_synthetic_fixture_has_valid_unique_products():
    data = json.loads(Path("tests/fixtures/synthetic_products.json").read_text(encoding="utf-8"))
    products = [CanonicalProduct.model_validate(item) for item in data]
    assert len(products) == 3
    assert len({p.name for p in products}) == len(products)
    assert all(p.source.page > 0 for p in products)
    assert all(p.source.document_name == "synthetic_catalog.pdf" for p in products)


def test_public_sample_matches_catalog_schema():
    data = json.loads(Path("data/samples/catalog.sample.json").read_text(encoding="utf-8"))
    catalog = CatalogDocument.model_validate(data)

    assert catalog.source_pdf == "synthetic_catalog.pdf"
    assert [product.name for product in catalog.products] == ["SAMPLE PRODUCT"]


def test_parse_variants_single():
    text = "SKU TAMAÑO | 357211 | 15 ml"
    variants = _parse_variants(text)
    assert len(variants) == 1
    assert variants[0].sku == "357211"
    assert variants[0].size_value == 15.0
    assert variants[0].size_unit == "ml"


def test_parse_variants_multiple_with_decimal_comma():
    text = "SKU TAMAÑO 12345 15,5 ml | 67890 5 ml"
    variants = _parse_variants(text)
    assert len(variants) == 2
    assert variants[0].sku == "12345"
    assert variants[0].size_value == 15.5
    assert variants[0].size_unit == "ml"
    assert variants[1].sku == "67890"
    assert variants[1].size_value == 5.0


def test_parse_variants_supplement_quantity_and_package_detail():
    tablets = _parse_variants("SKU CANTIDAD\n33802 120 tabletas")
    assert tablets[0].model_dump() == {
        "sku": "33802",
        "size_value": 120.0,
        "size_unit": "tabletas",
        "raw_size": "120 tabletas",
    }

    package = _parse_variants("SKU CANTIDAD\n35602\n2 pk - 750 ml c/u")
    assert package[0].model_dump() == {
        "sku": "35602",
        "size_value": 2.0,
        "size_unit": "pk",
        "raw_size": "2 pk - 750 ml c/u",
    }


def test_parse_variants_missing_returns_empty():
    assert _parse_variants("no sku here") == []


def test_candidate_name_rejects_headers():
    blocks = []
    assert _candidate_name(blocks) is None


def test_candidate_name_accepts_uppercase_product():
    from catalog_ingestor.extractor import TextBlock

    blocks = [TextBlock((0, 0, 100, 20), "CEDAR MIST")]
    assert _candidate_name(blocks) == "CEDAR MIST"


def test_candidate_name_joins_wrapped_uppercase_heading():
    from catalog_ingestor.extractor import TextBlock

    blocks = [
        TextBlock((0, 0, 100, 10), "SAMPLE"),
        TextBlock((0, 11, 100, 21), "PRODUCT"),
        TextBlock((0, 23, 100, 33), "SKU TAMAÑO"),
    ]
    assert _candidate_name(blocks) == "SAMPLE PRODUCT"


def test_candidate_name_rejects_ignored_header():
    from catalog_ingestor.extractor import TextBlock

    blocks = [TextBlock((0, 0, 100, 20), "MODO DE USO |")]
    assert _candidate_name(blocks) is None
