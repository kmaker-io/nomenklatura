from pathlib import Path
from tempfile import NamedTemporaryFile
from followthemoney import model
from nomenklatura.index import Index

DAIMLER = "66ce9f62af8c7d329506da41cb7c36ba058b3d28"


def test_index_build(dloader):
    index = Index(dloader)
    assert len(index) == 0, index.terms
    assert len(index.inverted) == 0, index.inverted
    index.build()
    assert len(index) == 95, len(index.terms)


def test_index_persist(dloader, dindex):
    with NamedTemporaryFile("w") as fh:
        path = Path(fh.name)
        dindex.save(path)
        loaded = Index.load(dloader, path)
    assert len(dindex.inverted) == len(loaded.inverted), (dindex, loaded)
    assert len(dindex) == len(loaded), (dindex, loaded)

    path.unlink(missing_ok=True)
    empty = Index.load(dloader, path)
    assert len(empty) == len(loaded), (empty, loaded)


def test_index_search(dindex):
    query = model.make_entity("Person")
    query.add("name", "Susanne Klatten")
    results = list(dindex.match_entities(query))
    assert len(results), len(results)
    first = results[0][0]
    assert first.schema == query.schema, first.schema
    assert "Klatten" in first.caption

    query = model.make_entity("Person")
    query.add("name", "Henry Ford")
    results = list(dindex.match(query))
    assert len(results), len(results)

    query = model.make_entity("Company")
    query.add("name", "Susanne Klatten")
    results = list(dindex.match_entities(query))
    assert len(results), len(results)
    first = results[0][0]
    assert first.schema != model.get("Person")
    assert "Klatten" not in first.caption

    query = model.make_entity("Address")
    assert not query.schema.matchable
    query.add("full", "Susanne Klatten")
    results = list(dindex.match(query))
    assert 0 == len(results), len(results)


def test_index_filter(dloader, dindex):
    query = dloader.get_entity(DAIMLER)
    query.id = None
    query.schema = model.get("Person")

    results = list(dindex.match_entities(query))
    for result, _ in results:
        assert not result.schema.is_a("Organization"), result.schema
