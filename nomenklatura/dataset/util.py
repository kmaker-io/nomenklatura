from typing import Any, Optional, Dict
from normality import stringify
from followthemoney.types.common import PropertyType

from nomenklatura.exceptions import MetadataException


def type_check(type_: PropertyType, value: Any) -> Optional[str]:
    text = stringify(value)
    if text is None:
        return None
    cleaned = type_.clean_text(text)
    if cleaned is None:
        raise MetadataException("Invalid %s: %r" % (type_.name, value))
    return cleaned


def type_require(type_: PropertyType, value: Any) -> str:
    text = stringify(value)
    if text is None:
        raise MetadataException("Invalid %s: %r" % (type_.name, value))
    cleaned = type_.clean_text(text)
    if cleaned is None:
        raise MetadataException("Invalid %s: %r" % (type_.name, value))
    return cleaned


def cleanup(data: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in list(data.items()):
        if value is None:
            data.pop(key)
    return data


class Named(object):
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: Any) -> bool:
        try:
            return not not self.name == other.name
        except AttributeError:
            return False

    def __lt__(self, other: Any) -> bool:
        return self.name.__lt__(other.name)

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.name))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.name!r})>"
