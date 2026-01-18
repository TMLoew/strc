from pathlib import Path

from core.parsing.issuer_lukb_style import LUKBStyleParser


def test_golden_fixture() -> None:
    text = Path("backend/tests/fixtures/canonical_termsheet.txt").read_text()
    parser = LUKBStyleParser()
    product = parser.parse(Path("fixture.pdf"), text)
    assert product.isin.value == "CH1234567890"
    assert product.valor_number.value == "1234567"
    assert product.currency.value == "CHF"
