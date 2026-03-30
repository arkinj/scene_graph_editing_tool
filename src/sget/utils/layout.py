"""
Spatial layout computation for the 2D scene graph view.

Design
------
Nodes are positioned using their actual 3D coordinates from the scene graph,
projected onto the x-y plane.  This preserves the spatial relationships
between nodes — objects that are near each other in the real environment
appear near each other in the view.

The ``center`` property in Neo4j is a CartesianPoint with x, y, z
coordinates.  We use x for the horizontal axis and y for the vertical axis
(negated, since Qt's y-axis increases downward but spatial y typically
increases upward).

A scale factor converts from world coordinates (meters) to scene coordinates
(pixels).  The layout auto-scales to fit the data.
"""

# Scale factor from world coordinates to scene pixels.
# Tuned so a typical indoor scene (~30m across) fills ~800px.
DEFAULT_SCALE = 30.0


def compute_layout(
    nodes: dict[str, dict],
    node_layers: dict[str, str],
    edges: list[dict],
) -> dict[str, tuple[float, float]]:
    """Compute 2D positions for all nodes from their spatial coordinates.

    Uses the ``center`` property from each node's cached properties.
    Projects 3D → 2D by taking (x, -y) — the negation puts "north" at
    the top of the screen, matching typical map conventions.

    Parameters
    ----------
    nodes : dict
        {node_symbol: props_dict} from SceneGraphModel cache.
    node_layers : dict
        {node_symbol: layer_label} from SceneGraphModel cache.
    edges : list
        Edge dicts (unused in spatial layout, kept for API compatibility).

    Returns
    -------
    dict
        {node_symbol: (x, y)} positions in scene coordinates.
    """
    if not nodes:
        return {}

    positions = {}

    for ns, props in nodes.items():
        center = props.get("center")
        if center is not None:
            # Project 3D → 2D: use x and -y (negate y so "up" is up).
            # Scale from world coordinates (meters) to scene pixels.
            x = float(center[0]) * DEFAULT_SCALE
            y = -float(center[1]) * DEFAULT_SCALE
        else:
            # Fallback for nodes without a position.
            x, y = 0.0, 0.0

        positions[ns] = (x, y)

    return positions
