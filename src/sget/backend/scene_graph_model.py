"""
Central model for the Scene Graph Editing Tool.

Design overview
===============
``SceneGraphModel`` is a QObject that serves as the single source of truth for
the entire application.  All views (2D graph, property panel, layer panel)
observe this model through Qt signals, and all mutations flow through it.

The model maintains two synchronized representations:

1. **Neo4j database** — the persistent store, accessed via our CRUD layer
   (``sget.backend.neo4j_crud``) for single-item operations and heracles'
   bulk functions for full load/export.

2. **In-memory cache** — dicts of node properties and edge tuples, populated
   from Neo4j on load.  Views read from this cache (fast) rather than
   querying Neo4j on every frame.  Mutations update both the cache and Neo4j,
   then emit signals so views can refresh.

Why not keep a spark_dsg.DynamicSceneGraph in memory?
-----------------------------------------------------
We considered holding the C++ DSG object as the live in-memory model, but:
- spark_dsg's pybind11 bindings are primarily designed for bulk construction
  and serialization, not fine-grained incremental mutation with change
  notification.
- We'd have to mirror every edit to both the DSG and Neo4j anyway.
- For save/export, we reconstruct the DSG from Neo4j via heracles'
  ``db_to_spark_dsg()`` — this is the same path heracles itself uses and
  keeps serialization consistent.

So the flow is: load JSON → push to Neo4j → populate cache → edit via cache+Neo4j
→ export Neo4j → save JSON.  The DSG is a transient object used only at the
load and save boundaries.

Selection and visibility
------------------------
Selection (which nodes are highlighted/shown in property panel) and layer
visibility (which layers are drawn) are UI concerns, but they need to be
shared across multiple views.  Rather than coupling views to each other, the
model owns this state and emits signals when it changes.  Any view can update
selection or visibility through the model, and all other views react.
"""

import spark_dsg
from heracles import constants
from heracles.graph_interface import (
    db_to_spark_dsg,
    initialize_db,
    spark_dsg_to_db,
)
from heracles.query_interface import Neo4jWrapper
from PySide6.QtCore import QObject, Signal

from sget.backend import neo4j_crud
from sget.utils.colors import LAYER_STYLES

# Derived from LAYER_STYLES — single source of truth for layer ordering.
# Used by load/save/cache methods that need (label, layer_id) tuples.
LAYER_ORDER = [(s.layer_label, s.layer_id) for s in LAYER_STYLES]

# Default metadata required by heracles for bulk load/export.
# Maps spark_dsg layer IDs to heracles label strings.
# This must be added to the DSG metadata before calling spark_dsg_to_db().
_DEFAULT_LAYER_ID_TO_HERACLES = {
    2: constants.OBJECTS,
    3: constants.PLACES,
    4: constants.ROOMS,
    5: constants.BUILDINGS,
    20: constants.MESH_PLACES,
    "3[1]": constants.MESH_PLACES,
}


