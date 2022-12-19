import os
import logging
from banal import ensure_list
from typing import Any, Generator, Optional, Dict, List
from urllib.parse import urljoin
from followthemoney.types import registry
from followthemoney.namespace import Namespace

from nomenklatura.entity import CE
from nomenklatura.dataset import DS
from nomenklatura.cache import Cache
from nomenklatura.enrich.common import Enricher, EnricherConfig
from nomenklatura.util import normalize_url

log = logging.getLogger(__name__)


class YenteEnricher(Enricher):
    """Uses the `yente` match API to look up entities in a specific dataset."""

    def __init__(self, dataset: DS, cache: Cache, config: EnricherConfig):
        super().__init__(dataset, cache, config)
        self._api: str = config.pop("api")
        self._dataset: str = config.pop("dataset", "default")
        self._threshold: Optional[float] = config.pop("threshold", None)
        self._ns: Optional[Namespace] = None
        if self.get_config_bool("strip_namespace"):
            self._ns = Namespace()

        api_key: Optional[str] = os.path.expandvars(config.pop("api_key", "")).strip()
        if api_key is None or not len(api_key):
            api_key = os.environ.get("YENTE_API_KEY")
        self._api_key: Optional[str] = api_key
        if self._api_key is not None:
            self.session.headers["Authorization"] = f"ApiKey {self._api_key}"

        self.cache.preload(f"{self._api}%")

    def make_url(self, entity: CE) -> str:
        return urljoin(self._api, f"entities/{entity.id}")

    def match(self, entity: CE) -> Generator[CE, None, None]:
        if not entity.schema.matchable:
            return
        url = urljoin(self._api, f"match/{self._dataset}")
        if self._threshold is not None:
            url = normalize_url(url, {"threshold": self._threshold})
        cache_key = f"{url}:{entity.id}"
        response = self.cache.get_json(cache_key, max_age=self.cache_days)
        if response is None:
            props: Dict[str, List[str]] = {}
            for prop in entity.iterprops():
                if prop.type == registry.entity:
                    continue
                if prop.matchable:
                    props[prop.name] = entity.get(prop)
            data = {
                "queries": {
                    "entity": {
                        "schema": entity.schema.name,
                        "properties": props,
                    }
                }
            }
            resp = self.session.post(url, json=data)
            resp.raise_for_status()
            response = resp.json().get("responses", {}).get("entity", {})
            self.cache.set_json(cache_key, response)
        for result in response.get("results", []):
            proxy = self.load_entity(entity, result)
            proxy.add("sourceUrl", self.make_url(proxy))
            if self._ns is not None:
                proxy = self._ns.apply(proxy)
            yield proxy

    def _traverse_nested(self, entity: CE, response: Any) -> Generator[CE, None, None]:
        entity = self.load_entity(entity, response)
        if self._ns is not None:
            entity = self._ns.apply(entity)
        yield entity
        for prop_name, values in response.get("properties", {}).items():
            prop = entity.schema.properties.get(prop_name)
            if prop is None or prop.type != registry.entity:
                continue
            for value in ensure_list(values):
                if isinstance(value, dict):
                    if prop.reverse is not None and not prop.reverse.stub:
                        reverse = prop.reverse.name
                        if reverse not in value["properties"]:
                            value["properties"][reverse] = []
                        value["properties"][reverse].append(entity.id)
                    yield from self._traverse_nested(entity, value)

    def expand(self, entity: CE, match: CE) -> Generator[CE, None, None]:
        url = self.make_url(match)
        for source_url in match.get("sourceUrl", quiet=True):
            if source_url.startswith(self._api):
                url = source_url
        url = normalize_url(url, {"nested": True})
        response = self.http_get_json_cached(url)
        yield from self._traverse_nested(match, response)
