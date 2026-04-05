"""
QGraphicsItem subclasses for scene graph nodes and edges.

Extracted from graph_view.py to keep the main view file focused on
layout, interaction modes, and model signal handling.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
)

from sget.utils.colors import (
    INTERLAYER_EDGE_COLOR,
    INTRALAYER_EDGE_COLOR,
    SELECTION_COLOR,
    SELECTION_PEN_WIDTH,
    STYLE_BY_LABEL,
)

# Node circle radius in scene coordinates.
NODE_RADIUS = 12


class NodeItem(QGraphicsEllipseItem):
    """Visual representation of a scene graph node.

    Each node is a colored circle with a text label.  It is selectable
    by clicking, and optionally draggable when positions are unlocked.

    When dragged, connected edges are updated in real time via the
    ``ItemSendsGeometryChanges`` flag and ``itemChange`` override.
    The actual model update (writing to Neo4j) happens on mouse release,
    handled by the parent GraphView.
    """

    def __init__(self, node_symbol: str, layer_label: str, display_text: str, x: float, y: float):
        r = NODE_RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.node_symbol = node_symbol
        self.layer_label = layer_label

        # Position in scene coordinates.
        self.setPos(x, y)

        # Styling based on layer.
        style = STYLE_BY_LABEL.get(layer_label)
        color = QColor(style.color) if style else QColor("#888888")
        self.setBrush(QBrush(color))
        self._default_pen = QPen(Qt.black, 1)
        self.setPen(self._default_pen)

        # Tooltip for hover.
        self.setToolTip(f"{layer_label}: {node_symbol}")

        # Make it selectable (QGraphicsView handles click events).
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        # Enable geometry change notifications so we can update edges during drag.
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges, True)

        # Per-node lock state — locked by default (not draggable).
        self._locked = True

        # Text label below the circle.
        self._label = QGraphicsSimpleTextItem(display_text, self)
        self._label.setPos(-r, r + 2)
        font = self._label.font()
        font.setPointSize(7)
        self._label.setFont(font)

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool):
        self._locked = locked
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable, not locked)

    def set_highlighted(self, highlighted: bool):
        """Toggle selection highlight."""
        if highlighted:
            self.setPen(QPen(QColor(SELECTION_COLOR), SELECTION_PEN_WIDTH))
        else:
            self.setPen(self._default_pen)

    def itemChange(self, change, value):
        """Update connected edges in real time while dragging."""
        if change == QGraphicsEllipseItem.ItemPositionHasChanged:
            # Find the parent GraphView and ask it to reposition edges.
            scene = self.scene()
            if scene:
                for view in scene.views():
                    if hasattr(view, "_graph_view"):
                        view._graph_view._update_edges_for_node(self.node_symbol)
                        break
        return super().itemChange(change, value)


class EdgeItem(QGraphicsLineItem):
    """Visual representation of an edge between two nodes.

    Intralayer edges (sibling connections) are drawn as solid darker lines.
    Interlayer edges (CONTAINS) are drawn as dashed lighter lines, visually
    de-emphasizing the dense parent-child connectivity.
    """

    def __init__(self, from_item: NodeItem, to_item: NodeItem, is_interlayer: bool):
        super().__init__()
        self.from_symbol = from_item.node_symbol
        self.to_symbol = to_item.node_symbol
        self.is_interlayer = is_interlayer

        if is_interlayer:
            pen = QPen(QColor(INTERLAYER_EDGE_COLOR), 1, Qt.DashLine)
        else:
            pen = QPen(QColor(INTRALAYER_EDGE_COLOR), 1.5, Qt.SolidLine)
        self.setPen(pen)

        # Draw line between node centers.
        self.setLine(
            from_item.pos().x(),
            from_item.pos().y(),
            to_item.pos().x(),
            to_item.pos().y(),
        )

        # Edges should be behind nodes.
        self.setZValue(-1)

        # Make edges selectable for deletion.
        self.setFlag(QGraphicsLineItem.ItemIsSelectable, True)