class SceneGraphModel(QObject):
    """Central model that all views observe.

    Signals
    -------
    graph_loaded
        Emitted after a full graph load (from JSON or DB).  Views should
        rebuild their entire representation.
    node_added(node_symbol: str, layer_label: str)
        A single node was created.
    node_removed(node_symbol: str, layer_label: str)
        A single node was deleted (along with its edges).
    node_updated(node_symbol: str, layer_label: str)
        Properties on a node changed.
    edge_added(from_symbol: str, to_symbol: str, edge_type: str)
        An edge was created between two nodes.
    edge_removed(from_symbol: str, to_symbol: str, edge_type: str)
        An edge was deleted.
    selection_changed(selected: list)
        The set of selected node symbols changed.  ``selected`` is a list
        of nodeSymbol strings.
    layer_visibility_changed(layer_label: str, visible: bool)
        A layer's visibility was toggled.
    connection_changed(connected: bool)
        Neo4j connection state changed.
    """

    graph_loaded = Signal()
    node_added = Signal(str, str)
    node_removed = Signal(str, str)
    node_updated = Signal(str, str)
    edge_added = Signal(str, str, str)
    edge_removed = Signal(str, str, str)
    selection_changed = Signal(list)
    layer_visibility_changed = Signal(str, bool)
    interlayer_edges_visibility_changed = Signal(bool)
    connection_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Neo4j connection (None when disconnected / offline mode).
        self._db: Neo4jWrapper | None = None

        # In-memory cache, populated from Neo4j after load.
        # nodes: {node_symbol: {prop_name: value, ...}}
        # edges: list of {from_label, from_symbol, to_label, to_symbol, edge_type}
        self._nodes: dict[str, dict] = {}
        self._node_layers: dict[str, str] = {}  # node_symbol -> layer_label
        self._edges: list[dict] = []

        # Labelspace mappings — needed for heracles' bulk export.
        # label_to_semantic_id: {"box": 34, "tree": 2, ...}
        # room_label_to_semantic_id: {"lounge": 0, "hallway": 1, ...}
        self._label_to_semantic_id: dict[str, int] = {}
        self._room_label_to_semantic_id: dict[str, int] = {}

        # UI state shared across views.
        self._selected: list[str] = []
        self._layer_visibility: dict[str, bool] = {label: True for label, _ in LAYER_ORDER}
        self._show_interlayer_edges: bool = False  # Off by default — reduces visual clutter

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._db is not None

    def connect(self, uri: str, user: str, password: str, db_name: str = "neo4j"):
        """Establish a Neo4j connection.

        Raises on failure (bad credentials, unreachable server, etc.) — the
        caller (main window / connection dialog) should catch and display.
        """
        db = Neo4jWrapper(uri, (user, password), db_name=db_name, atomic_queries=True)
        db.connect()
        self._db = db
        self.connection_changed.emit(True)

    def disconnect(self):
        if self._db is not None:
            self._db.close()
            self._db = None
            self.connection_changed.emit(False)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def load_from_json(self, path: str):
        """Load a scene graph JSON file into Neo4j and populate the cache.

        Flow: JSON → spark_dsg.DynamicSceneGraph.load() → extract embedded
        labelspaces → heracles.initialize_db() + spark_dsg_to_db()
        → populate in-memory cache from Neo4j → emit graph_loaded.

        The DSG object is transient — we don't keep it around.  Neo4j is the
        live store; the cache is the fast read path.

        Labelspaces are read from the DSG's embedded metadata
        (``metadata["labelspaces"]``). The model's labelspace dicts are
        updated to match so the UI dropdowns reflect what's in the file.
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        dsg = spark_dsg.DynamicSceneGraph.load(path)

        # Extract embedded labelspaces and update the model's dicts.
        from heracles.utils import extract_labelspaces_from_dsg

        obj_ls, room_ls = extract_labelspaces_from_dsg(dsg)
        if obj_ls is not None:
            self._label_to_semantic_id = {name: int(sid) for sid, name in obj_ls.items()}
        if room_ls is not None:
            self._room_label_to_semantic_id = {name: int(sid) for sid, name in room_ls.items()}

        dsg.metadata.add({"LayerIdToHeraclesLayerStr": _DEFAULT_LAYER_ID_TO_HERACLES})

        # Push to Neo4j (clears existing data first).
        initialize_db(self._db)
        spark_dsg_to_db(dsg, self._db, source_file_path=path)

        # Populate cache from what's now in Neo4j.
        self._refresh_cache()
        self._selected = []
        self.graph_loaded.emit()

    def save_to_json(self, path: str, include_mesh: bool = False):
        """Export the current Neo4j state to a JSON file via spark_dsg.

        Flow: heracles.db_to_spark_dsg() → DynamicSceneGraph.save().
        This reconstructs the DSG from Neo4j, which ensures the saved file
        reflects exactly what's in the database.

        If ``include_mesh`` is True, the mesh is copied from the original
        source file (whose path is stored as _GraphMetadata in Neo4j) into
        the saved file.  This makes the output self-contained but larger.
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        # Update labelspaces in Neo4j so db_to_spark_dsg() picks up any
        # labels added at runtime (via add_object_label / add_room_label).
        if self._label_to_semantic_id:
            ids = list(self._label_to_semantic_id.values())
            names = list(self._label_to_semantic_id.keys())
            self._db.execute(
                "MERGE (m:_Labelspace {layer: 'object'}) SET m.ids = $ids, m.names = $names",
                ids=ids,
                names=names,
            )
        if self._room_label_to_semantic_id:
            ids = list(self._room_label_to_semantic_id.values())
            names = list(self._room_label_to_semantic_id.keys())
            self._db.execute(
                "MERGE (m:_Labelspace {layer: 'room'}) SET m.ids = $ids, m.names = $names",
                ids=ids,
                names=names,
            )

        dsg = db_to_spark_dsg(self._db)

        if include_mesh:
            source_path = self.get_source_file_path()
            if source_path:
                import os

                if os.path.exists(source_path):
                    source_dsg = spark_dsg.DynamicSceneGraph.load(source_path)
                    if source_dsg.has_mesh():
                        dsg.mesh = source_dsg.mesh

        dsg.save(path, include_mesh=include_mesh)

    def _refresh_cache(self):
        """Rebuild the in-memory cache from Neo4j.

        Called after bulk load operations.  For incremental edits, the cache
        is updated directly by the CRUD methods (faster than a full refresh).
        """
        self._nodes = {}
        self._node_layers = {}
        self._edges = []

        for layer_label, _ in LAYER_ORDER:
            nodes = neo4j_crud.get_all_nodes(self._db, layer_label)
            for props in nodes:
                ns = props["nodeSymbol"]
                self._nodes[ns] = props
                self._node_layers[ns] = layer_label

        self._edges = neo4j_crud.get_all_edges(self._db)

    def refresh_from_db(self):
        """Re-read all nodes and edges from Neo4j into the cache.

        Use this when an external process (e.g., the chat agent) has modified
        Neo4j directly.  The model cache and all views will be rebuilt to
        reflect the current database state.
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        self._refresh_cache()
        self._selected = []
        self.graph_loaded.emit()

    # ------------------------------------------------------------------
    # Read access (views read from cache, not Neo4j)
    # ------------------------------------------------------------------

    def get_node(self, node_symbol: str) -> dict | None:
        """Get cached properties for a node, or None if not found."""
        return self._nodes.get(node_symbol)

    def get_node_layer(self, node_symbol: str) -> str | None:
        """Get the layer label for a node, or None if not found."""
        return self._node_layers.get(node_symbol)

    def get_nodes_by_layer(self, layer_label: str) -> list[dict]:
        """Get all cached nodes in a layer."""
        return [
            props for ns, props in self._nodes.items() if self._node_layers.get(ns) == layer_label
        ]

    def get_descendants(self, node_symbol: str) -> set[str]:
        """Find all transitive descendants of a node via CONTAINS edges.

        Walks the cached edge list following CONTAINS edges from parent to
        child, collecting all reachable descendants.  Used by the Focus on
        Subtree feature to show only a node's subtree.
        """
        # Build a children lookup from CONTAINS edges.
        children_of: dict[str, list[str]] = {}
        for e in self._edges:
            if e["edge_type"] == "CONTAINS":
                children_of.setdefault(e["from_symbol"], []).append(e["to_symbol"])

        # BFS from the root node.
        descendants = set()
        queue = list(children_of.get(node_symbol, []))
        while queue:
            child = queue.pop()
            if child not in descendants:
                descendants.add(child)
                queue.extend(children_of.get(child, []))

        return descendants

    def get_all_nodes(self) -> dict[str, dict]:
        """Get the full node cache.  Returns {node_symbol: props_dict}."""
        return self._nodes

    def get_edges(self) -> list[dict]:
        """Get the full edge cache."""
        return self._edges

    def node_count(self, layer_label: str) -> int:
        """Count nodes in a layer (from cache)."""
        return sum(1 for layer in self._node_layers.values() if layer == layer_label)

    # ------------------------------------------------------------------
    # Node mutations
    # ------------------------------------------------------------------

    def add_node(self, layer_label: str, node_symbol: str, props: dict):
        """Create a node in Neo4j and the cache, then notify views.

        ``props`` should contain the flat property dict expected by
        ``neo4j_crud.create_node`` (pos_x/y/z, and layer-specific fields
        like class, name, bbox_* for Objects).
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        neo4j_crud.create_node(self._db, layer_label, node_symbol, props)

        # Update cache — read back from Neo4j to get the canonical form
        # (e.g., Point3D values converted to lists).
        stored = neo4j_crud.get_node(self._db, layer_label, node_symbol)
        if stored is not None:
            self._nodes[node_symbol] = stored
            self._node_layers[node_symbol] = layer_label

        self.node_added.emit(node_symbol, layer_label)

    def remove_node(self, node_symbol: str):
        """Delete a node and its edges from Neo4j and the cache.

        Uses DETACH DELETE, so all connected edges are removed atomically.
        We also remove those edges from the cache and emit signals for each.
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        layer_label = self._node_layers.get(node_symbol)
        if layer_label is None:
            return  # Node not in cache — nothing to do.

        # Find and remove edges connected to this node from cache.
        removed_edges = [
            e
            for e in self._edges
            if e["from_symbol"] == node_symbol or e["to_symbol"] == node_symbol
        ]
        self._edges = [
            e
            for e in self._edges
            if e["from_symbol"] != node_symbol and e["to_symbol"] != node_symbol
        ]

        # Delete from Neo4j (DETACH DELETE handles edges).
        neo4j_crud.delete_node(self._db, layer_label, node_symbol)

        # Remove from cache.
        self._nodes.pop(node_symbol, None)
        self._node_layers.pop(node_symbol, None)

        # Remove from selection if present.
        if node_symbol in self._selected:
            self._selected = [s for s in self._selected if s != node_symbol]
            self.selection_changed.emit(self._selected)

        # Notify views — edges first, then node.
        for e in removed_edges:
            self.edge_removed.emit(e["from_symbol"], e["to_symbol"], e["edge_type"])
        self.node_removed.emit(node_symbol, layer_label)

    def update_node(self, node_symbol: str, props: dict):
        """Update properties on an existing node.

        ``props`` is a dict of property names to new values.  Point3D
        properties (center, bbox_center, bbox_dim) should be [x, y, z] lists.
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        layer_label = self._node_layers.get(node_symbol)
        if layer_label is None:
            return

        neo4j_crud.update_node(self._db, layer_label, node_symbol, props)

        # Refresh this node's cache entry from Neo4j.
        stored = neo4j_crud.get_node(self._db, layer_label, node_symbol)
        if stored is not None:
            self._nodes[node_symbol] = stored

        self.node_updated.emit(node_symbol, layer_label)

    # ------------------------------------------------------------------
    # Edge mutations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        from_symbol: str,
        to_symbol: str,
        edge_type: str | None = None,
    ):
        """Create an edge between two nodes.

        If ``edge_type`` is not provided, it is inferred from the layer
        labels of the two nodes (intralayer → *_CONNECTED, interlayer →
        CONTAINS).
        """
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        from_label = self._node_layers.get(from_symbol)
        to_label = self._node_layers.get(to_symbol)
        if from_label is None or to_label is None:
            raise ValueError(
                f"Cannot create edge: node(s) not found (from={from_symbol!r}, to={to_symbol!r})"
            )

        if edge_type is None:
            edge_type = neo4j_crud.determine_edge_type(from_label, to_label)

        neo4j_crud.create_edge(self._db, from_label, from_symbol, to_label, to_symbol, edge_type)

        # Update cache.
        self._edges.append(
            {
                "from_label": from_label,
                "from_symbol": from_symbol,
                "to_label": to_label,
                "to_symbol": to_symbol,
                "edge_type": edge_type,
            }
        )

        self.edge_added.emit(from_symbol, to_symbol, edge_type)

    def remove_edge(
        self,
        from_symbol: str,
        to_symbol: str,
        edge_type: str | None = None,
    ):
        """Delete an edge between two nodes."""
        if self._db is None:
            raise RuntimeError("Not connected to Neo4j")

        from_label = self._node_layers.get(from_symbol)
        to_label = self._node_layers.get(to_symbol)
        if from_label is None or to_label is None:
            return

        if edge_type is None:
            edge_type = neo4j_crud.determine_edge_type(from_label, to_label)

        neo4j_crud.delete_edge(self._db, from_label, from_symbol, to_label, to_symbol, edge_type)

        # Update cache — remove matching edge(s).
        self._edges = [
            e
            for e in self._edges
            if not (
                e["from_symbol"] == from_symbol
                and e["to_symbol"] == to_symbol
                and e["edge_type"] == edge_type
            )
        ]

        self.edge_removed.emit(from_symbol, to_symbol, edge_type)

    # ------------------------------------------------------------------
    # Selection state
    # ------------------------------------------------------------------

    @property
    def selected(self) -> list[str]:
        """Currently selected node symbols (read-only copy)."""
        return list(self._selected)

    def set_selection(self, node_symbols: list[str]):
        """Replace the current selection."""
        self._selected = list(node_symbols)
        self.selection_changed.emit(self._selected)

    def clear_selection(self):
        """Deselect all nodes."""
        if self._selected:
            self._selected = []
            self.selection_changed.emit(self._selected)

    def toggle_selection(self, node_symbol: str):
        """Toggle a single node's selection state (for Ctrl+click)."""
        if node_symbol in self._selected:
            self._selected = [s for s in self._selected if s != node_symbol]
        else:
            self._selected = self._selected + [node_symbol]
        self.selection_changed.emit(self._selected)

    # ------------------------------------------------------------------
    # Layer visibility
    # ------------------------------------------------------------------

    def is_layer_visible(self, layer_label: str) -> bool:
        return self._layer_visibility.get(layer_label, True)

    def set_layer_visibility(self, layer_label: str, visible: bool):
        if self._layer_visibility.get(layer_label) != visible:
            self._layer_visibility[layer_label] = visible
            self.layer_visibility_changed.emit(layer_label, visible)

    def get_layer_visibility(self) -> dict[str, bool]:
        """Get visibility state for all layers."""
        return dict(self._layer_visibility)

    @property
    def show_interlayer_edges(self) -> bool:
        return self._show_interlayer_edges

    def set_interlayer_edges_visible(self, visible: bool):
        if self._show_interlayer_edges != visible:
            self._show_interlayer_edges = visible
            self.interlayer_edges_visibility_changed.emit(visible)

    # ------------------------------------------------------------------
    # Graph metadata (source file path, mesh location)
    # ------------------------------------------------------------------

    def get_source_file_path(self) -> str | None:
        """Get the original DSG file path from Neo4j metadata.

        Returns None if no source path is stored (e.g., old data or
        graph created from scratch).
        """
        if self._db is None:
            return None
        try:
            records, _, _ = self._db.execute(
                "MATCH (m:_GraphMetadata {key: 'source'}) RETURN m.file_path AS path"
            )
            if records:
                return records[0]["path"]
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Labelspace access (for property panel dropdowns)
    # ------------------------------------------------------------------

    def get_object_labels(self) -> dict[str, int]:
        """Returns {label_name: semantic_id} for object/mesh_place classes."""
        return dict(self._label_to_semantic_id)

    def get_room_labels(self) -> dict[str, int]:
        """Returns {label_name: semantic_id} for room classes."""
        return dict(self._room_label_to_semantic_id)

    def set_labelspaces(
        self,
        object_labels: dict[str, int] | None = None,
        room_labels: dict[str, int] | None = None,
    ):
        """Set labelspace mappings (e.g., loaded from YAML files)."""
        if object_labels is not None:
            self._label_to_semantic_id = dict(object_labels)
        if room_labels is not None:
            self._room_label_to_semantic_id = dict(room_labels)

    def add_object_label(self, name: str) -> int:
        """Register a new object/mesh_place label, assigning the next semantic ID.

        No-op if the label already exists. Returns the semantic ID.
        """
        if name in self._label_to_semantic_id:
            return self._label_to_semantic_id[name]
        next_id = max(self._label_to_semantic_id.values(), default=-1) + 1
        self._label_to_semantic_id[name] = next_id
        return next_id

    def add_room_label(self, name: str) -> int:
        """Register a new room label, assigning the next semantic ID.

        No-op if the label already exists. Returns the semantic ID.
        """
        if name in self._room_label_to_semantic_id:
            return self._room_label_to_semantic_id[name]
        next_id = max(self._room_label_to_semantic_id.values(), default=-1) + 1
        self._room_label_to_semantic_id[name] = next_id
        return next_id
