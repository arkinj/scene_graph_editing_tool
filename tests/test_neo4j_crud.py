"""
Tests for the Neo4j CRUD layer.

These tests run against a live Neo4j instance (Docker) and exercise every
function in sget.backend.neo4j_crud.  Each test gets a clean database via
the ``db`` fixture, which clears all nodes/edges and recreates indexes
before yielding the connection.

The tests follow the same patterns as heracles' own test suite
(~/software/mit/sget/heracles/heracles/tests/test_db.py).
"""

import neo4j
import numpy as np
import pytest
from heracles import constants
from heracles.query_interface import Neo4jWrapper

from sget.backend.neo4j_crud import (
    INTERLAYER_EDGE_TYPE,
    create_edge,
    create_node,
    delete_edge,
    delete_node,
    determine_edge_type,
    get_all_edges,
    get_all_nodes,
    get_node,
    update_node,
)

# ---------------------------------------------------------------------------
# Connection settings — matches heracles' test defaults
# ---------------------------------------------------------------------------
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_AUTH = ("neo4j", "neo4j_pw")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _try_drop_index(db, index_name):
    try:
        db.execute(f"DROP INDEX {index_name}")
    except neo4j.exceptions.DatabaseError:
        pass


@pytest.fixture()
def db():
    """Provide a clean Neo4j database for each test.

    Clears all data, recreates the nodeSymbol indexes (matching heracles'
    initialize_db), and yields the connection.  Per-test isolation ensures
    tests don't interfere with each other.
    """
    wrapper = Neo4jWrapper(NEO4J_URI, NEO4J_AUTH, atomic_queries=True)
    wrapper.connect()

    # Clear everything
    wrapper.execute("MATCH (n) DETACH DELETE n")

    # Recreate indexes (same as heracles.graph_interface.initialize_db)
    for name, label in [
        ("object_node_symbol", constants.OBJECTS),
        ("place_node_symbol", constants.PLACES),
        ("mesh_place_node_symbol", constants.MESH_PLACES),
        ("room_node_symbol", constants.ROOMS),
        ("building_node_symbol", constants.BUILDINGS),
    ]:
        _try_drop_index(wrapper, name)
        wrapper.execute(f"CREATE INDEX {name} FOR (n:{label}) ON (n.nodeSymbol)")

    yield wrapper

    wrapper.close()


# ---------------------------------------------------------------------------
# Node creation tests
# ---------------------------------------------------------------------------


class TestCreateNode:
    def test_create_object(self, db):
        create_node(
            db,
            constants.OBJECTS,
            "o(0)",
            {
                "pos_x": 1.0,
                "pos_y": 2.0,
                "pos_z": 3.0,
                "bbox_x": 1.0,
                "bbox_y": 2.0,
                "bbox_z": 3.0,
                "bbox_l": 0.5,
                "bbox_w": 0.5,
                "bbox_h": 0.5,
                "class": "box",
                "name": "test_box",
            },
        )

        result = db.query("MATCH (n:Object {nodeSymbol: 'o(0)'}) RETURN n")
        assert len(result) == 1
        node = result[0]["n"]
        assert node["nodeSymbol"] == "o(0)"
        assert node["class"] == "box"
        assert node["name"] == "test_box"
        assert np.allclose(node["center"], [1.0, 2.0, 3.0])
        assert np.allclose(node["bbox_center"], [1.0, 2.0, 3.0])
        assert np.allclose(node["bbox_dim"], [0.5, 0.5, 0.5])

    def test_create_place(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": -1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        result = db.query("MATCH (n:Place {nodeSymbol: 'p(0)'}) RETURN n")
        assert len(result) == 1
        assert np.allclose(result[0]["n"]["center"], [-1.0, 0.0, 0.0])

    def test_create_mesh_place(self, db):
        create_node(
            db,
            constants.MESH_PLACES,
            "P(0)",
            {
                "pos_x": 0.0,
                "pos_y": 1.0,
                "pos_z": 0.0,
                "class": "ground",
            },
        )

        result = db.query("MATCH (n:MeshPlace {nodeSymbol: 'P(0)'}) RETURN n")
        assert len(result) == 1
        assert result[0]["n"]["class"] == "ground"

    def test_create_room(self, db):
        create_node(
            db,
            constants.ROOMS,
            "R(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "class": "lounge",
            },
        )

        result = db.query("MATCH (n:Room {nodeSymbol: 'R(0)'}) RETURN n")
        assert len(result) == 1
        assert result[0]["n"]["class"] == "lounge"

    def test_create_building(self, db):
        create_node(
            db,
            constants.BUILDINGS,
            "B(0)",
            {
                "pos_x": 10.0,
                "pos_y": 20.0,
                "pos_z": 30.0,
            },
        )

        result = db.query("MATCH (n:Building {nodeSymbol: 'B(0)'}) RETURN n")
        assert len(result) == 1
        assert np.allclose(result[0]["n"]["center"], [10.0, 20.0, 30.0])

    def test_create_unknown_layer_raises(self, db):
        with pytest.raises(ValueError, match="Unknown layer label"):
            create_node(db, "Nonexistent", "X(0)", {"pos_x": 0, "pos_y": 0, "pos_z": 0})


