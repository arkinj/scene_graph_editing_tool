"""
Tests for SceneGraphModel.

These tests exercise the model's CRUD methods, signal emissions, selection
state, and layer visibility.  They run against a live Neo4j instance and
use a fresh database per test (via the ``model`` fixture).

Signal assertions use a simple SignalSpy helper that records emissions,
avoiding a dependency on pytest-qt.
"""

import neo4j
import pytest
from heracles import constants
from PySide6.QtWidgets import QApplication

from sget.backend.scene_graph_model import SceneGraphModel

# ---------------------------------------------------------------------------
# Qt app — PySide6 requires a QApplication for signals to work.
# Created once per test session.
# ---------------------------------------------------------------------------
_app = None


@pytest.fixture(scope="session", autouse=True)
def qapp():
    global _app
    _app = QApplication.instance() or QApplication([])
    yield _app


# ---------------------------------------------------------------------------
# Signal spy helper
# ---------------------------------------------------------------------------


class SignalSpy:
    """Records all emissions of a Qt signal for later assertion.

    Usage::

        spy = SignalSpy(model.node_added)
        model.add_node(...)
        assert len(spy.calls) == 1
        assert spy.calls[0] == ("o(0)", "Object")
    """

    def __init__(self, signal):
        self.calls = []
        signal.connect(lambda *args: self.calls.append(args))


# ---------------------------------------------------------------------------
# Connection settings
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
def model():
    """Provide a SceneGraphModel connected to a clean Neo4j database."""
    m = SceneGraphModel()
    m.connect(NEO4J_URI, "neo4j", "neo4j_pw")

    # Clear the database and recreate indexes.
    m._db.execute("MATCH (n) DETACH DELETE n")
    for name, label in [
        ("object_node_symbol", constants.OBJECTS),
        ("place_node_symbol", constants.PLACES),
        ("mesh_place_node_symbol", constants.MESH_PLACES),
        ("room_node_symbol", constants.ROOMS),
        ("building_node_symbol", constants.BUILDINGS),
    ]:
        _try_drop_index(m._db, name)
        m._db.execute(f"CREATE INDEX {name} FOR (n:{label}) ON (n.nodeSymbol)")

    yield m

    m.disconnect()


def _add_sample_place(model, symbol="p(0)", x=1.0, y=2.0, z=3.0):
    """Helper to add a Place node without verbose prop dicts everywhere."""
    model.add_node(
        constants.PLACES,
        symbol,
        {
            "pos_x": x,
            "pos_y": y,
            "pos_z": z,
        },
    )


def _add_sample_object(model, symbol="o(0)", x=0.0, y=0.0, z=0.0):
    """Helper to add an Object node with minimal required properties."""
    model.add_node(
        constants.OBJECTS,
        symbol,
        {
            "pos_x": x,
            "pos_y": y,
            "pos_z": z,
            "bbox_x": x,
            "bbox_y": y,
            "bbox_z": z,
            "bbox_l": 1.0,
            "bbox_w": 1.0,
            "bbox_h": 1.0,
            "class": "box",
            "name": f"test_{symbol}",
        },
    )


def _add_sample_room(model, symbol="R(0)", x=0.0, y=0.0, z=0.0):
    """Helper to add a Room node."""
    model.add_node(
        constants.ROOMS,
        symbol,
        {
            "pos_x": x,
            "pos_y": y,
            "pos_z": z,
            "class": "lounge",
        },
    )


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------


class TestConnection:
    def test_connect_and_disconnect(self):
        m = SceneGraphModel()
        assert not m.connected

        spy = SignalSpy(m.connection_changed)
        m.connect(NEO4J_URI, "neo4j", "neo4j_pw")
        assert m.connected
        assert spy.calls == [(True,)]

        m.disconnect()
        assert not m.connected
        assert spy.calls == [(True,), (False,)]

    def test_operations_require_connection(self):
        m = SceneGraphModel()
        with pytest.raises(RuntimeError, match="Not connected"):
            m.add_node(constants.PLACES, "p(0)", {"pos_x": 0, "pos_y": 0, "pos_z": 0})


