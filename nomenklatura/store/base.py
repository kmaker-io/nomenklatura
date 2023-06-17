from types import TracebackType
from typing import Optional, Generator, List, Tuple, Generic, Type
from followthemoney.property import Property
from followthemoney.types import registry

from nomenklatura.dataset import DS
from nomenklatura.resolver import Resolver, StrIdent
from nomenklatura.statement import Statement
from nomenklatura.entity import CE, CompositeEntity


class Store(Generic[DS, CE]):
    """A data storage and retrieval mechanism for statement-based entity data. Essentially,
    this is a triple store which can be implemented using various backends."""

    def __init__(
        self,
        dataset: DS,
        resolver: Resolver[CE],
    ):
        self.dataset = dataset
        self.resolver = resolver

    def writer(self) -> "Writer[DS, CE]":
        raise NotImplementedError()

    def view(self, scope: DS, external: bool = False) -> "View[DS, CE]":
        raise NotImplementedError()

    def default_view(self, external: bool = False) -> "View[DS, CE]":
        return self.view(self.dataset, external=external)

    def assemble(self, statements: List[Statement]) -> Optional[CE]:
        if not len(statements):
            return None
        for stmt in statements:
            if stmt.prop_type == registry.entity.name:
                stmt.value = self.resolver.get_canonical(stmt.value)
        entity = CompositeEntity.from_statements(statements)
        if entity.id is not None:
            entity.extra_referents.update(self.resolver.get_referents(entity.id))
        return entity  # type: ignore

    def update(self, id: StrIdent) -> None:
        canonical_id = self.resolver.get_canonical(id)
        with self.writer() as writer:
            for referent in self.resolver.get_referents(canonical_id):
                for stmt in writer.pop(referent):
                    stmt.canonical_id = canonical_id
                    writer.add_statement(stmt)


class Writer(Generic[DS, CE]):
    """Bulk writing operations."""

    def __init__(self, store: Store[DS, CE]):
        self.store = store

    def add_statement(self, stmt: Statement) -> None:
        raise NotImplementedError()

    def add_entity(self, entity: CE) -> None:
        for stmt in entity.statements:
            self.add_statement(stmt)

    def pop(self, entity_id: str) -> List[Statement]:
        raise NotImplementedError()

    def flush(self) -> None:
        pass

    def __enter__(self) -> "Writer[DS, CE]":
        return self

    def __exit__(
        self,
        type: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.flush()


class View(Generic[DS, CE]):
    def __init__(self, store: Store[DS, CE], scope: DS, external: bool = False):
        self.store = store
        self.scope = scope
        self.scope_names = scope.scope_names
        self.external = external

    def get_entity(self, id: str) -> Optional[CE]:
        raise NotImplementedError()

    def get_inverted(self, id: str) -> Generator[Tuple[Property, CE], None, None]:
        raise NotImplementedError()

    def get_adjacent(
        self, entity: CE, inverted: bool = True
    ) -> Generator[Tuple[Property, CE], None, None]:
        for prop, value in entity.itervalues():
            if prop.type == registry.entity:
                child = self.get_entity(value)
                if child is not None:
                    yield prop, child

        if inverted and entity.id is not None:
            for prop, adjacent in self.get_inverted(entity.id):
                yield prop, adjacent

    def entities(self) -> Generator[CE, None, None]:
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"<View({self.scope!r})>"
