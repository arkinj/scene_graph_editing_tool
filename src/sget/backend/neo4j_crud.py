"""
Single-node and single-edge CRUD operations for Neo4j scene graph databases.

Design overview
===============
Heracles (~/software/mit/sget/heracles/heracles/) provides bulk operations for
loading entire scene graphs into Neo4j (via UNWIND + MERGE over lists), but has
no support for mutating individual nodes or edges. This module fills that gap
with targeted Cypher queries for the interactive editing tool.

All functions take a ``Neo4jWrapper`` instance (from heracles.query_interface)
as their first argument and delegate to its ``execute()`` method, which passes
keyword arguments through to the Neo4j Python driver as query parameters.

Neo4j schema conventions (matching heracles)
--------------------------------------------
- Each scene graph layer maps to a Neo4j **node label**: Object, Place,
  MeshPlace, Room, Building (defined in ``heracles.constants``).
- Every node has a ``nodeSymbol`` string property (e.g. "O(4)", "p(15)")
  that uniquely identifies it within its label. Heracles creates indexes on
  this property for fast lookups.
- 3D coordinates are stored as Neo4j ``Point`` values via the ``point()``
  function.  Scalar properties (class, name) are stored directly.
- Intralayer edges (sibling connectivity) use label-specific relationship
  types: OBJECT_CONNECTED, PLACE_CONNECTED, MESH_PLACE_CONNECTED,
  ROOM_CONNECTED, BUILDING_CONNECTED.
- Interlayer edges (parent-child containment) all use the CONTAINS
  relationship type, directed from parent to child.

Why per-layer CREATE templates?
-------------------------------
Each layer stores a different set of properties in Neo4j (see the property
tables below).  Rather than building Cypher dynamically from arbitrary dicts
at create time — which would be fragile and hard to validate — we use explicit
templates per layer that mirror the MERGE patterns in heracles'
``graph_interface.py``.  This keeps the schema consistent between bulk loads
and interactive edits.

Update is the exception: since any subset of properties can change, it builds
SET clauses dynamically.  Point3D fields require wrapping in ``point()``,
while scalar fields are set directly.

Property reference
------------------
Object:    nodeSymbol, center (Point3D), bbox_center (Point3D),
           bbox_dim (Point3D), class, name
Place:     nodeSymbol, center (Point3D)
MeshPlace: nodeSymbol, center (Point3D), class
Room:      nodeSymbol, center (Point3D), class
Building:  nodeSymbol, center (Point3D)
"""

from heracles import constants
from heracles.query_interface import Neo4jWrapper

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps heracles layer labels to the Neo4j relationship type used for
# intralayer (sibling) edges.  Derived from the edge insertion logic in
# heracles graph_interface.py (insert_edges calls on lines 247-376).
INTRALAYER_EDGE_TYPES = {
    constants.OBJECTS: "OBJECT_CONNECTED",
    constants.PLACES: "PLACE_CONNECTED",
    constants.MESH_PLACES: "MESH_PLACE_CONNECTED",
    constants.ROOMS: "ROOM_CONNECTED",
    constants.BUILDINGS: "BUILDING_CONNECTED",
}

# All interlayer (parent→child) edges use a single relationship type.
INTERLAYER_EDGE_TYPE = "CONTAINS"

# The set of node properties that are stored as Neo4j Point3D values.
# These require special handling in UPDATE queries (must be wrapped in the
# ``point()`` function rather than set as raw values).
POINT3D_PROPERTIES = {"center", "bbox_center", "bbox_dim"}


# ---------------------------------------------------------------------------
# Node creation — per-layer templates
# ---------------------------------------------------------------------------


def create_object(db: Neo4jWrapper, node_symbol: str, props: dict):
    """Create a single Object node.

    Required keys in ``props``: pos_x/y/z, bbox_x/y/z, bbox_l/w/h, class, name.
    These match the flat dict format produced by heracles' ``obj_to_dict()``.
    """
    db.execute(
        f"""
        CREATE (:{constants.OBJECTS} {{
            nodeSymbol: $ns,
            center: point({{x: $pos_x, y: $pos_y, z: $pos_z}}),
            bbox_center: point({{x: $bbox_x, y: $bbox_y, z: $bbox_z}}),
            bbox_dim: point({{x: $bbox_l, y: $bbox_w, z: $bbox_h}}),
            class: $cls,
            name: $name
        }})
        """,
        ns=node_symbol,
        pos_x=props["pos_x"],
        pos_y=props["pos_y"],
        pos_z=props["pos_z"],
        bbox_x=props["bbox_x"],
        bbox_y=props["bbox_y"],
        bbox_z=props["bbox_z"],
        bbox_l=props["bbox_l"],
        bbox_w=props["bbox_w"],
        bbox_h=props["bbox_h"],
        cls=props["class"],
        name=props["name"],
    )


