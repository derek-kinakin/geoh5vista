"""Detached native hierarchy identity, traversal, and structural invariants."""

from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from geoh5vista.models import HierarchyEntity, WorkspaceHierarchy


def uid(index):
    return str(UUID(int=index))


def entity(index, parent=None, *, is_object=True, is_root=False, supported=True):
    return HierarchyEntity(
        uid=uid(index),
        name="same",
        entity_type="Points" if is_object else "ContainerGroup",
        parent_uid=uid(parent) if parent is not None else None,
        is_object=is_object,
        is_root=is_root,
        conversion_supported=supported,
    )


def test_hierarchy_lookup_and_depth_first_branch_traversal():
    nodes = (
        entity(10, is_object=False, is_root=True, supported=False),
        entity(20, 10, is_object=False, supported=False),
        entity(1, 20),
        entity(30, 10, supported=False),
    )
    hierarchy = WorkspaceHierarchy(2.1, nodes)
    assert hierarchy.nodes == nodes
    assert hierarchy.root_uid == uid(10)
    assert hierarchy.top_level_uids == (uid(10),)
    assert hierarchy.node(UUID(int=1)) is nodes[2]
    assert hierarchy.node("{" + uid(1) + "}") is nodes[2]
    assert hierarchy.children(uid(10)) == (nodes[1], nodes[3])
    assert hierarchy.children(uid(1)) == ()
    assert tuple(hierarchy.descendants(uid(10))) == nodes[1:]
    assert tuple(hierarchy.descendants(uid(20), include_self=True)) == nodes[1:3]
    assert tuple(hierarchy.descendants(uid(30))) == ()
    assert tuple(hierarchy.descendants(uid(30), include_self=True)) == (nodes[3],)


def test_rootless_forest_keeps_top_level_identities_and_order():
    nodes = (entity(10), entity(1, 10), entity(20))
    hierarchy = WorkspaceHierarchy(1.0, nodes)
    assert hierarchy.root_uid is None
    assert hierarchy.top_level_uids == (uid(10), uid(20))
    assert tuple(hierarchy.descendants(uid(10), include_self=True)) == nodes[:2]
    assert hierarchy.node(uid(20)).parent_uid is None


def test_branch_selection_deduplicates_and_preserves_discovery_order():
    nodes = (
        entity(10, is_object=False, is_root=True, supported=False),
        entity(20, 10, is_object=False, supported=False),
        entity(1, 20),
        entity(30, 10, supported=False),
    )
    hierarchy = WorkspaceHierarchy(2.1, nodes)
    assert hierarchy.select([uid(1), UUID(int=20), uid(1)]) == nodes[1:3]
    assert hierarchy.select([uid(30), uid(20)]) == nodes[1:]
    assert hierarchy.select([uid(1), uid(20), uid(10)]) == nodes
    assert hierarchy.select([]) == ()
    with pytest.raises(KeyError):
        hierarchy.select([uid(999)])
    with pytest.raises(ValueError):
        hierarchy.select(["invalid"])


def test_empty_hierarchy_is_a_valid_forest():
    hierarchy = WorkspaceHierarchy(2.1, ())
    assert hierarchy.nodes == ()
    assert hierarchy.top_level_uids == ()
    assert hierarchy.root_uid is None
    assert dict(hierarchy.by_uid) == {}


def test_hierarchy_records_and_relationships_are_immutable():
    node = entity(1)
    hierarchy = WorkspaceHierarchy(2.1, (node,))
    with pytest.raises(FrozenInstanceError):
        node.name = "changed"
    with pytest.raises(FrozenInstanceError):
        hierarchy.nodes = ()
    with pytest.raises(TypeError):
        hierarchy.by_uid[node.uid] = entity(2)
    assert not hasattr(node, "__dict__")
    assert not hasattr(hierarchy, "__dict__")


def test_hierarchy_entity_ids_are_canonical():
    node = HierarchyEntity(
        uid="{" + uid(1).upper() + "}",
        name="same",
        entity_type="Points",
        parent_uid="{" + uid(2).upper() + "}",
        is_object=True,
    )
    assert node.uid == uid(1)
    assert node.parent_uid == uid(2)
    with pytest.raises(ValueError):
        HierarchyEntity("invalid", "same", "Points", None, True)


@pytest.mark.parametrize(
    "nodes, message",
    [
        ((entity(1), entity(1)), "Duplicate"),
        ((entity(1, 2),), "missing hierarchy parent"),
        ((entity(1, 1),), "Cyclic"),
        ((entity(1, 2), entity(2, 1)), "Cyclic"),
        ((entity(1, is_root=True), entity(2, is_root=True)), "Multiple"),
        ((entity(1), entity(2, 1, is_root=True)), "root has a parent"),
    ],
)
def test_invalid_hierarchy_relationships_raise(nodes, message):
    with pytest.raises(ValueError, match=message):
        WorkspaceHierarchy(2.1, nodes)


@pytest.mark.parametrize("version", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_hierarchy_version_raises(version):
    with pytest.raises(ValueError, match="format version"):
        WorkspaceHierarchy(version, ())


@pytest.mark.parametrize("operation", ["node", "children", "descendants"])
def test_unknown_hierarchy_identity_raises(operation):
    hierarchy = WorkspaceHierarchy(2.1, (entity(1),))
    with pytest.raises(KeyError):
        result = getattr(hierarchy, operation)(uid(2))
        if operation == "descendants":
            tuple(result)
    with pytest.raises(ValueError):
        result = getattr(hierarchy, operation)("invalid")
        if operation == "descendants":
            tuple(result)


def test_deep_hierarchy_traversal_does_not_require_recursion():
    nodes = tuple(
        entity(index, index - 1 if index > 1 else None) for index in range(1, 1501)
    )
    hierarchy = WorkspaceHierarchy(2.1, nodes)
    assert tuple(hierarchy.descendants(uid(1), include_self=True)) == nodes