# ---------------------------------------------------------------------------
# Node CRUD tests
# ---------------------------------------------------------------------------


class TestNodeCRUD:
    def test_add_node_populates_cache(self, model):
        _add_sample_place(model)

        cached = model.get_node("p(0)")
        assert cached is not None
        assert cached["nodeSymbol"] == "p(0)"

    def test_add_node_emits_signal(self, model):
        spy = SignalSpy(model.node_added)
        _add_sample_place(model)

        assert len(spy.calls) == 1
        assert spy.calls[0] == ("p(0)", constants.PLACES)

    def test_add_node_sets_layer(self, model):
        _add_sample_place(model)
        assert model.get_node_layer("p(0)") == constants.PLACES

    def test_remove_node(self, model):
        _add_sample_place(model)
        spy = SignalSpy(model.node_removed)

        model.remove_node("p(0)")

        assert model.get_node("p(0)") is None
        assert len(spy.calls) == 1
        assert spy.calls[0] == ("p(0)", constants.PLACES)

    def test_remove_node_clears_connected_edges(self, model):
        """Removing a node should also remove its edges from the cache."""
        _add_sample_room(model)
        _add_sample_place(model)
        model.add_edge("R(0)", "p(0)")

        edge_spy = SignalSpy(model.edge_removed)
        model.remove_node("R(0)")

        assert len(model.get_edges()) == 0
        assert len(edge_spy.calls) == 1

    def test_remove_node_clears_selection(self, model):
        _add_sample_place(model)
        model.set_selection(["p(0)"])

        model.remove_node("p(0)")
        assert model.selected == []

    def test_update_node(self, model):
        _add_sample_object(model)
        spy = SignalSpy(model.node_updated)

        model.update_node("o(0)", {"name": "updated_box"})

        cached = model.get_node("o(0)")
        assert cached["name"] == "updated_box"
        assert len(spy.calls) == 1
        assert spy.calls[0] == ("o(0)", constants.OBJECTS)

    def test_update_node_point3d(self, model):
        """Test updating a Point3D property via the model.

        This is the code path the property panel's Apply button exercises:
        the "pos" spinboxes map to "center" in Neo4j, which is a Point3D.
        The model must pass it through neo4j_crud.update_node, which wraps
        the value in point().  The round-trip must preserve the coordinates.
        """
        _add_sample_place(model)

        model.update_node("p(0)", {"center": [99.0, 88.0, 77.0]})

        cached = model.get_node("p(0)")
        # Neo4j returns CartesianPoint, which behaves like a sequence.
        import numpy as np

        assert np.allclose(cached["center"], [99.0, 88.0, 77.0])

    def test_update_node_mixed_props(self, model):
        """Update both scalar and Point3D properties in one model call."""
        _add_sample_object(model)

        model.update_node(
            "o(0)",
            {
                "name": "new_name",
                "center": [10.0, 20.0, 30.0],
                "bbox_dim": [2.0, 3.0, 4.0],
            },
        )

        cached = model.get_node("o(0)")
        import numpy as np

        assert cached["name"] == "new_name"
        assert np.allclose(cached["center"], [10.0, 20.0, 30.0])
        assert np.allclose(cached["bbox_dim"], [2.0, 3.0, 4.0])

    def test_node_count(self, model):
        assert model.node_count(constants.PLACES) == 0
        _add_sample_place(model, "p(0)")
        _add_sample_place(model, "p(1)", x=5.0)
        assert model.node_count(constants.PLACES) == 2

    def test_get_nodes_by_layer(self, model):
        _add_sample_place(model, "p(0)")
        _add_sample_place(model, "p(1)", x=5.0)
        _add_sample_object(model, "o(0)")

        places = model.get_nodes_by_layer(constants.PLACES)
        assert len(places) == 2

        objects = model.get_nodes_by_layer(constants.OBJECTS)
        assert len(objects) == 1


