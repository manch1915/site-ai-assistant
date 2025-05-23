from app.domain.excerpt import best_lines, readable_line

PRICES = """# Repair prices

Every price includes the part, labour and the warranty.

| Repair | Time | Price |
|---|---|---|
| iPhone 14 screen replacement | about 1 hour | €169 |
| iPhone 15 screen replacement | about 1 hour | €189 |
| Samsung Galaxy S24 screen replacement | about 1.5 hours | €219 |
"""


def test_table_rows_read_like_text() -> None:
    assert readable_line("| iPhone 15 screen | about 1 hour | €189 |") == (
        "iPhone 15 screen: about 1 hour, €189"
    )
    assert readable_line("## Phones") == "Phones"


def test_picks_the_row_that_answers() -> None:
    assert best_lines(PRICES, "How much is an iPhone 15 screen?") == [
        "iPhone 15 screen replacement: about 1 hour, €189",
    ]
    assert len(best_lines(PRICES, "screen replacement prices")) == 3


def test_falls_back_to_the_opening_lines() -> None:
    assert best_lines(PRICES, "zzz")[0] == "Repair prices"
