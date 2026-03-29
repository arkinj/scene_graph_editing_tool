"""
2D hierarchical graph view for scene graph visualization.

Design
------
This module provides the primary visual representation of the scene graph.
It uses Qt's QGraphicsScene/QGraphicsView framework, which gives us:
- Efficient rendering of thousands of items
- Built-in zoom/pan (via wheel and drag)
- Built-in rubber-band selection
- Per-item hit testing and event handling

The view is populated by reading from the SceneGraphModel's cache and
computing a hierarchical layout via ``utils.layout``.  It listens to model
signals to stay in sync:
- ``graph_loaded`` → full rebuild
- ``selection_changed`` → update highlights
- ``layer_visibility_changed`` → show/hide items

For the initial demo, we do a full rebuild on ``graph_loaded`` only.
Incremental updates (node_added/removed) will be wired in Phase 6.

Node selection in the view updates the model's selection state, which
propagates to all other views (property panel, etc.) via signals.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import (
    INTERLAYER_EDGE_COLOR,
    INTRALAYER_EDGE_COLOR,
    SELECTION_COLOR,
    SELECTION_PEN_WIDTH,
    STYLE_BY_LABEL,
)
from sget.utils.layout import compute_layout

# Node circle radius in scene coordinates.
NODE_RADIUS = 12


class NodeItem(QGraphicsEllipseItem):
    """Visual representation of a scene graph node.

    Each node is a colored circle with a text label.  It is selectable
    by clicking, and the view translates selection events into model
    selection updates.
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

        # Text label below the circle.
        self._label = QGraphicsSimpleTextItem(display_text, self)
        self._label.setPos(-r, r + 2)
        font = self._label.font()
        font.setPointSize(7)
        self._label.setFont(font)

    def set_highlighted(self, highlighted: bool):
        """Toggle selection highlight."""
        if highlighted:
            self.setPen(QPen(QColor(SELECTION_COLOR), SELECTION_PEN_WIDTH))
        else:
            self.setPen(self._default_pen)


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


class GraphView(QWidget):
    """Container widget for the 2D scene graph visualization.

    Wraps a QGraphicsView + QGraphicsScene and manages the lifecycle of
    node/edge items.  Connects to the SceneGraphModel to stay in sync.
    """

    def __init__(self, model: SceneGraphModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model

        # Item tracking: node_symbol -> NodeItem, for selection sync.
        self._node_items: dict[str, NodeItem] = {}

        # Qt graphics setup.
        self._scene = QGraphicsScene(self)
        self._view = _ZoomableGraphicsView(self._scene)
        self._view.setRenderHint(self._view.renderHints())
        self._view.setDragMode(QGraphicsView.RubberBandDrag)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        # Connect model signals.
        self._model.graph_loaded.connect(self._on_graph_loaded)
        self._model.selection_changed.connect(self._on_selection_changed)
        self._model.layer_visibility_changed.connect(self._on_layer_visibility_changed)

        # Connect scene selection changes to model.
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

        # Guard against recursive selection updates.
        self._updating_selection = False

    # ------------------------------------------------------------------
    # Full rebuild (on graph_loaded)
    # ------------------------------------------------------------------

    def _on_graph_loaded(self):
        """Rebuild the entire scene from the model's cache."""
        self._scene.selectionChanged.disconnect(self._on_scene_selection_changed)
        self._scene.clear()
        self._node_items = {}

        nodes = self._model.get_all_nodes()
        node_layers = {ns: self._model.get_node_layer(ns) for ns in nodes}
        edges = self._model.get_edges()

        # Compute layout positions.
        positions = compute_layout(nodes, node_layers, edges)

        # Create node items.
        for ns, props in nodes.items():
            layer_label = node_layers.get(ns, "")
            pos = positions.get(ns, (0, 0))

            # Build display text: nodeSymbol + class if available.
            display = ns
            if "class" in props:
                display = f"{ns}\n{props['class']}"

            item = NodeItem(ns, layer_label, display, pos[0], pos[1])
            self._scene.addItem(item)
            self._node_items[ns] = item

            # Respect current layer visibility.
            if not self._model.is_layer_visible(layer_label):
                item.setVisible(False)

        # Create edge items.
        for edge in edges:
            from_item = self._node_items.get(edge["from_symbol"])
            to_item = self._node_items.get(edge["to_symbol"])
            if from_item is None or to_item is None:
                continue

            is_interlayer = edge["edge_type"] == "CONTAINS"
            edge_item = EdgeItem(from_item, to_item, is_interlayer)
            self._scene.addItem(edge_item)

            # Hide edge if either endpoint's layer is hidden.
            if not from_item.isVisible() or not to_item.isVisible():
                edge_item.setVisible(False)

        # Fit the view to show all items.
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        # Reconnect selection handler.
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

    # ------------------------------------------------------------------
    # Selection sync
    # ------------------------------------------------------------------

    def _on_scene_selection_changed(self):
        """User clicked/rubber-banded in the view → update model selection."""
        if self._updating_selection:
            return

        selected = [
            item.node_symbol for item in self._scene.selectedItems() if isinstance(item, NodeItem)
        ]
        self._updating_selection = True
        self._model.set_selection(selected)
        self._updating_selection = False

    def _on_selection_changed(self, selected: list):
        """Model selection changed (from another view) → update highlights."""
        if self._updating_selection:
            return

        self._updating_selection = True
        selected_set = set(selected)

        # Block scene signals while we programmatically change selection.
        self._scene.blockSignals(True)
        self._scene.clearSelection()
        for ns, item in self._node_items.items():
            highlighted = ns in selected_set
            item.set_highlighted(highlighted)
            item.setSelected(highlighted)
        self._scene.blockSignals(False)

        self._updating_selection = False

    # ------------------------------------------------------------------
    # Layer visibility
    # ------------------------------------------------------------------

    def _on_layer_visibility_changed(self, layer_label: str, visible: bool):
        """Toggle visibility of all nodes and their edges in a layer."""
        for ns, item in self._node_items.items():
            if item.layer_label == layer_label:
                item.setVisible(visible)

        # Also update edge visibility — hide if either endpoint is hidden.
        for item in self._scene.items():
            if isinstance(item, EdgeItem):
                from_visible = self._node_items.get(item.from_symbol, None)
                to_visible = self._node_items.get(item.to_symbol, None)
                item.setVisible(
                    (from_visible is not None and from_visible.isVisible())
                    and (to_visible is not None and to_visible.isVisible())
                )


class _ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView subclass that supports mouse wheel zoom.

    The default QGraphicsView doesn't zoom on scroll — it scrolls the
    viewport.  This subclass intercepts wheel events and applies a scale
    transform instead, which is the expected behavior for a graph viewer.
    """

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
        else:
            self.scale(1 / factor, 1 / factor)
