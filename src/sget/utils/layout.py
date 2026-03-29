"""
Hierarchical layout computation for the 2D scene graph view.

Design
------
The layout arranges nodes in horizontal bands, one per layer, with the most
abstract layer (Buildings) at the top and the most concrete (Objects) at the
bottom.  This mirrors the scene graph hierarchy visually.

Within each band, nodes are positioned using NetworkX's spring layout, which
clusters connected nodes together.  The per-band Y coordinate is fixed, and
only the X positions come from the spring layout.

We don't use ``nx.multipartite_layout`` because it spaces nodes evenly
regardless of connectivity — spring layout produces more meaningful groupings
within each layer.

The layout operates on the model's cache (dicts of node properties and edge
lists) rather than constructing a NetworkX graph from the spark_dsg object.
This keeps the layout independent of the spark_dsg bindings and avoids
importing the C++ module just for positioning.
"""

import networkx as nx
import numpy as np

from sget.utils.colors import LAYER_STYLES

# Vertical spacing between layer bands (in scene units).
LAYER_BAND_HEIGHT = 300.0

# Horizontal scale factor for the spring layout within each band.
BAND_WIDTH = 800.0


def compute_layout(
    nodes: dict[str, dict],
    node_layers: dict[str, str],
    edges: list[dict],
) -> dict[str, tuple[float, float]]:
    """Compute 2D positions for all nodes.

    Parameters
    ----------
    nodes : dict
        {node_symbol: props_dict} from SceneGraphModel cache.
    node_layers : dict
        {node_symbol: layer_label} from SceneGraphModel cache.
    edges : list
        Edge dicts from SceneGraphModel cache, each with
        from_symbol, to_symbol, edge_type.

    Returns
    -------
    dict
        {node_symbol: (x, y)} positions in scene coordinates.
        Y increases downward (Buildings at y=0, Objects at bottom).
    """
    if not nodes:
        return {}

    # Assign each layer a Y band.  Index 0 = top of hierarchy = Buildings.
    layer_y = {}
    for i, style in enumerate(LAYER_STYLES):
        layer_y[style.layer_label] = i * LAYER_BAND_HEIGHT

    # Group nodes by layer for per-band spring layout.
    layer_nodes: dict[str, list[str]] = {}
    for ns, label in node_layers.items():
        layer_nodes.setdefault(label, []).append(ns)

    # Build a NetworkX graph of intralayer edges only — these drive the
    # spring layout within each band.
    intralayer_edges_by_layer: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        fl = node_layers.get(e["from_symbol"])
        tl = node_layers.get(e["to_symbol"])
        if fl is not None and tl is not None and fl == tl:
            intralayer_edges_by_layer.setdefault(fl, []).append((e["from_symbol"], e["to_symbol"]))

    positions = {}

    for label, ns_list in layer_nodes.items():
        y = layer_y.get(label, len(LAYER_STYLES) * LAYER_BAND_HEIGHT)

        if len(ns_list) == 1:
            # Single node — center it.
            positions[ns_list[0]] = (BAND_WIDTH / 2, y)
            continue

        # Build a subgraph for this layer's spring layout.
        sub = nx.Graph()
        sub.add_nodes_from(ns_list)
        for u, v in intralayer_edges_by_layer.get(label, []):
            if u in sub and v in sub:
                sub.add_edge(u, v)

        # Spring layout returns {node: array([x, y])}.
        # We only use the x coordinate; y is fixed per band.
        try:
            raw = nx.spring_layout(sub, scale=BAND_WIDTH / 2, iterations=50, seed=42)
        except Exception:
            # Fallback: evenly space nodes along the band.
            raw = {
                ns: np.array([i * BAND_WIDTH / max(len(ns_list) - 1, 1), 0])
                for i, ns in enumerate(ns_list)
            }

        for ns, pos in raw.items():
            # Shift x so the band is centered around BAND_WIDTH/2.
            x = pos[0] + BAND_WIDTH / 2
            positions[ns] = (x, y)

    return positions
