import orjson
import fakeredis
from pathlib import Path
from followthemoney import model

from nomenklatura.resolver import Resolver
from nomenklatura.judgement import Judgement
from nomenklatura.store.versioned import VersionedRedisStore
from nomenklatura.dataset import Dataset
from nomenklatura.entity import CompositeEntity

DAIMLER = "66ce9f62af8c7d329506da41cb7c36ba058b3d28"
PERSON = {
    "id": "john-doe",
    "schema": "Person",
    "properties": {"name": ["John Doe"], "birthDate": ["1976"]},
}

PERSON_EXT = {
    "id": "john-doe-2",
    "schema": "Person",
    "properties": {"birthPlace": ["North Texas"]},
}


def test_store_basics(test_dataset: Dataset):
    redis = fakeredis.FakeStrictRedis(version=6, decode_responses=False)
    resolver = Resolver[CompositeEntity]()
    store = VersionedRedisStore(test_dataset, resolver, db=redis)
    entity = CompositeEntity.from_data(test_dataset, PERSON)
    entity_ext = CompositeEntity.from_data(test_dataset, PERSON_EXT)
    assert len(list(store.view(test_dataset).entities())) == 0
    writer = store.writer()
    writer.add_entity(entity)
    writer.flush()
    writer.release()
    assert len(list(store.view(test_dataset).entities())) == 1
    writer.add_entity(entity_ext)
    writer.flush()
    assert len(list(store.view(test_dataset).entities())) == 2

    merged_id = resolver.decide(
        "john-doe",
        "john-doe-2",
        judgement=Judgement.POSITIVE,
        user="test",
    )
    store.update(merged_id)
    assert len(list(store.view(test_dataset).entities())) == 1


def test_graph_query(donations_path: Path, test_dataset: Dataset):
    redis = fakeredis.FakeStrictRedis(version=6, decode_responses=False)
    resolver = Resolver[CompositeEntity]()
    store = VersionedRedisStore(test_dataset, resolver, db=redis)
    assert len(list(store.view(test_dataset).entities())) == 0
    with store.writer() as writer:
        with open(donations_path, "rb") as fh:
            while line := fh.readline():
                data = orjson.loads(line)
                proxy = CompositeEntity.from_data(test_dataset, data)
                writer.add_entity(proxy)
        writer.release()

    assert len(list(store.view(test_dataset).entities())) == 474

    view = store.default_view()
    entity = view.get_entity("banana")
    assert entity is None, entity
    assert not view.has_entity("banana")
    entity = view.get_entity(DAIMLER)
    assert entity is not None, entity
    assert view.has_entity(DAIMLER)
    assert "Daimler" in entity.caption, entity.caption
    assert len(entity.datasets) == 1
    ds = entity.datasets.pop()
    assert test_dataset.name in ds, ds

    adjacent = list(view.get_adjacent(entity))
    assert len(adjacent) == 10, len(adjacent)
    schemata = [e.schema for (_, e) in adjacent]
    assert model.get("Payment") in schemata, set(schemata)
    assert model.get("Address") in schemata, set(schemata)
    assert model.get("Company") not in schemata, set(schemata)

    ext_entity = CompositeEntity.from_data(test_dataset, PERSON)
    with store.writer() as writer:
        for stmt in ext_entity.statements:
            stmt.external = True
            writer.add_statement(stmt)
        writer.release()

    view = store.view(test_dataset, external=False)
    entity = view.get_entity("john-doe")
    assert entity is None, entity
    # FIXME: this is broken at the moment but I'm not sure it's
    # worth fixing.
    # assert not view.has_entity("john-doe")

    ext_view = store.view(test_dataset, external=True)
    entity = ext_view.get_entity("john-doe")
    assert entity is not None, entity
    assert ext_view.has_entity("john-doe")
    assert len(list(entity.statements)) == len(list(ext_entity.statements))


def test_versioning(test_dataset: Dataset):
    redis = fakeredis.FakeStrictRedis(version=6, decode_responses=False)
    resolver = Resolver[CompositeEntity]()
    store = VersionedRedisStore(test_dataset, resolver, db=redis)
    assert store.get_latest(test_dataset.name) is None
    assert len(store.get_history(test_dataset.name)) == 0
    entity = CompositeEntity.from_data(test_dataset, PERSON)
    version_a = "A"
    with store.writer(version=version_a) as writer:
        writer.add_entity(entity)
        writer.flush()
        writer.release()
    assert store.get_latest(test_dataset.name) == version_a
    assert len(store.get_history(test_dataset.name)) == 1
    version_b = "B"
    with store.writer(version=version_b) as writer:
        writer.add_entity(entity)
        writer.flush()
        writer.release()
    assert store.get_latest(test_dataset.name) == version_b
    assert len(store.get_history(test_dataset.name)) == 2

    store.drop_version(test_dataset.name, version_b)
    assert store.get_latest(test_dataset.name) == version_a
    assert len(store.get_history(test_dataset.name)) == 1
