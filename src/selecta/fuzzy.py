# from thefuzz import fuzz
from rapidfuzz import fuzz

method = fuzz.partial_ratio
method = fuzz.ratio
method = fuzz.token_set_ratio
method = fuzz.partial_token_set_ratio
method = fuzz.WRatio
method = fuzz.token_sort_ratio


def fuzzy_list(search_text: str, lines: list[str]) -> list:
    """Return a list of lines sorted by fuzzy score."""

    def compare(line1, line2):
        return method(search_text, line1) - method(search_text, line2)

    lines.sort(key=lambda x: compare(x, search_text), reverse=True)
    return lines