# ---------------------------------------------------------------------------
# Node read tests
# ---------------------------------------------------------------------------


class TestGetNode:
    def test_get_existing_node(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(5)",
            {
                "pos_x": 3.0,
                "pos_y": 4.0,
                "pos_z": 5.0,
            },
        )

        result = get_node(db, constants.PLACES, "p(5)")
        assert result is not None
        assert result["nodeSymbol"] == "p(5)"
        assert np.allclose(result["center"], [3.0, 4.0, 5.0])

    def test_get_nonexistent_node_returns_none(self, db):
        result = get_node(db, constants.PLACES, "p(999)")
        assert result is None

    def test_get_all_nodes(self, db):
        for i in range(3):
            create_node(
                db,
                constants.PLACES,
                f"p({i})",
                {
                    "pos_x": float(i),
                    "pos_y": 0.0,
                    "pos_z": 0.0,
                },
            )

        results = get_all_nodes(db, constants.PLACES)
        assert len(results) == 3
        symbols = {r["nodeSymbol"] for r in results}
        assert symbols == {"p(0)", "p(1)", "p(2)"}

    def test_get_all_nodes_empty_layer(self, db):
        results = get_all_nodes(db, constants.BUILDINGS)
        assert results == []


# ---------------------------------------------------------------------------
# Node update tests
# ---------------------------------------------------------------------------


