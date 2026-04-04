"""
Per-layer visual styling for the scene graph.

Each layer gets a distinct color so nodes are immediately identifiable by
their position in the hierarchy.  Colors are chosen to be distinguishable
on both light and dark backgrounds and to work well when rendered as filled
circles in the 2D graph view.
"""

from dataclasses import dataclass

from heracles import constants


@dataclass(frozen=True)
class LayerStyle:
    """Visual properties for rendering a single scene graph layer."""

    layer_label: str  # heracles constant (e.g., "Object")
    layer_id: int  # spark_dsg numeric layer ID
    display_name: str  # Human-readable name
    color: str  # Hex color for node fill
    category_chars: tuple[str, ...]  # NodeSymbol category characters


# Ordered from top of hierarchy (Buildings) to bottom (Objects).
# This order is used by the layer panel, the 2D layout, and the model's
# LAYER_ORDER (which derives from this list to avoid duplication).
#
# category_chars lists ALL known category characters for a layer.  Different
# DSG creators use different chars (e.g., 'O' vs 'o' for Objects, 'P' vs 't'
# for MeshPlaces).  The first char is the default for new node creation.
LAYER_STYLES = [
    LayerStyle(constants.BUILDINGS, 5, "Buildings", "#636EFA", ("B",)),
    LayerStyle(constants.ROOMS, 4, "Rooms", "#EF553B", ("R",)),
    LayerStyle(constants.PLACES, 3, "Places", "#AB63FA", ("p",)),
    LayerStyle(constants.MESH_PLACES, 20, "MeshPlaces", "#FFA15A", ("P", "t")),
    LayerStyle(constants.OBJECTS, 2, "Objects", "#00CC96", ("O", "o")),
]

# Quick lookups by different keys.
STYLE_BY_LABEL = {s.layer_label: s for s in LAYER_STYLES}
# Selection highlight color.
SELECTION_COLOR = "#FFD700"  # Gold
SELECTION_PEN_WIDTH = 3

# Edge colors.
INTRALAYER_EDGE_COLOR = "#666666"
INTERLAYER_EDGE_COLOR = "#BBBBBB"
