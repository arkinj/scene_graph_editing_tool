"""
Dialog for adding a new node to the scene graph.

Collects the layer, position, name, and class from the user, generates a
fresh nodeSymbol, and returns the data needed for ``model.add_node()``.

NodeSymbol generation
---------------------
Each layer uses a category character (e.g., 'O' for Objects, 'R' for Rooms).
To generate a unique symbol, we scan the model's existing nodes for the
highest index in that category and increment.  This mirrors the approach
described in the plan (NodeIdAllocator concept) but kept simple — a function
rather than a separate class, since we only need it here.
"""

from heracles import constants as hc
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import LAYER_STYLES, STYLE_BY_LABEL


def _next_node_symbol(model: SceneGraphModel, layer_label: str) -> str:
    """Generate the next available nodeSymbol for a layer.

    Scans existing nodeSymbols in the cache across ALL known category
    characters for the layer (e.g., both 'O' and 'o' for Objects, both
    'P' and 't' for MeshPlaces), finds the max index, and returns
    the first (default) category char + (max_index + 1).

    For example, if MeshPlaces has P0, P5, t1, t160, this returns "P(161)".
    """
    style = STYLE_BY_LABEL.get(layer_label)
    if style is None:
        raise ValueError(f"Unknown layer: {layer_label}")

    cats = style.category_chars
    max_idx = -1

    for ns in model.get_all_nodes():
        for cat in cats:
            if ns.startswith(cat):
                rest = ns[len(cat) :].strip("()")
                try:
                    idx = int(rest)
                    max_idx = max(max_idx, idx)
                except ValueError:
                    continue

    # Use the first category char as the default for new nodes.
    return f"{cats[0]}({max_idx + 1})"


class AddNodeDialog(QDialog):
    """Modal dialog for creating a new scene graph node."""

    def __init__(self, model: SceneGraphModel, parent=None):
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Add Node")
        self.setMinimumWidth(350)

        form = QFormLayout(self)

        # Layer picker.
        self._layer_combo = QComboBox()
        for style in LAYER_STYLES:
            self._layer_combo.addItem(style.display_name, style.layer_label)
        # Default to Objects (last in list, most commonly added).
        self._layer_combo.setCurrentIndex(len(LAYER_STYLES) - 1)
        self._layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        form.addRow("Layer:", self._layer_combo)

        # Position.
        pos_widget = QWidget()
        pos_layout = QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        self._pos_spins = []
        for axis in ("x", "y", "z"):
            spin = QDoubleSpinBox()
            spin.setRange(-10000, 10000)
            spin.setDecimals(2)
            spin.setPrefix(f"{axis}: ")
            pos_layout.addWidget(spin)
            self._pos_spins.append(spin)
        form.addRow("Position:", pos_widget)

        # Name (optional, mainly for Objects).
        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        # Class (from labelspace).
        self._class_combo = QComboBox()
        self._class_combo.setEditable(True)
        form.addRow("Class:", self._class_combo)
        self._class_row_label = "Class:"

        # OK/Cancel buttons.
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        # Populate class dropdown for the default layer.
        self._on_layer_changed()

    def _on_layer_changed(self):
        """Update the class dropdown when the layer changes."""
        self._class_combo.clear()
        layer_label = self._layer_combo.currentData()

        if layer_label == hc.ROOMS:
            labels = self._model.get_room_labels()
        elif layer_label in (hc.OBJECTS, hc.MESH_PLACES):
            labels = self._model.get_object_labels()
        else:
            labels = {}

        if labels:
            self._class_combo.addItems(sorted(labels.keys()))
            self._class_combo.setEnabled(True)
        else:
            self._class_combo.setEnabled(False)

    def get_result(self) -> tuple[str, str, dict] | None:
        """Return (layer_label, node_symbol, props) or None if cancelled.

        The props dict is in the flat format expected by neo4j_crud.create_node.
        """
        if self.result() != QDialog.Accepted:
            return None

        layer_label = self._layer_combo.currentData()
        node_symbol = _next_node_symbol(self._model, layer_label)

        props = {
            "pos_x": self._pos_spins[0].value(),
            "pos_y": self._pos_spins[1].value(),
            "pos_z": self._pos_spins[2].value(),
        }

        # Layer-specific properties.
        # Class is required for Objects and Rooms. For MeshPlaces it's
        # optional — newer DSGs use TravNodeAttributes without semantic labels.
        if layer_label in (hc.OBJECTS, hc.ROOMS):
            props["class"] = self._class_combo.currentText() or "unknown"
        elif layer_label == hc.MESH_PLACES and self._class_combo.currentText():
            props["class"] = self._class_combo.currentText()

        if layer_label == hc.OBJECTS:
            props["name"] = self._name_edit.text()
            # Default bounding box at the node position with unit dimensions.
            props["bbox_x"] = props["pos_x"]
            props["bbox_y"] = props["pos_y"]
            props["bbox_z"] = props["pos_z"]
            props["bbox_l"] = 1.0
            props["bbox_w"] = 1.0
            props["bbox_h"] = 1.0

        return layer_label, node_symbol, props