class TestUpdateNode:
    def test_update_scalar_property(self, db):
        create_node(
            db,
            constants.OBJECTS,
            "o(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "bbox_x": 0.0,
                "bbox_y": 0.0,
                "bbox_z": 0.0,
                "bbox_l": 1.0,
                "bbox_w": 1.0,
                "bbox_h": 1.0,
                "class": "box",
                "name": "old_name",
            },
        )

        update_node(db, constants.OBJECTS, "o(0)", {"name": "new_name"})

        result = get_node(db, constants.OBJECTS, "o(0)")
        assert result["name"] == "new_name"
        # Other properties unchanged
        assert result["class"] == "box"

    def test_update_point3d_property(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        update_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "center": [10.0, 20.0, 30.0],
            },
        )

        result = get_node(db, constants.PLACES, "p(0)")
        assert np.allclose(result["center"], [10.0, 20.0, 30.0])

    def test_update_mixed_properties(self, db):
        """Update both scalar and Point3D properties in one call."""
        create_node(
            db,
            constants.OBJECTS,
            "o(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "bbox_x": 0.0,
                "bbox_y": 0.0,
                "bbox_z": 0.0,
                "bbox_l": 1.0,
                "bbox_w": 1.0,
                "bbox_h": 1.0,
                "class": "box",
                "name": "thing",
            },
        )

        update_node(
            db,
            constants.OBJECTS,
            "o(0)",
            {
                "name": "updated_thing",
                "center": [5.0, 6.0, 7.0],
                "bbox_dim": [2.0, 3.0, 4.0],
            },
        )

        result = get_node(db, constants.OBJECTS, "o(0)")
        assert result["name"] == "updated_thing"
        assert np.allclose(result["center"], [5.0, 6.0, 7.0])
        assert np.allclose(result["bbox_dim"], [2.0, 3.0, 4.0])
        # Unchanged
        assert np.allclose(result["bbox_center"], [0.0, 0.0, 0.0])

    def test_update_empty_props_is_noop(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 1.0,
                "pos_y": 2.0,
                "pos_z": 3.0,
            },
        )

        update_node(db, constants.PLACES, "p(0)", {})

        result = get_node(db, constants.PLACES, "p(0)")
        assert np.allclose(result["center"], [1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# Node deletion tests
# ---------------------------------------------------------------------------


class TestDeleteNode:
    def test_delete_node(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        assert get_node(db, constants.PLACES, "p(0)") is not None

        delete_node(db, constants.PLACES, "p(0)")
        assert get_node(db, constants.PLACES, "p(0)") is None

    def test_delete_node_removes_edges(self, db):
        """DETACH DELETE should remove all connected edges."""
        create_node(
            db,
            constants.ROOMS,
            "R(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "class": "lounge",
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        create_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(0)")

        # Verify edge exists
        edges = get_all_edges(db)
        assert len(edges) == 1

        # Delete the room — edge should be gone too
        delete_node(db, constants.ROOMS, "R(0)")
        edges = get_all_edges(db)
        assert len(edges) == 0
        # Place should still exist
        assert get_node(db, constants.PLACES, "p(0)") is not None


# ---------------------------------------------------------------------------
# Edge tests
# ---------------------------------------------------------------------------


class TestEdges:
    def test_determine_intralayer_edge_type(self):
        assert determine_edge_type(constants.OBJECTS, constants.OBJECTS) == "OBJECT_CONNECTED"
        assert determine_edge_type(constants.PLACES, constants.PLACES) == "PLACE_CONNECTED"
        assert determine_edge_type(constants.ROOMS, constants.ROOMS) == "ROOM_CONNECTED"

    def test_determine_interlayer_edge_type(self):
        assert determine_edge_type(constants.ROOMS, constants.PLACES) == INTERLAYER_EDGE_TYPE
        assert determine_edge_type(constants.PLACES, constants.OBJECTS) == INTERLAYER_EDGE_TYPE

    def test_create_interlayer_edge(self, db):
        create_node(
            db,
            constants.ROOMS,
            "R(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "class": "lounge",
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        create_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(0)")

        # Verify via transitive CONTAINS query (same pattern as heracles tests)
        result = db.query("MATCH (r:Room {nodeSymbol: 'R(0)'})-[:CONTAINS]->(p:Place) RETURN p")
        assert len(result) == 1
        assert result[0]["p"]["nodeSymbol"] == "p(0)"

    def test_create_intralayer_edge(self, db):
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(1)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        create_edge(db, constants.PLACES, "p(0)", constants.PLACES, "p(1)")

        result = db.query(
            "MATCH (a:Place {nodeSymbol: 'p(0)'})-[:PLACE_CONNECTED]->(b:Place) RETURN b"
        )
        assert len(result) == 1
        assert result[0]["b"]["nodeSymbol"] == "p(1)"

    def test_create_edge_with_explicit_type(self, db):
        """Caller can override the auto-inferred edge type."""
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(1)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        create_edge(
            db,
            constants.PLACES,
            "p(0)",
            constants.PLACES,
            "p(1)",
            edge_type="CUSTOM_EDGE",
        )

        result = db.query(
            "MATCH (a:Place {nodeSymbol: 'p(0)'})-[:CUSTOM_EDGE]->(b:Place) RETURN b"
        )
        assert len(result) == 1

    def test_delete_edge(self, db):
        create_node(
            db,
            constants.ROOMS,
            "R(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "class": "lounge",
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        create_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(0)")

        # Edge exists
        assert len(get_all_edges(db)) == 1

        delete_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(0)")

        # Edge gone, nodes still exist
        assert len(get_all_edges(db)) == 0
        assert get_node(db, constants.ROOMS, "R(0)") is not None
        assert get_node(db, constants.PLACES, "p(0)") is not None

    def test_get_all_edges(self, db):
        """Build a small hierarchy and verify get_all_edges returns them all."""
        create_node(
            db,
            constants.ROOMS,
            "R(0)",
            {
                "pos_x": 0.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
                "class": "hallway",
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(0)",
            {
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )
        create_node(
            db,
            constants.PLACES,
            "p(1)",
            {
                "pos_x": 2.0,
                "pos_y": 0.0,
                "pos_z": 0.0,
            },
        )

        create_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(0)")
        create_edge(db, constants.ROOMS, "R(0)", constants.PLACES, "p(1)")
        create_edge(db, constants.PLACES, "p(0)", constants.PLACES, "p(1)")

        edges = get_all_edges(db)
        assert len(edges) == 3

        # Check structure of returned dicts
        edge_types = {e["edge_type"] for e in edges}
        assert "CONTAINS" in edge_types
        assert "PLACE_CONNECTED" in edge_types

        for edge in edges:
            assert "from_label" in edge
            assert "from_symbol" in edge
            assert "to_label" in edge
            assert "to_symbol" in edge
            assert "edge_type" in edge
