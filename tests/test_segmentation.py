from catalog_ingestor.extractor import (
    PageLayout,
    PositionedWord,
    TextBlock,
    TextCell,
    reconstruct_text_cells,
)
from catalog_ingestor.parser import _description, layout_adapter, parse_page


def test_positioned_words_are_reconstructed_inside_strict_cells():
    words = [
        PositionedWord((90, 100, 145, 110), "CEDAR"),
        PositionedWord((148, 100, 180, 110), "MIST"),
        PositionedWord((350, 100, 395, 110), "CITRUS"),
        PositionedWord((398, 100, 430, 110), "GLOW"),
        PositionedWord((90, 115, 125, 125), "Arbor"),
        PositionedWord((128, 115, 155, 125), "ficta"),
        PositionedWord((350, 115, 390, 125), "Citrus"),
        PositionedWord((393, 115, 425, 125), "ficta"),
        PositionedWord((90, 130, 110, 140), "SKU"),
        PositionedWord((115, 130, 160, 140), "TAMAÑO"),
        PositionedWord((350, 130, 370, 140), "SKU"),
        PositionedWord((375, 130, 420, 140), "TAMAÑO"),
    ]

    cells = reconstruct_text_cells(words, width=595, height=482)

    assert cells[0].text.splitlines() == ["CEDAR MIST", "Arbor ficta", "SKU TAMAÑO"]
    assert cells[1].text.splitlines() == ["CITRUS GLOW", "Citrus ficta", "SKU TAMAÑO"]
    assert all("CITRUS" not in line.text for line in cells[0].blocks)
    assert all("CEDAR" not in line.text for line in cells[1].blocks)


def test_description_keeps_short_continuation_and_stops_at_usage():
    lines = [
        "CEDAR MIST",
        "Arbor ficta",
        "SKU TAMAÑO",
        "000001 15 ml",
        "This invented sample has a crisp woodland aroma,",
        "with a light and",
        "clean finish.",
        "MODO DE USO |",
        "Use in a diffuser or dilute before applying to skin.",
    ]
    blocks = [TextBlock((0, index, 1, index + 1), line) for index, line in enumerate(lines)]

    assert _description(blocks, "CEDAR MIST") == (
        "This invented sample has a crisp woodland aroma, with a light and clean finish."
    )


def test_synthetic_adjacent_cards_are_parsed_independently(tmp_path):
    width, height = 595, 482
    cells = reconstruct_text_cells(
        [
            PositionedWord((90, 100, 145, 110), "CEDAR"),
            PositionedWord((148, 100, 180, 110), "MIST"),
            PositionedWord((90, 120, 110, 130), "SKU"),
            PositionedWord((115, 120, 160, 130), "TAMAÑO"),
            PositionedWord((90, 140, 130, 150), "000001"),
            PositionedWord((135, 140, 145, 150), "15"),
            PositionedWord((150, 140, 165, 150), "ml"),
            PositionedWord((350, 100, 395, 110), "CITRUS"),
            PositionedWord((398, 100, 430, 110), "GLOW"),
            PositionedWord((350, 120, 370, 130), "SKU"),
            PositionedWord((375, 120, 420, 130), "TAMAÑO"),
            PositionedWord((350, 140, 390, 150), "000002"),
            PositionedWord((395, 140, 405, 150), "5"),
            PositionedWord((410, 140, 425, 150), "ml"),
        ],
        width,
        height,
    )
    layout = PageLayout(15, width, height, [], [], cells)

    products = parse_page(None, layout, "synthetic_catalog.pdf", tmp_path)

    assert [product.name for product in products] == ["CEDAR MIST", "CITRUS GLOW"]
    assert [[variant.sku for variant in product.variants] for product in products] == [
        ["000001"],
        ["000002"],
    ]
    assert all("repeated_sku_marker" not in product.warnings for product in products)


def test_unknown_layout_is_not_guessed():
    empty_cells = [TextCell((0, 0, 1, 1), []) for _ in range(4)]
    layout = PageLayout(1, 595, 482, [], [], empty_cells)

    assert layout_adapter(layout) is None
