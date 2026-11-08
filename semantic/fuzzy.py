"""Fuzzy Catalog Matching using Levenshtein distance.

Computes edit distances to suggest or auto-correct typos in table and column identifiers.
"""

from typing import List, Optional, Tuple


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes the Levenshtein distance between two strings."""
    s1 = s1.lower()
    s2 = s2.lower()

    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


COMMON_ABBREVIATIONS = {
    "cust": "customer",
    "prod": "product",
    "qty": "quantity",
    "cat": "category",
    "num": "number",
}


def expand_abbreviations(name: str) -> str:
    parts = name.lower().split("_")
    expanded_parts = [COMMON_ABBREVIATIONS.get(p, p) for p in parts]
    return "_".join(expanded_parts)


def find_closest_identifier(
    target: str,
    candidates: List[str],
    max_distance: int = 2,
) -> Optional[Tuple[str, int]]:
    """
    Finds the candidate identifier with the lowest Levenshtein distance
    within the max_distance threshold (<= 2). Supports common schema abbreviations.
    """
    best_candidate: Optional[str] = None
    min_dist = max_distance + 1

    expanded_target = expand_abbreviations(target)

    for cand in candidates:
        cand_lower = cand.lower()
        # Direct distance
        dist1 = levenshtein_distance(target, cand_lower)
        # Expanded abbreviation distance
        dist2 = levenshtein_distance(expanded_target, cand_lower)
        dist = min(dist1, dist2)

        if dist < min_dist:
            min_dist = dist
            best_candidate = cand

    if best_candidate is not None and min_dist <= max_distance:
        return (best_candidate, min_dist)
    return None
