from pathlib import Path

from core.parsing.generic_regex import GenericRegexParser
from core.utils.dates import parse_date_de
from core.utils.hashing import sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("abc")
    assert sha256_file(file_path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_parse_date_de() -> None:
    assert parse_date_de("12.03.2024") == "2024-03-12"


def test_regex_extraction() -> None:
    text = "ISIN CH1234567890 Valor 1234567 Waehrung CHF"
    parser = GenericRegexParser()
    product = parser.parse(Path("dummy.pdf"), text)
    assert product.isin.value == "CH1234567890"
    assert product.valor_number.value == "1234567"
    assert product.currency.value == "CHF"
