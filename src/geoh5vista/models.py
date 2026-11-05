"""Detached metadata and native hierarchy records, independent of file handles and VTK."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Literal
from uuid import UUID

__all__ = ("EntityMetadata", "HierarchyEntity", "WorkspaceHierarchy")

_KINDS = frozenset(("root", "group", "object"))


@dataclass(frozen=True, slots=True)
class EntityMetadata:
    """Detached native entity metadata returned by :func:`catalog_geoh5`.

    UIDs are canonical UUID strings. Colour is RGB, or ``None`` if absent.
    Conversion support describes the type, not the validity of its geometry.
    ``parent_uid`` may identify a root or organizational group not cataloged.
    """

    uid: str
    name: str
    entity_type: str
    parent_uid: str | None
    visible: bool
    colour: tuple[int, int, int] | None
    conversion_supported: bool
    unsupported_reason: str | None


@dataclass(frozen=True, slots=True)
class HierarchyEntity:
    """Identity, parentage and display state of a native group or object.

    Not a generated VTK component. ``kind`` is ``"root"``, ``"group"`` or
    ``"object"``; ``concatenated`` marks objects stored inside a concatenator
    group. ``visible`` is the entity's own stored checkbox (missing means
    visible), independent of views and ancestors. ``colour`` is the object's
    stored Visual Parameters RGB, or ``None`` when absent, not loaded, or the
    entity is not an object. Attached data channels and property groups are
    deliberately excluded; they are discovered when entities are read.
    """

    uid: str
    name: str
    entity_type: str
    parent_uid: str | None
    kind: Literal["root", "group", "object"]
    conversion_supported: bool = False
    concatenated: bool = False
    visible: bool = True
    colour: tuple[int, int, int] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", str(UUID(str(self.uid))))
        if self.parent_uid is not None:
            object.__setattr__(self, "parent_uid", str(UUID(str(self.parent_uid))))
        if self.kind not in _KINDS:
            raise ValueError(f"Entity {self.uid}: invalid hierarchy kind {self.kind!r}.")
        if self.concatenated and self.kind != "object":
            raise ValueError(f"Entity {self.uid}: only objects can be concatenated.")
        if self.colour is not None:
            if self.kind != "object":
                raise ValueError(f"Entity {self.uid}: only objects have a colour.")
            colour = tuple(self.colour)
            if len(colour) != 3 or not all(
                isinstance(value, int) and 0 <= value <= 255 for value in colour
            ):
                raise ValueError(f"Entity {self.uid}: colour must be three 0-255 integers.")
            object.__setattr__(self, "colour", colour)

    @property
    def is_object(self) -> bool:
        return self.kind == "object"

    @property
    def is_root(self) -> bool:
        return self.kind == "root"


@dataclass(frozen=True, slots=True)
class WorkspaceHierarchy:
    """Immutable native tree or rootless forest in discovery order.

    Includes organizational groups and unsupported objects. Nodes, UID lookup,
    and child relationships remain usable after the source file closes.
    Attached data channels and property groups are not represented.
    """

    version: float
    nodes: tuple[HierarchyEntity, ...]
    by_uid: Mapping[str, HierarchyEntity] = field(init=False, repr=False, compare=False)
    top_level_uids: tuple[str, ...] = field(init=False)
    _children: Mapping[str, tuple[str, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isfinite(self.version) or self.version <= 0:
            raise ValueError("Invalid geoh5 format version.")
        nodes = tuple(self.nodes)
        by_uid = {node.uid: node for node in nodes}
        if len(by_uid) != len(nodes):
            raise ValueError("Duplicate hierarchy entity UIDs.")
        if sum(node.is_root for node in nodes) > 1:
            raise ValueError("Multiple hierarchy roots.")
        children: dict[str, list[str]] = {node.uid: [] for node in nodes}
        starts = []
        for node in nodes:
            if node.parent_uid is None:
                starts.append(node.uid)
            elif node.parent_uid not in by_uid:
                raise ValueError(
                    f"Entity {node.uid}: missing hierarchy parent {node.parent_uid}."
                )
            else:
                children[node.parent_uid].append(node.uid)
            if node.is_root and node.parent_uid is not None:
                raise ValueError(f"Entity {node.uid}: hierarchy root has a parent.")
        seen = set()
        pending = list(starts)
        while pending:
            uid = pending.pop()
            seen.add(uid)
            pending.extend(children[uid])
        if len(seen) != len(nodes):
            raise ValueError("Cyclic hierarchy has no top-level parent.")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "by_uid", MappingProxyType(by_uid))
        object.__setattr__(self, "top_level_uids", tuple(starts))
        object.__setattr__(
            self,
            "_children",
            MappingProxyType({uid: tuple(values) for uid, values in children.items()}),
        )

    @property
    def root_uid(self) -> str | None:
        """Return the stored root identity, or ``None`` for a rootless forest."""
        return next((node.uid for node in self.nodes if node.is_root), None)

    def node(self, uid: UUID | str) -> HierarchyEntity:
        """Look up a native entity by UUID; unknown identities raise ``KeyError``."""
        return self.by_uid[str(UUID(str(uid)))]

    def children(self, uid: UUID | str) -> tuple[HierarchyEntity, ...]:
        """Return immediate children in discovery order."""
        node = self.node(uid)
        return tuple(self.by_uid[child] for child in self._children[node.uid])

    def effectively_visible(self, uid: UUID | str) -> bool:
        """Whether the entity and every stored ancestor, including the root, are visible."""
        node = self.node(uid)
        while True:
            if not node.visible:
                return False
            if node.parent_uid is None:
                return True
            node = self.by_uid[node.parent_uid]

    def descendants(
        self,
        uid: UUID | str,
        *,
        include_self: bool = False,
    ) -> Iterator[HierarchyEntity]:
        """Traverse a branch depth-first without filtering unsupported entities."""
        node = self.node(uid)
        pending = (
            [node.uid] if include_self else list(reversed(self._children[node.uid]))
        )
        while pending:
            current = pending.pop()
            yield self.by_uid[current]
            pending.extend(reversed(self._children[current]))

    def select(self, uids: Iterable[UUID | str]) -> tuple[HierarchyEntity, ...]:
        """Expand and deduplicate selected branches, returning discovery order."""
        pending = [self.node(uid).uid for uid in uids]
        selected = set()
        while pending:
            current = pending.pop()
            if current in selected:
                continue
            selected.add(current)
            pending.extend(self._children[current])
        return tuple(node for node in self.nodes if node.uid in selected)