def create_place(db: Neo4jWrapper, node_symbol: str, props: dict):
    """Create a single Place node.  Required keys: pos_x/y/z."""
    db.execute(
        f"""
        CREATE (:{constants.PLACES} {{
            nodeSymbol: $ns,
            center: point({{x: $pos_x, y: $pos_y, z: $pos_z}})
        }})
        """,
        ns=node_symbol,
        pos_x=props["pos_x"],
        pos_y=props["pos_y"],
        pos_z=props["pos_z"],
    )


def create_mesh_place(db: Neo4jWrapper, node_symbol: str, props: dict):
    """Create a single MeshPlace node.  Required keys: pos_x/y/z, class."""
    db.execute(
        f"""
        CREATE (:{constants.MESH_PLACES} {{
            nodeSymbol: $ns,
            center: point({{x: $pos_x, y: $pos_y, z: $pos_z}}),
            class: $cls
        }})
        """,
        ns=node_symbol,
        pos_x=props["pos_x"],
        pos_y=props["pos_y"],
        pos_z=props["pos_z"],
        cls=props["class"],
    )


def create_room(db: Neo4jWrapper, node_symbol: str, props: dict):
    """Create a single Room node.  Required keys: pos_x/y/z, class."""
    db.execute(
        f"""
        CREATE (:{constants.ROOMS} {{
            nodeSymbol: $ns,
            center: point({{x: $pos_x, y: $pos_y, z: $pos_z}}),
            class: $cls
        }})
        """,
        ns=node_symbol,
        pos_x=props["pos_x"],
        pos_y=props["pos_y"],
        pos_z=props["pos_z"],
        cls=props["class"],
    )


def create_building(db: Neo4jWrapper, node_symbol: str, props: dict):
    """Create a single Building node.  Required keys: pos_x/y/z."""
    db.execute(
        f"""
        CREATE (:{constants.BUILDINGS} {{
            nodeSymbol: $ns,
            center: point({{x: $pos_x, y: $pos_y, z: $pos_z}})
        }})
        """,
        ns=node_symbol,
        pos_x=props["pos_x"],
        pos_y=props["pos_y"],
        pos_z=props["pos_z"],
    )


# Dispatch table mapping layer labels to their create functions.
_CREATE_DISPATCH = {
    constants.OBJECTS: create_object,
    constants.PLACES: create_place,
    constants.MESH_PLACES: create_mesh_place,
    constants.ROOMS: create_room,
    constants.BUILDINGS: create_building,
}


def create_node(db: Neo4jWrapper, layer_label: str, node_symbol: str, props: dict):
    """Create a single node in the given layer.

    Dispatches to the appropriate per-layer function based on ``layer_label``
    (one of the heracles.constants label strings: "Object", "Place", etc.).
    """
    create_fn = _CREATE_DISPATCH.get(layer_label)
    if create_fn is None:
        raise ValueError(f"Unknown layer label: {layer_label!r}")
    create_fn(db, node_symbol, props)


# ---------------------------------------------------------------------------
# Node read
# ---------------------------------------------------------------------------


def get_node(db: Neo4jWrapper, layer_label: str, node_symbol: str) -> dict | None:
    """Fetch a single node by label and nodeSymbol.

    Returns a dict of property names to values, or None if not found.
    The Neo4j driver returns Point3D values as lists [x, y, z], which
    matches the format expected by the rest of the application.
    """
    # Object nodes have extra properties (bbox_center, bbox_dim, name) that
    # other layers don't.  Rather than branching per layer, we return all
    # properties generically with ``properties(n)``.
    records, _, _ = db.execute(
        f"""
        MATCH (n:{layer_label} {{nodeSymbol: $ns}})
        RETURN properties(n) AS props
        """,
        ns=node_symbol,
    )
    if not records:
        return None
    return dict(records[0]["props"])


def get_all_nodes(db: Neo4jWrapper, layer_label: str) -> list[dict]:
    """Fetch all nodes for a given layer.

    This mirrors heracles' ``get_layer_nodes()`` but returns a uniform format
    (list of property dicts) regardless of layer, using ``properties(n)``.
    """
    records, _, _ = db.execute(
        f"""
        MATCH (n:{layer_label})
        RETURN properties(n) AS props
        """,
    )
    return [dict(r["props"]) for r in records]


# ---------------------------------------------------------------------------
# Node update
# ---------------------------------------------------------------------------


