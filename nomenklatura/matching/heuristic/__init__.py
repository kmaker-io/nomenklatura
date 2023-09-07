from typing import Dict
from prefixdate import Precision
from followthemoney.proxy import E
from followthemoney.types import registry
from nomenklatura.matching.types import MatchingResult, ScoringAlgorithm, FeatureDocs
from nomenklatura.matching.heuristic.logic import soundex_name_parts, jaro_name_parts
from nomenklatura.matching.heuristic.logic import compare_identifiers
from nomenklatura.matching.heuristic.feature import Feature, HeuristicAlgorithm
from nomenklatura.matching.util import make_github_url, dates_precision
from nomenklatura.matching.util import props_pair, type_pair, compare_sets


class NameMatcher(HeuristicAlgorithm):
    """An algorithm that matches on entity name, using phonetic comparisons and edit
    distance to generate potential matches. This implementation is vaguely based on
    the behaviour proposed by the US OFAC documentation (FAQ #249)."""

    # Try to re-produce results from: https://sanctionssearch.ofac.treas.gov/
    # cf. https://ofac.treasury.gov/faqs/topic/1636

    NAME = "name-based"
    features = [
        Feature(func=jaro_name_parts, weight=0.5),
        Feature(func=soundex_name_parts, weight=0.5),
    ]

    @classmethod
    def compute_score(cls, weights: Dict[str, float]) -> float:
        return sum(weights.values()) / float(len(weights))


class NameQualifiedMatcher(ScoringAlgorithm):
    """Same as the name-based algorithm, but scores will be reduced if a mis-match
    of birth dates and nationalities is found for persons, or different
    tax/registration identifiers are included for organizations and companies."""

    NAME = "name-qualified"
    COUNTRIES_DISJOINT = "countries_disjoint"
    DOB_DAY_DISJOINT = "dob_day_disjoint"
    DOB_YEAR_DISJOINT = "dob_year_disjoint"
    ID_DISJOINT = "identifier_disjoint"

    @classmethod
    def explain(cls) -> FeatureDocs:
        features = NameMatcher.explain()
        features[cls.COUNTRIES_DISJOINT] = {
            "description": "Both entities are linked to different countries.",
            "coefficient": -0.1,
            "url": make_github_url(NameQualifiedMatcher.compare),
        }
        features[cls.DOB_DAY_DISJOINT] = {
            "description": "Both persons have different birthdays.",
            "coefficient": -0.15,
            "url": make_github_url(NameQualifiedMatcher.compare),
        }
        features[cls.DOB_YEAR_DISJOINT] = {
            "description": "Both persons are born in different years.",
            "coefficient": -0.1,
            "url": make_github_url(NameQualifiedMatcher.compare),
        }
        features[cls.ID_DISJOINT] = {
            "description": "Two companies or organizations have different tax identifiers or registration numbers.",
            "coefficient": -0.2,
            "url": make_github_url(NameQualifiedMatcher.compare),
        }
        return features

    @classmethod
    def compare(cls, query: E, match: E) -> MatchingResult:
        result = NameMatcher.compare(query, match)
        features = cls.explain()

        result["features"][cls.COUNTRIES_DISJOINT] = 0.0
        query_countries, match_countries = type_pair(query, match, registry.country)
        if is_disjoint(query_countries, match_countries):
            weight = features[cls.COUNTRIES_DISJOINT]["coefficient"]
            result["features"][cls.COUNTRIES_DISJOINT] = weight
            result["score"] += weight

        query_dob, match_dob = props_pair(query, match, ["birthDate"])
        query_days = dates_precision(query_dob, Precision.DAY)
        match_days = dates_precision(match_dob, Precision.DAY)
        result["features"][cls.DOB_DAY_DISJOINT] = 0.0
        if is_disjoint(query_days, match_days):
            weight = features[cls.DOB_DAY_DISJOINT]["coefficient"]
            result["features"][cls.DOB_DAY_DISJOINT] = weight
            result["score"] += weight

        query_years = dates_precision(query_dob, Precision.YEAR)
        match_years = dates_precision(match_dob, Precision.YEAR)
        result["features"][cls.DOB_YEAR_DISJOINT] = 0.0
        if is_disjoint(query_years, match_years):
            weight = features[cls.DOB_YEAR_DISJOINT]["coefficient"]
            result["features"][cls.DOB_YEAR_DISJOINT] = weight
            result["score"] += weight

        result["features"][cls.ID_DISJOINT] = 0.0
        if query.schema.is_a("Organization") or match.schema.is_a("Organization"):
            query_ids, match_ids = type_pair(query, match, registry.identifier)
            if len(query_ids) and len(match_ids):
                base_weight = features[cls.ID_DISJOINT]["coefficient"]
                score = compare_sets(query_ids, match_ids, compare_identifiers)
                weight = (1 - score) * base_weight
                result["features"][cls.ID_DISJOINT] = weight
                result["score"] += weight
        return result
