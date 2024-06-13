import logging
from typing import List, Optional, Type, Dict, Set
from followthemoney.schema import Schema
from itertools import combinations
from collections import defaultdict
from pprint import pprint
from rich.console import Console
from rich.table import Table
from rich import box

from nomenklatura.dataset import DS
from nomenklatura.entity import CE
from nomenklatura.store import Store, View
from nomenklatura.judgement import Judgement
from nomenklatura.resolver import Resolver
from nomenklatura.index import Index
from nomenklatura.matching import DefaultAlgorithm, ScoringAlgorithm

log = logging.getLogger(__name__)


def _print_stats(pairs: int, suggested: int, scores: List[float]) -> None:
    matches = len(scores)
    log.info(
        "Xref: %d pairs, %d suggested, avg: %.2f, min: %.2f, max: %.2f",
        pairs,
        suggested,
        sum(scores) / max(1, matches),
        min(scores, default=0.0),
        max(scores, default=0.0),
    )


def print_name_sources(title: str, entity: CE) -> None:
    tuples = []
    sorted_tuples = []
    for stmt in entity.statements:
        if stmt.prop != "name":
            continue
        tuples.append((stmt.dataset, stmt.entity_id, stmt.prop, stmt.lang, stmt.value))
    sorted_tuples.extend(sorted(tuples))
    tuples = []
    for stmt in entity.statements:
        if stmt.prop != "alias":
            continue
        tuples.append((stmt.dataset, stmt.entity_id, stmt.prop, stmt.lang, stmt.value))
    sorted_tuples.extend(sorted(tuples))

    table = Table(title=title + "\n" + entity.id, box=box.SIMPLE, expand=True)
    table.add_column("Dataset", style="cyan", max_width=20)
    table.add_column("Entity ID", style="magenta", max_width=30)
    table.add_column("Prop", style="blue")
    table.add_column("Lang", style="green")
    table.add_column("Name", style="yellow")

    for dataset, entity_id, prop, lang, value in sorted_tuples:
        table.add_row(dataset, entity_id, prop, lang, "• " + value)

    console = Console()
    console.print(table)


def report_potential_conflicts(
    view: View[DS, CE],
    negative_check_matches: Dict[str, Set[str]],
    resolver: Resolver[CE],
) -> None:
    # pprint(negative_check_matches)
    for candidate_id, matches in negative_check_matches.items():
        for left_id, right_id in combinations(matches, 2):
            judgement = resolver.get_judgement(left_id, right_id)
            if judgement == Judgement.NEGATIVE:
                log.info(
                    "Potential conflict: %s <> %s for %s",
                    left_id,
                    right_id,
                    candidate_id,
                )
                left = view.get_entity(left_id)
                right = view.get_entity(right_id)
                candidate = view.get_entity(candidate_id)
                print_name_sources("Candidate", candidate)
                print_name_sources("Left side of negative decision", left)
                print_name_sources("Right side of negative decision", right)


def xref(
    resolver: Resolver[CE],
    store: Store[DS, CE],
    limit: int = 5000,
    scored: bool = True,
    external: bool = True,
    range: Optional[Schema] = None,
    auto_threshold: Optional[float] = None,
    negative_check_threshold: Optional[float] = None,
    focus_dataset: Optional[str] = None,
    algorithm: Type[ScoringAlgorithm] = DefaultAlgorithm,
    user: Optional[str] = None,
) -> None:
    log.info("Begin xref: %r, resolver: %s", store, resolver)
    view = store.default_view(external=external)
    index = Index(view)
    index.build()
    negative_check_threshold = negative_check_threshold or auto_threshold or 0.98
    negative_check_matches: Dict[str, Set[str]] = defaultdict(set)
    try:
        scores: List[float] = []
        suggested = 0
        idx = 0
        for idx, ((left_id, right_id), score) in enumerate(index.pairs()):
            if idx % 1000 == 0 and idx > 0:
                _print_stats(idx, suggested, scores)

            if not resolver.check_candidate(left_id, right_id):
                continue

            left = view.get_entity(left_id.id)
            right = view.get_entity(right_id.id)
            if left is None or left.id is None or right is None or right.id is None:
                continue

            if not left.schema.can_match(right.schema):
                continue

            if range is not None:
                if not left.schema.is_a(range) and not right.schema.is_a(range):
                    continue

            if scored:
                result = algorithm.compare(left, right)
                score = result.score

            scores.append(score)

            if score > negative_check_threshold:
                negative_check_matches[left_id.id].add(right_id.id)
                negative_check_matches[right_id.id].add(left_id.id)

            # Not sure this is globally a good idea.
            if len(left.datasets.intersection(right.datasets)) > 0:
                score = score * 0.7

            if auto_threshold is not None and score > auto_threshold:
                log.info("Auto-merge [%.2f]: %s <> %s", score, left, right)
                canonical_id = resolver.decide(
                    left_id, right_id, Judgement.POSITIVE, user=user
                )
                store.update(canonical_id)
                continue

            if focus_dataset in left.datasets and focus_dataset not in right.datasets:
                score = (score + 1.0) / 2.0
            if focus_dataset not in left.datasets and focus_dataset in right.datasets:
                score = (score + 1.0) / 2.0

            resolver.suggest(left.id, right.id, score, user=user)
            if suggested >= limit:
                break
            suggested += 1
        _print_stats(idx, suggested, scores)

        report_potential_conflicts(view, negative_check_matches, resolver)

    except KeyboardInterrupt:
        log.info("User cancelled, xref will end gracefully.")