def update_node(db: Neo4jWrapper, layer_label: str, node_symbol: str, props: dict):
    """Update properties on an existing node.

    Builds SET clauses dynamically from the ``props`` dict.  Properties whose
    names are in ``POINT3D_PROPERTIES`` (center, bbox_center, bbox_dim) are
    wrapped in Neo4j's ``point()`` function; all other properties are set as
    scalar values.

    This is the one operation that is generic across layers, because any
    subset of properties can change and we don't need to enforce which
    properties belong to which layer here — the caller (SceneGraphModel)
    is responsible for providing valid properties.
    """
    if not props:
        return

    set_clauses = []
    params = {"ns": node_symbol}

    for key, value in props.items():
        if key in POINT3D_PROPERTIES:
            # Point3D fields arrive as a 3-element sequence [x, y, z].
            # Neo4j requires the point() constructor function.
            px, py, pz = f"{key}_x", f"{key}_y", f"{key}_z"
            set_clauses.append(f"n.{key} = point({{x: ${px}, y: ${py}, z: ${pz}}})")
            params[px] = value[0]
            params[py] = value[1]
            params[pz] = value[2]
        else:
            # Scalar property — set directly.
            set_clauses.append(f"n.{key} = ${key}")
            params[key] = value

    query = f"""
        MATCH (n:{layer_label} {{nodeSymbol: $ns}})
        SET {", ".join(set_clauses)}
    """
    db.execute(query, **params)


# ---------------------------------------------------------------------------
# Node deletion
# ---------------------------------------------------------------------------


def delete_node(db: Neo4jWrapper, layer_label: str, node_symbol: str):
    """Delete a node and all its relationships.

    Uses DETACH DELETE which removes the node and every edge connected to it
    in a single atomic operation.  This is the same regardless of layer.
    """
    db.execute(
        f"""
        MATCH (n:{layer_label} {{nodeSymbol: $ns}})
        DETACH DELETE n
        """,
        ns=node_symbol,
    )


# ---------------------------------------------------------------------------
# Edge operations
# ---------------------------------------------------------------------------


def determine_edge_type(from_label: str, to_label: str) -> str:
    """Determine the Neo4j relationship type for an edge between two nodes.

    Heracles uses two kinds of edges (see graph_interface.py add_edges_from_dsg):
    - **Intralayer**: same-label nodes connected by a label-specific relationship
      (e.g., OBJECT_CONNECTED for Object↔Object).
    - **Interlayer**: parent→child nodes connected by CONTAINS (always directed
      from the higher layer to the lower layer).

    This function infers which type to use based on the source and target labels.
    """
    if from_label == to_label:
        edge_type = INTRALAYER_EDGE_TYPES.get(from_label)
        if edge_type is None:
            raise ValueError(f"No intralayer edge type for label: {from_label!r}")
        return edge_type
    return INTERLAYER_EDGE_TYPE


def create_edge(
    db: Neo4jWrapper,
    from_label: str,
    from_symbol: str,
    to_label: str,
    to_symbol: str,
    edge_type: str | None = None,
):
    """Create a single directed edge between two nodes.

    If ``edge_type`` is not provided, it is inferred via ``determine_edge_type``.
    The edge is directed from the ``from`` node to the ``to`` node, matching
    heracles' convention where CONTAINS edges point from parent to child and
    intralayer edges point from the node that listed the sibling.
    """
    if edge_type is None:
        edge_type = determine_edge_type(from_label, to_label)

    db.execute(
        f"""
        MATCH (a:{from_label} {{nodeSymbol: $from_ns}})
        MATCH (b:{to_label} {{nodeSymbol: $to_ns}})
        CREATE (a)-[:{edge_type}]->(b)
        """,
        from_ns=from_symbol,
        to_ns=to_symbol,
    )


def delete_edge(
    db: Neo4jWrapper,
    from_label: str,
    from_symbol: str,
    to_label: str,
    to_symbol: str,
    edge_type: str | None = None,
):
    """Delete a single directed edge between two nodes.

    Only deletes the relationship, not the nodes themselves.  If ``edge_type``
    is not provided, it is inferred via ``determine_edge_type``.
    """
    if edge_type is None:
        edge_type = determine_edge_type(from_label, to_label)

    db.execute(
        f"""
        MATCH (a:{from_label} {{nodeSymbol: $from_ns}})
              -[r:{edge_type}]->
              (b:{to_label} {{nodeSymbol: $to_ns}})
        DELETE r
        """,
        from_ns=from_symbol,
        to_ns=to_symbol,
    )


def get_all_edges(db: Neo4jWrapper) -> list[dict]:
    """Fetch all edges in the database, regardless of type.

    Returns a list of dicts with keys: from_label, from_symbol, to_label,
    to_symbol, edge_type.  This provides a uniform view across all
    relationship types for populating the graph view.
    """
    records, _, _ = db.execute(
        """
        MATCH (a)-[r]->(b)
        RETURN labels(a)[0] AS from_label,
               a.nodeSymbol AS from_symbol,
               labels(b)[0] AS to_label,
               b.nodeSymbol AS to_symbol,
               type(r) AS edge_type
        """
    )
    return [dict(r) for r in records]