# ---------------------------------------------------------------------------
# Edge CRUD tests
# ---------------------------------------------------------------------------


class TestEdgeCRUD:
    def test_add_interlayer_edge(self, model):
        _add_sample_room(model)
        _add_sample_place(model)
        spy = SignalSpy(model.edge_added)

        model.add_edge("R(0)", "p(0)")

        edges = model.get_edges()
        assert len(edges) == 1
        assert edges[0]["edge_type"] == "CONTAINS"
        assert len(spy.calls) == 1
        assert spy.calls[0] == ("R(0)", "p(0)", "CONTAINS")

    def test_add_intralayer_edge(self, model):
        _add_sample_place(model, "p(0)")
        _add_sample_place(model, "p(1)", x=5.0)

        model.add_edge("p(0)", "p(1)")

        edges = model.get_edges()
        assert len(edges) == 1
        assert edges[0]["edge_type"] == "PLACE_CONNECTED"

    def test_remove_edge(self, model):
        _add_sample_room(model)
        _add_sample_place(model)
        model.add_edge("R(0)", "p(0)")
        spy = SignalSpy(model.edge_removed)

        model.remove_edge("R(0)", "p(0)")

        assert len(model.get_edges()) == 0
        assert len(spy.calls) == 1
        assert spy.calls[0] == ("R(0)", "p(0)", "CONTAINS")

    def test_add_edge_unknown_node_raises(self, model):
        _add_sample_place(model)
        with pytest.raises(ValueError, match="not found"):
            model.add_edge("p(0)", "NONEXISTENT")


# ---------------------------------------------------------------------------
# Selection tests
# ---------------------------------------------------------------------------


class TestSelection:
    def test_set_selection(self, model):
        spy = SignalSpy(model.selection_changed)

        model.set_selection(["p(0)", "p(1)"])
        assert model.selected == ["p(0)", "p(1)"]
        assert len(spy.calls) == 1

    def test_clear_selection(self, model):
        model.set_selection(["p(0)"])
        spy = SignalSpy(model.selection_changed)

        model.clear_selection()
        assert model.selected == []
        assert len(spy.calls) == 1

    def test_clear_empty_selection_is_noop(self, model):
        spy = SignalSpy(model.selection_changed)
        model.clear_selection()
        assert len(spy.calls) == 0

    def test_toggle_selection(self, model):
        model.toggle_selection("p(0)")
        assert model.selected == ["p(0)"]

        model.toggle_selection("p(1)")
        assert model.selected == ["p(0)", "p(1)"]

        model.toggle_selection("p(0)")
        assert model.selected == ["p(1)"]


# ---------------------------------------------------------------------------
# Layer visibility tests
# ---------------------------------------------------------------------------


class TestLayerVisibility:
    def test_default_all_visible(self, model):
        for label, _ in [
            (constants.BUILDINGS, 5),
            (constants.ROOMS, 4),
            (constants.PLACES, 3),
            (constants.OBJECTS, 2),
        ]:
            assert model.is_layer_visible(label)

    def test_toggle_visibility(self, model):
        spy = SignalSpy(model.layer_visibility_changed)

        model.set_layer_visibility(constants.OBJECTS, False)
        assert not model.is_layer_visible(constants.OBJECTS)
        assert spy.calls == [(constants.OBJECTS, False)]

        model.set_layer_visibility(constants.OBJECTS, True)
        assert model.is_layer_visible(constants.OBJECTS)
        assert spy.calls == [(constants.OBJECTS, False), (constants.OBJECTS, True)]

    def test_no_signal_if_unchanged(self, model):
        spy = SignalSpy(model.layer_visibility_changed)
        model.set_layer_visibility(constants.OBJECTS, True)  # Already True
        assert len(spy.calls) == 0
