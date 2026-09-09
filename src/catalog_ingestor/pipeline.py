from pathlib import Path

from .extractor import extract_layout
from .parser import _dedupe_warnings, layout_adapter, parse_page
from .schemas import CatalogDocument


def extract_catalog(pdf_path: Path, output_dir: Path) -> CatalogDocument:
    doc, layouts = extract_layout(pdf_path)
    image_dir = output_dir / "images"
    products = []
    page_audit = []
    try:
        for layout in layouts:
            adapter = layout_adapter(layout)
            page_products = parse_page(doc, layout, pdf_path.name, image_dir)
            products.extend(page_products)
            warnings = []
            if adapter is None and 15 <= layout.page_number <= 69:
                warnings.append("unrecognized_layout_skipped")
            page_audit.append(
                {
                    "page": layout.page_number,
                    "adapter": adapter or "none",
                    "candidate_count": len(page_products),
                    "warnings": warnings,
                }
            )
    finally:
        doc.close()

    sku_products = {}
    for product in products:
        for variant in product.variants:
            sku_products.setdefault(variant.sku, []).append(product)
    for duplicate_products in sku_products.values():
        if len(duplicate_products) > 1:
            for product in duplicate_products:
                product.warnings = _dedupe_warnings(
                    [
                        *product.warnings,
                        "duplicate_sku",
                        "low_confidence",
                    ]
                )

    total = len(products)
    with_variants = sum(1 for p in products if p.variants)
    with_images = sum(1 for p in products if p.image)
    with_warnings = sum(1 for p in products if p.warnings)
    summary = {
        "total_products": total,
        "products_with_variants": with_variants,
        "products_with_images": with_images,
        "products_with_warnings": with_warnings,
        "pages_processed": len(layouts),
    }
    return CatalogDocument(
        source_pdf=pdf_path.name,
        products=products,
        metadata={
            "pages": len(layouts),
            "parser": "yl_mx_positioned_cells_v2",
            "summary": summary,
            "page_audit": page_audit,
        },
    )
