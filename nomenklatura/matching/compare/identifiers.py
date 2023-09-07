from followthemoney.proxy import E
from followthemoney.types import registry

from nomenklatura.matching.util import type_pair, has_schema, compare_sets
from nomenklatura.util import levenshtein

# def imo_match(left: E, right: E) -> float:
#     """Matching IMO numbers between the two entities."""
#     lv, rv = type_pair(left, right, registry.imo)
#     return has_overlap(set(lv), set(rv))


def orgid_disjoint(left: E, right: E) -> float:
    """Two companies or organizations have different tax identifiers or registration
    numbers."""
    # used by name-qualified
    if not has_schema(left, right, "Organization"):
        return 0.0
    left_ids, right_ids = type_pair(left, right, registry.identifier)
    return 1 - compare_sets(left_ids, right_ids, _nq_compare_identifiers)


def _nq_compare_identifiers(left: str, right: str) -> float:
    """Overly clever method for comparing tax and company identifiers."""
    if min(len(left), len(right)) < 5:
        return 0.0
    if left in right or right in left:
        return 1.0
    distance = levenshtein(left, right)
    ratio = 1.0 - (distance / float(max(len(left), len(right))))
    return ratio if ratio > 0.7 else 0.0
