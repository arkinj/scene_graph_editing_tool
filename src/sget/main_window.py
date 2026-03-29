"""
Main application window.

2D graph view as the central widget, layer panel as a left dock, property
panel as a right dock, and a File menu for Open/Save/Quit.  The model is
passed in from app.py (which handles CLI args and Neo4j connection).
"""

from PySide6.QtCore import Qt
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

    def _setup_menus(self, layer_dock: QDockWidget, property_dock: QDockWidget):
        # File menu.
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("&Open JSON...", self._open_json, "Ctrl+O")
        file_menu.addAction("&Save As JSON...", self._save_json, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("&Quit", self.close, "Ctrl+Q")

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

    def _on_graph_loaded(self):
        nodes = sum(self._model.node_count(s.layer_label) for s in LAYER_STYLES)
        edges = len(self._model.get_edges())
        self.statusBar().showMessage(f"Loaded: {nodes} nodes, {edges} edges")

    def _on_connection_changed(self, connected: bool):
        status = "Connected to Neo4j" if connected else "Disconnected"
        self.statusBar().showMessage(status)
