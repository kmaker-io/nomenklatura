import re
from itertools import product
from typing import List, Set, TypeVar, Tuple, Iterable, Optional, Callable
from followthemoney.types.common import PropertyType

from nomenklatura.entity import CompositeEntity as Entity

V = TypeVar("V")
FIND_NUM = re.compile("\d{2,}")


def extract_numbers(values: List[str]) -> Set[str]:
    numbers: Set[str] = set()
    for value in values:
        numbers.update(FIND_NUM.findall(value))
    return numbers


def has_schema(left: Entity, right: Entity, schema: str) -> bool:
    """Check if one of the entities has the required schema."""
    if left.schema.is_a(schema) or right.schema.is_a(schema):
        if not left.schema.can_match(right.schema):
            return False
        return True
    return False


def props_pair(
    left: Entity, right: Entity, props: List[str]
) -> Tuple[Set[str], Set[str]]:
    left_values: Set[str] = set()
    right_values: Set[str] = set()
    for prop in props:
        left_values.update(left.get(prop, quiet=True))
        right_values.update(right.get(prop, quiet=True))
    return left_values, right_values


def type_pair(
    left: Entity, right: Entity, type_: PropertyType
) -> Tuple[List[str], List[str]]:
    left_values = left.get_type_values(type_, matchable=True)
    right_values = right.get_type_values(type_, matchable=True)
    return left_values, right_values


def compare_sets(
    left: Iterable[Optional[V]],
    right: Iterable[Optional[V]],
    compare_func: Callable[[V, V], float],
    select_func: Callable[[Iterable[float]], float] = max,
) -> float:
    """Compare two sets of values pair-wise and select the highest-scored result."""
    results: List[float] = []
    for (l, r) in product(left, right):
        if l is None or r is None:
            continue
        results.append(compare_func(l, r))
    if not len(results):
        return 0.0
    return select_func(results)
