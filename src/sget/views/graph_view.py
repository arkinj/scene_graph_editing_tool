"""
2D scene graph view with spatial layout and polygon region drawing.

Design
------
This module provides the primary visual representation of the scene graph.
It uses Qt's QGraphicsScene/QGraphicsView framework, which gives us:
- Efficient rendering of thousands of items
- Built-in zoom/pan (via wheel and drag)
- Built-in rubber-band selection
- Per-item hit testing and event handling

Nodes are positioned using their actual 3D coordinates (x, -y projection),
so the view reflects the real spatial layout of the environment.

The view supports two interaction modes:
1. **Normal mode** (default): click to select, rubber-band drag, right-click
   context menu for node/edge operations.
2. **Polygon draw mode**: activated via Edit → Draw Region. Click to place
   vertices, double-click to close the polygon, Escape to cancel. On close,
   all nodes inside the polygon are identified and the Group dialog opens
   with them pre-selected.

The polygon tool is designed to work with the Group dialog — it's a spatial
selection method, not a standalone feature. The three ways to create a region
all feed into the same Group dialog:
- Individual node selection (Ctrl+click) → Ctrl+G
- Rubber-band selection → Ctrl+G
- Polygon boundary → automatic Group dialog with boundary data
"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QImage, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLineEdit,
    QMenu,
    QMessageBox,
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
from sget.utils.layout import DEFAULT_SCALE, compute_layout

# Node circle radius in scene coordinates.
NODE_RADIUS = 12

# Polygon drawing style.
_POLYGON_FILL = QColor(100, 150, 255, 40)  # Semi-transparent blue
_POLYGON_BORDER = QColor(100, 150, 255, 200)
_POLYGON_PEN_WIDTH = 2


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


class GraphView(QWidget):
    """Container widget for the 2D scene graph visualization.

    Wraps a QGraphicsView + QGraphicsScene and manages the lifecycle of
    node/edge items.  Connects to the SceneGraphModel to stay in sync.
    """

    def __init__(self, model: SceneGraphModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model

        # Item tracking for selection sync and incremental updates.
        self._node_items: dict[str, NodeItem] = {}
        # Edge items keyed by (from_symbol, to_symbol) for lookup on removal.
        self._edge_items: dict[tuple[str, str], EdgeItem] = {}

        # Boundary overlay items for Rooms with polygon data.
        self._boundary_items: dict[str, QGraphicsPolygonItem] = {}

        # Polygon drawing state.
        self._polygon_mode_active = False
        self._polygon_vertices: list[QPointF] = []
        self._polygon_item: QGraphicsPolygonItem | None = None
        self._polygon_preview_line = None  # Temp line from last vertex to cursor

        # Qt graphics setup.
        self._scene = QGraphicsScene(self)
        self._view = _ZoomableGraphicsView(self._scene, self)
        self._view.setRenderHint(self._view.renderHints())
        self._view.setDragMode(QGraphicsView.RubberBandDrag)

        # Search bar for filtering nodes by symbol, class, or name.
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Search nodes... (by symbol, class, or name)")
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._on_search_changed)
        self._search_bar.returnPressed.connect(self._on_search_enter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._search_bar)
        layout.addWidget(self._view)

        # Connect model signals.
        self._model.graph_loaded.connect(self._on_graph_loaded)
        self._model.selection_changed.connect(self._on_selection_changed)
        self._model.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        self._model.node_added.connect(self._on_node_added)
        self._model.node_removed.connect(self._on_node_removed)
        self._model.edge_added.connect(self._on_edge_added)
        self._model.edge_removed.connect(self._on_edge_removed)
        self._model.interlayer_edges_visibility_changed.connect(
            self._on_interlayer_edges_visibility_changed
        )

        # Connect scene selection changes to model.
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

        # Guard against recursive selection updates.
        self._updating_selection = False

    # ------------------------------------------------------------------
    # Polygon drawing mode
    # ------------------------------------------------------------------

    @property
    def polygon_mode_active(self) -> bool:
        return self._polygon_mode_active

    def start_polygon_mode(self):
        """Enter polygon drawing mode.

        Disables rubber-band selection and enables click-to-place-vertex.
        The status bar message is set by the caller (MainWindow).
        """
        self._polygon_mode_active = True
        self._polygon_vertices = []
        self._view.setDragMode(QGraphicsView.NoDrag)
        self._view.setCursor(Qt.CrossCursor)

    def cancel_polygon_mode(self):
        """Exit polygon drawing mode without creating a region."""
        self._cleanup_polygon_visuals()
        self._polygon_mode_active = False
        self._polygon_vertices = []
        self._view.setDragMode(QGraphicsView.RubberBandDrag)
        self._view.setCursor(Qt.ArrowCursor)

    def _on_polygon_click(self, scene_pos: QPointF):
        """Handle a left-click in polygon mode — place a vertex."""
        self._polygon_vertices.append(scene_pos)
        self._update_polygon_visual()

    def _on_polygon_double_click(self, scene_pos: QPointF):
        """Handle a double-click in polygon mode — close the polygon.

        A double-click fires both a click and a double-click event.
        The click already added the vertex, so we just close.
        """
        if len(self._polygon_vertices) < 3:
            # Need at least 3 vertices for a polygon.
            return

        # Find nodes inside the polygon.
        polygon = QPolygonF(self._polygon_vertices)
        captured = self._find_nodes_in_polygon(polygon)

        # Convert polygon vertices from scene coords back to world coords
        # for storage as a Room boundary property.
        boundary_world = [
            (pt.x() / DEFAULT_SCALE, -pt.y() / DEFAULT_SCALE) for pt in self._polygon_vertices
        ]

        # Exit polygon mode.
        self.cancel_polygon_mode()

        # Notify the main window to open the Group dialog with captured nodes.
        # We use a callback pattern — MainWindow sets this when it wires up
        # the Draw Region action.
        if hasattr(self, "_on_polygon_completed") and self._on_polygon_completed:
            self._on_polygon_completed(captured, boundary_world)

    def _on_polygon_mouse_move(self, scene_pos: QPointF):
        """Update the preview line from the last vertex to the cursor."""
        if not self._polygon_vertices:
            return

        # Remove old preview line.
        if self._polygon_preview_line is not None:
            self._scene.removeItem(self._polygon_preview_line)
            self._polygon_preview_line = None

        # Draw new preview line.
        last = self._polygon_vertices[-1]
        self._polygon_preview_line = self._scene.addLine(
            last.x(),
            last.y(),
            scene_pos.x(),
            scene_pos.y(),
            QPen(_POLYGON_BORDER, 1, Qt.DashLine),
        )
        self._polygon_preview_line.setZValue(10)

    def _update_polygon_visual(self):
        """Redraw the polygon overlay with current vertices."""
        # Remove old polygon item.
        if self._polygon_item is not None:
            self._scene.removeItem(self._polygon_item)

        if len(self._polygon_vertices) < 2:
            # Just show a dot for a single vertex.
            return

        polygon = QPolygonF(self._polygon_vertices)
        self._polygon_item = QGraphicsPolygonItem(polygon)
        self._polygon_item.setBrush(QBrush(_POLYGON_FILL))
        self._polygon_item.setPen(QPen(_POLYGON_BORDER, _POLYGON_PEN_WIDTH, Qt.DashLine))
        self._polygon_item.setZValue(5)  # Above edges, below cursor
        self._scene.addItem(self._polygon_item)

    def _cleanup_polygon_visuals(self):
        """Remove all temporary polygon drawing items from the scene."""
        if self._polygon_item is not None:
            self._scene.removeItem(self._polygon_item)
            self._polygon_item = None
        if self._polygon_preview_line is not None:
            self._scene.removeItem(self._polygon_preview_line)
            self._polygon_preview_line = None

    def _find_nodes_in_polygon(
        self,
        polygon: QPolygonF,
        layer_filter: list[str] | None = None,
    ) -> list[str]:
        """Find all visible node symbols whose positions fall inside a polygon.

        Parameters
        ----------
        polygon : QPolygonF
            The closed polygon in scene coordinates.
        layer_filter : list of str, optional
            If provided, only include nodes in these layers.
            Defaults to None (all visible nodes).

        Returns
        -------
        list of str
            Node symbols inside the polygon.
        """
        captured = []
        for ns, item in self._node_items.items():
            if not item.isVisible():
                continue
            if layer_filter and item.layer_label not in layer_filter:
                continue
            if polygon.containsPoint(item.pos(), Qt.OddEvenFill):
                captured.append(ns)
        return captured

    # ------------------------------------------------------------------
    # Full rebuild (on graph_loaded)
    # ------------------------------------------------------------------

    def _on_graph_loaded(self):
        """Rebuild the entire scene from the model's cache."""
        # Cancel polygon mode if active.
        if self._polygon_mode_active:
            self.cancel_polygon_mode()

        self._scene.selectionChanged.disconnect(self._on_scene_selection_changed)
        self._scene.clear()
        self._node_items = {}
        self._edge_items = {}
        self._boundary_items = {}

        nodes = self._model.get_all_nodes()
        node_layers = {ns: self._model.get_node_layer(ns) for ns in nodes}
        edges = self._model.get_edges()

        # Compute layout positions.
        positions = compute_layout(nodes, node_layers, edges)

        # Create node items.
        for ns, props in nodes.items():
            layer_label = node_layers.get(ns, "")
            pos = positions.get(ns, (0, 0))
            self._add_node_item(ns, layer_label, props, pos[0], pos[1])

        # Create edge items.
        for edge in edges:
            self._add_edge_item(edge["from_symbol"], edge["to_symbol"], edge["edge_type"])

        # Draw boundary overlays for Rooms with polygon data.
        self._draw_boundaries()

        # Fit the view to show all items.
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        # Clear search bar.
        self._search_bar.clear()

        # Reconnect selection handler.
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

    # ------------------------------------------------------------------
    # Incremental updates
    # ------------------------------------------------------------------

    def _on_node_added(self, node_symbol: str, layer_label: str):
        """Add a single node to the scene without recomputing the full layout."""
        props = self._model.get_node(node_symbol)
        if props is None:
            return

        x, y = self._default_position_for_layer(layer_label)
        self._add_node_item(node_symbol, layer_label, props, x, y)

    def _on_node_removed(self, node_symbol: str, layer_label: str):
        """Remove a single node and its connected edges from the scene."""
        item = self._node_items.pop(node_symbol, None)
        if item is not None:
            self._scene.removeItem(item)

        # Remove any edge items connected to this node.
        to_remove = [key for key in self._edge_items if node_symbol in key]
        for key in to_remove:
            edge_item = self._edge_items.pop(key, None)
            if edge_item is not None:
                self._scene.removeItem(edge_item)

    def _on_edge_added(self, from_symbol: str, to_symbol: str, edge_type: str):
        """Add a single edge item to the scene."""
        self._add_edge_item(from_symbol, to_symbol, edge_type)

    def _on_edge_removed(self, from_symbol: str, to_symbol: str, edge_type: str):
        """Remove a single edge item from the scene."""
        key = (from_symbol, to_symbol)
        edge_item = self._edge_items.pop(key, None)
        if edge_item is not None:
            self._scene.removeItem(edge_item)

    # ------------------------------------------------------------------
    # Item creation helpers
    # ------------------------------------------------------------------

    def _add_node_item(self, ns: str, layer_label: str, props: dict, x: float, y: float):
        """Create a NodeItem and add it to the scene."""
        display = ns
        if "class" in props:
            display = f"{ns}\n{props['class']}"

        item = NodeItem(ns, layer_label, display, x, y)
        self._scene.addItem(item)
        self._node_items[ns] = item

        # Respect current layer visibility.
        if not self._model.is_layer_visible(layer_label):
            item.setVisible(False)

    def _add_edge_item(self, from_symbol: str, to_symbol: str, edge_type: str):
        """Create an EdgeItem and add it to the scene."""
        from_item = self._node_items.get(from_symbol)
        to_item = self._node_items.get(to_symbol)
        if from_item is None or to_item is None:
            return

        is_interlayer = edge_type == "CONTAINS"
        edge_item = EdgeItem(from_item, to_item, is_interlayer)
        self._scene.addItem(edge_item)
        self._edge_items[(from_symbol, to_symbol)] = edge_item

        # Determine visibility: hide if either endpoint is hidden,
        # or if it's an interlayer edge and those are toggled off.
        visible = from_item.isVisible() and to_item.isVisible()
        if is_interlayer and not self._model.show_interlayer_edges:
            visible = False
        edge_item.setVisible(visible)

    def _default_position_for_layer(self, layer_label: str) -> tuple[float, float]:
        """Compute a default position for a new node in a given layer.

        Returns the centroid of existing nodes in the layer, or (0, 0)
        if the layer is empty.
        """
        layer_items = [
            item for item in self._node_items.values() if item.layer_label == layer_label
        ]
        if not layer_items:
            return 0.0, 0.0

        x = sum(item.pos().x() for item in layer_items) / len(layer_items)
        y = sum(item.pos().y() for item in layer_items) / len(layer_items)
        return x, y

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
        """Toggle visibility of all nodes, edges, and boundaries in a layer."""
        for ns, item in self._node_items.items():
            if item.layer_label == layer_label:
                item.setVisible(visible)

        # Toggle boundary overlays for Room layer.
        if layer_label == "Room":
            for boundary_item in self._boundary_items.values():
                boundary_item.setVisible(visible)

        self._update_edge_visibility()

    def _on_interlayer_edges_visibility_changed(self, visible: bool):
        """Toggle visibility of all interlayer (CONTAINS) edges."""
        self._update_edge_visibility()

    def _update_edge_visibility(self):
        """Recompute visibility for all edges.

        An edge is visible when:
        1. Both endpoints are visible (their layers are toggled on), AND
        2. If it's an interlayer edge, the interlayer toggle is on.
        """
        show_interlayer = self._model.show_interlayer_edges
        for edge_item in self._edge_items.values():
            from_vis = self._node_items.get(edge_item.from_symbol)
            to_vis = self._node_items.get(edge_item.to_symbol)
            endpoints_visible = (
                from_vis is not None
                and from_vis.isVisible()
                and to_vis is not None
                and to_vis.isVisible()
            )
            if edge_item.is_interlayer and not show_interlayer:
                edge_item.setVisible(False)
            else:
                edge_item.setVisible(endpoints_visible)

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        """Show a context menu with available actions based on selection.

        Called by the ZoomableGraphicsView on right-click.
        """
        menu = QMenu(self)

        selected_nodes = [
            item.node_symbol for item in self._scene.selectedItems() if isinstance(item, NodeItem)
        ]
        selected_edges = [
            item for item in self._scene.selectedItems() if isinstance(item, EdgeItem)
        ]

        if len(selected_nodes) == 2:
            add_edge_action = QAction("Add Edge", self)
            add_edge_action.triggered.connect(
                lambda: self._model.add_edge(selected_nodes[0], selected_nodes[1])
            )
            menu.addAction(add_edge_action)

        if selected_nodes:
            delete_action = QAction(f"Delete {len(selected_nodes)} Node(s)", self)
            delete_action.triggered.connect(self._delete_selected_nodes)
            menu.addAction(delete_action)

        if selected_edges:
            delete_edge_action = QAction(f"Delete {len(selected_edges)} Edge(s)", self)
            delete_edge_action.triggered.connect(
                lambda: self._delete_selected_edges(selected_edges)
            )
            menu.addAction(delete_edge_action)

        if not menu.isEmpty():
            menu.exec(self._view.mapToGlobal(pos))

    def delete_selected(self):
        """Delete whatever is selected — nodes first, then edges.

        Called by the MainWindow's Delete action (keyboard shortcut).
        """
        selected_nodes = [
            item.node_symbol for item in self._scene.selectedItems() if isinstance(item, NodeItem)
        ]
        selected_edges = [
            item for item in self._scene.selectedItems() if isinstance(item, EdgeItem)
        ]

        if selected_nodes:
            self._delete_selected_nodes()
        elif selected_edges:
            self._delete_selected_edges(selected_edges)

    def _delete_selected_nodes(self):
        """Delete all selected nodes via the model, with confirmation."""
        symbols = list(self._model.selected)
        if not symbols:
            return

        reply = QMessageBox.question(
            self,
            "Delete Nodes",
            f"Delete {len(symbols)} node(s) and their edges?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for ns in symbols:
            self._model.remove_node(ns)

    def _delete_selected_edges(self, edge_items: list[EdgeItem]):
        """Delete the given edge items via the model, with confirmation."""
        if not edge_items:
            return

        reply = QMessageBox.question(
            self,
            "Delete Edges",
            f"Delete {len(edge_items)} edge(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for item in edge_items:
            self._model.remove_edge(item.from_symbol, item.to_symbol)

    # ------------------------------------------------------------------
    # Search / filter
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        """Dim nodes that don't match the search text."""
        if not text:
            # Restore all to full opacity.
            for item in self._node_items.values():
                item.setOpacity(1.0)
            return

        text_lower = text.lower()
        for ns, item in self._node_items.items():
            # Match against nodeSymbol, class, or name.
            props = self._model.get_node(ns) or {}
            searchable = f"{ns} {props.get('class', '')} {props.get('name', '')}".lower()
            item.setOpacity(1.0 if text_lower in searchable else 0.15)

    def _on_search_enter(self):
        """Select all nodes matching the current search text."""
        text = self._search_bar.text()
        if not text:
            return

        text_lower = text.lower()
        matching = []
        for ns, item in self._node_items.items():
            props = self._model.get_node(ns) or {}
            searchable = f"{ns} {props.get('class', '')} {props.get('name', '')}".lower()
            if text_lower in searchable:
                matching.append(ns)

        self._model.set_selection(matching)

    # ------------------------------------------------------------------
    # Boundary visualization
    # ------------------------------------------------------------------

    def _draw_boundaries(self):
        """Draw polygon boundary overlays for Room nodes that have boundary data."""
        from heracles import constants as hc

        room_style = STYLE_BY_LABEL.get(hc.ROOMS)
        room_color = QColor(room_style.color) if room_style else QColor("#EF553B")

        for ns, props in self._model.get_all_nodes().items():
            if self._model.get_node_layer(ns) != hc.ROOMS:
                continue
            if "boundary_x" not in props or "boundary_y" not in props:
                continue

            bx = props["boundary_x"]
            by = props["boundary_y"]
            if len(bx) < 3:
                continue

            # Convert world coords → scene coords.
            points = [QPointF(x * DEFAULT_SCALE, -y * DEFAULT_SCALE) for x, y in zip(bx, by)]
            polygon = QPolygonF(points)

            item = QGraphicsPolygonItem(polygon)
            fill = QColor(room_color)
            fill.setAlpha(30)
            item.setBrush(QBrush(fill))
            item.setPen(QPen(room_color, 1.5, Qt.DashLine))
            item.setZValue(-2)  # Behind edges and nodes
            self._scene.addItem(item)
            self._boundary_items[ns] = item

            # Respect current Room layer visibility.
            if not self._model.is_layer_visible(hc.ROOMS):
                item.setVisible(False)

    # ------------------------------------------------------------------
    # Export to image
    # ------------------------------------------------------------------

    def export_to_image(self, path: str):
        """Render the scene to a PNG file."""
        rect = self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        self._scene.render(painter, source=rect)
        painter.end()
        image.save(path)


class _ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView subclass with zoom, context menus, and polygon drawing.

    Handles three concerns:
    1. Mouse wheel zoom (always active)
    2. Right-click context menu (forwarded to GraphView, only in normal mode)
    3. Polygon drawing mode (when GraphView.polygon_mode_active is True):
       left-click places vertices, double-click closes, Escape cancels.
       Mouse move shows a preview line from the last vertex to the cursor.

    In polygon mode, normal selection (rubber-band, click-to-select) is
    disabled by setting DragMode to NoDrag.  Mouse events are routed to
    the GraphView's polygon handlers instead of the default QGraphicsView
    behavior.
    """

    def __init__(self, scene, graph_view: GraphView):
        super().__init__(scene)
        self._graph_view = graph_view
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._graph_view._show_context_menu)
        self.setMouseTracking(True)  # Needed for polygon preview line

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
        else:
            self.scale(1 / factor, 1 / factor)

    def mousePressEvent(self, event):
        if self._graph_view.polygon_mode_active and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._graph_view._on_polygon_click(scene_pos)
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._graph_view.polygon_mode_active and event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._graph_view._on_polygon_double_click(scene_pos)
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._graph_view.polygon_mode_active:
            scene_pos = self.mapToScene(event.pos())
            self._graph_view._on_polygon_mouse_move(scene_pos)
            return
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if self._graph_view.polygon_mode_active and event.key() == Qt.Key_Escape:
            self._graph_view.cancel_polygon_mode()
            return
        # Fit-to-view: press F to re-fit the graph to the viewport.
        if event.key() == Qt.Key_F and not self._graph_view.polygon_mode_active:
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
            return
        super().keyPressEvent(event)
