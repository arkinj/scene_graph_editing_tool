"""
Main application window.

QMainWindow with 2D graph view as the central widget, layer panel as a left
dock, property panel as a right dock.  File menu for Open/Save/Connect/Quit,
Edit menu for Add Node/Delete/Group.  The model is passed in from app.py
(which handles CLI args and Neo4j connection).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import LAYER_STYLES
from sget.views.graph_view import GraphView
from sget.views.property_panel import PropertyPanel
from sget.widgets.add_node_dialog import AddNodeDialog
from sget.widgets.connection_dialog import ConnectionDialog
from sget.widgets.group_dialog import GroupDialog
from sget.widgets.layer_panel import LayerPanel


class MainWindow(QMainWindow):
    def __init__(self, model: SceneGraphModel, parent=None):
        super().__init__(parent)
        self._model = model

        self.setWindowTitle("SGET — Scene Graph Editing Tool")
        self.resize(1200, 800)

        # --- Central widget: 2D graph view ---
        self._graph_view = GraphView(model, self)
        self.setCentralWidget(self._graph_view)

        # --- Left dock: layer panel ---
        self._layer_panel = LayerPanel(model, self)
        layer_dock = QDockWidget("Layers", self)
        layer_dock.setWidget(self._layer_panel)
        layer_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, layer_dock)

        # --- Right dock: property panel ---
        self._property_panel = PropertyPanel(model, self)
        property_dock = QDockWidget("Properties", self)
        property_dock.setWidget(self._property_panel)
        property_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, property_dock)

        # --- Menu bar ---
        self._setup_menus(layer_dock, property_dock)

        # --- Status bar ---
        self.statusBar().showMessage("Ready")
        self._model.graph_loaded.connect(self._on_graph_loaded)
        self._model.connection_changed.connect(self._on_connection_changed)

        # Update layer counts on node add/remove too.
        self._model.node_added.connect(lambda *_: self._layer_panel._update_counts())
        self._model.node_removed.connect(lambda *_: self._layer_panel._update_counts())

    def _setup_menus(self, layer_dock: QDockWidget, property_dock: QDockWidget):
        # File menu.
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("&Open JSON...", self._open_json, "Ctrl+O")
        file_menu.addAction("&Save As JSON...", self._save_json, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("&Connect to Neo4j...", self._connect_neo4j)
        file_menu.addAction("&Refresh from DB", self._refresh_from_db, "Ctrl+Shift+R")
        file_menu.addSeparator()
        file_menu.addAction("&Quit", self.close, "Ctrl+Q")

        # Edit menu — node/edge operations.
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction("&Add Node...", self._add_node, "Ctrl+N")
        edit_menu.addAction(
            "&Delete Selected", self._graph_view.delete_selected, QKeySequence.Delete
        )
        edit_menu.addSeparator()
        edit_menu.addAction("&Group Selected...", self._group_selected, "Ctrl+G")
        edit_menu.addAction("&Draw Region...", self._draw_region, "Ctrl+R")

        # Set up polygon completion callback — when the polygon tool finishes,
        # it calls this to open the Group dialog with the captured nodes.
        self._graph_view._on_polygon_completed = self._on_polygon_completed

        # View menu — toggle dock visibility.
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(layer_dock.toggleViewAction())
        view_menu.addAction(property_dock.toggleViewAction())

    def _open_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Scene Graph JSON", "", "JSON files (*.json)"
        )
        if not path:
            return

        try:
            self.statusBar().showMessage(f"Loading {path}...")
            self._model.load_from_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            self.statusBar().showMessage("Load failed")

    def _save_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Scene Graph JSON", "", "JSON files (*.json)"
        )
        if not path:
            return

        try:
            self.statusBar().showMessage(f"Saving {path}...")
            self._model.save_to_json(path)
            self.statusBar().showMessage(f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self.statusBar().showMessage("Save failed")

    def _add_node(self):
        """Show the Add Node dialog and create the node if accepted."""
        dialog = AddNodeDialog(self._model, self)
        dialog.exec()
        result = dialog.get_result()
        if result is None:
            return

        layer_label, node_symbol, props = result
        try:
            self._model.add_node(layer_label, node_symbol, props)
            self.statusBar().showMessage(f"Added {node_symbol} ({layer_label})")
        except Exception as e:
            QMessageBox.critical(self, "Add Node Error", str(e))

    def _refresh_from_db(self):
        """Refresh the model cache from Neo4j.

        Useful when an external process (e.g., the chat agent) has modified
        the database directly.
        """
        try:
            self._model.refresh_from_db()
            nodes = sum(self._model.node_count(s.layer_label) for s in LAYER_STYLES)
            edges = len(self._model.get_edges())
            self.statusBar().showMessage(f"Refreshed: {nodes} nodes, {edges} edges")
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", str(e))

    def _connect_neo4j(self):
        """Show the connection dialog."""
        ConnectionDialog(self._model, self).exec()

    def _draw_region(self):
        """Enter polygon drawing mode for spatial region creation."""
        if self._graph_view.polygon_mode_active:
            # Already drawing — cancel.
            self._graph_view.cancel_polygon_mode()
            self.statusBar().showMessage("Region drawing cancelled")
            return

        self._graph_view.start_polygon_mode()
        self.statusBar().showMessage(
            "Drawing region: click to place vertices, double-click to close, Escape to cancel"
        )

    def _on_polygon_completed(
        self, captured_symbols: list[str], boundary: list[tuple[float, float]]
    ):
        """Called when the polygon tool finishes — opens Group dialog with captured nodes."""
        if not captured_symbols:
            self.statusBar().showMessage("No nodes captured by polygon")
            return

        self.statusBar().showMessage(f"Captured {len(captured_symbols)} nodes")
        dialog = GroupDialog(self._model, captured_symbols, self, boundary=boundary)
        parent_symbol = dialog.execute_group()
        if parent_symbol:
            self.statusBar().showMessage(
                f"Created region {parent_symbol} with {len(captured_symbols)} children"
            )
        else:
            self.statusBar().showMessage("Region creation cancelled")

    def _group_selected(self):
        """Show the Group dialog for the currently selected nodes."""
        selected = self._model.selected
        if len(selected) < 2:
            QMessageBox.information(
                self, "Group", "Select 2 or more nodes in the same layer to group."
            )
            return

        dialog = GroupDialog(self._model, selected, self)
        parent_symbol = dialog.execute_group()
        if parent_symbol:
            self.statusBar().showMessage(f"Grouped {len(selected)} nodes under {parent_symbol}")

    def _on_graph_loaded(self):
        nodes = sum(self._model.node_count(s.layer_label) for s in LAYER_STYLES)
        edges = len(self._model.get_edges())
        self.statusBar().showMessage(f"Loaded: {nodes} nodes, {edges} edges")

    def _on_connection_changed(self, connected: bool):
        status = "Connected to Neo4j" if connected else "Disconnected"
        self.statusBar().showMessage(status)
