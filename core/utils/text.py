import re


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate_excerpt(text: str, max_len: int = 200) -> str:
    text = normalize_whitespace(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def parse_number_ch(value: str) -> float | None:
    cleaned = value.replace("'", "").replace(" ", "").strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
