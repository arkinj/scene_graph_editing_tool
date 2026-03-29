"""
Dialog for grouping selected nodes under a new parent node.

Design
------
The user selects several nodes in a lower layer (e.g., Objects), then invokes
Group.  This dialog creates a new parent node in a higher layer and connects
it to each selected child via CONTAINS edges.

The parent layer is determined by the scene graph hierarchy:
- Objects (layer 2) → parent in Places (3) or MeshPlaces (20)
- Places (layer 3) → parent in Rooms (4)
- MeshPlaces (layer 20) → parent in Rooms (4)
- Rooms (layer 4) → parent in Buildings (5)

These constraints match heracles' edge insertion logic in graph_interface.py.

The parent node's position defaults to the centroid of the selected children,
which is a natural default for containment relationships.
"""

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import STYLE_BY_LABEL
from sget.widgets.add_node_dialog import _next_node_symbol

# Valid parent layers for each child layer, matching heracles' hierarchy.
_PARENT_LAYERS = {
    "Object": ["Place", "MeshPlace"],
    "Place": ["Room"],
    "MeshPlace": ["Room"],
    "Room": ["Building"],
}


class GroupDialog(QDialog):
    """Modal dialog for grouping selected nodes under a new parent."""

    def __init__(
        self,
        model: SceneGraphModel,
        selected_symbols: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self._model = model
        self._selected = selected_symbols
        self.setWindowTitle("Group Nodes")
        self.setMinimumWidth(350)

        form = QFormLayout(self)

        # Validate: all selected nodes must be in the same layer.
        layers = {model.get_node_layer(ns) for ns in selected_symbols}
        if len(layers) != 1:
            form.addRow(QLabel("Error: selected nodes must all be in the same layer."))
            buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
            buttons.rejected.connect(self.reject)
            form.addRow(buttons)
            self._valid = False
            return

        self._child_layer = layers.pop()
        parent_options = _PARENT_LAYERS.get(self._child_layer, [])

        if not parent_options:
            form.addRow(QLabel(f"No valid parent layer for {self._child_layer} nodes."))
            buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
            buttons.rejected.connect(self.reject)
            form.addRow(buttons)
            self._valid = False
            return

        self._valid = True

        # Show what we're grouping.
        form.addRow("Grouping:", QLabel(f"{len(selected_symbols)} {self._child_layer} node(s)"))

        # Parent layer picker.
        self._parent_combo = QComboBox()
        for label in parent_options:
            style = STYLE_BY_LABEL.get(label)
            display = style.display_name if style else label
            self._parent_combo.addItem(display, label)
        form.addRow("Parent layer:", self._parent_combo)

        # Class for the parent (from labelspace).
        self._class_combo = QComboBox()
        self._class_combo.setEditable(True)
        self._parent_combo.currentIndexChanged.connect(self._on_parent_layer_changed)
        self._on_parent_layer_changed()
        form.addRow("Parent class:", self._class_combo)

        # Name for the parent.
        self._name_edit = QLineEdit()
        form.addRow("Parent name:", self._name_edit)

        # OK/Cancel.
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_parent_layer_changed(self):
        """Update class dropdown when parent layer changes."""
        self._class_combo.clear()
        label = self._parent_combo.currentData()
        if label == "Room":
            labels = self._model.get_room_labels()
        elif label in ("Object", "MeshPlace"):
            labels = self._model.get_object_labels()
        else:
            labels = {}

        if labels:
            self._class_combo.addItems(sorted(labels.keys()))
            self._class_combo.setEnabled(True)
        else:
            self._class_combo.setEnabled(False)

    def execute_group(self) -> str | None:
        """Run the dialog and perform the grouping if accepted.

        Creates the parent node at the centroid of the children, then adds
        CONTAINS edges from the parent to each child.

        Returns the new parent's nodeSymbol, or None if cancelled.
        """
        if self.exec() != QDialog.Accepted or not self._valid:
            return None

        parent_label = self._parent_combo.currentData()
        parent_symbol = _next_node_symbol(self._model, parent_label)

        # Compute centroid of selected children's positions.
        positions = []
        for ns in self._selected:
            props = self._model.get_node(ns)
            if props and "center" in props:
                center = props["center"]
                positions.append([float(center[0]), float(center[1]), float(center[2])])

        if positions:
            centroid = np.mean(positions, axis=0)
        else:
            centroid = [0.0, 0.0, 0.0]

        # Build the parent's property dict.
        parent_props = {
            "pos_x": centroid[0],
            "pos_y": centroid[1],
            "pos_z": centroid[2],
        }

        if parent_label in ("Room", "MeshPlace"):
            parent_props["class"] = self._class_combo.currentText() or "unknown"

        if parent_label == "Object":
            parent_props["class"] = self._class_combo.currentText() or "unknown"
            parent_props["name"] = self._name_edit.text()
            parent_props["bbox_x"] = centroid[0]
            parent_props["bbox_y"] = centroid[1]
            parent_props["bbox_z"] = centroid[2]
            parent_props["bbox_l"] = 1.0
            parent_props["bbox_w"] = 1.0
            parent_props["bbox_h"] = 1.0

        # Create the parent node.
        try:
            self._model.add_node(parent_label, parent_symbol, parent_props)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create parent: {e}")
            return None

        # Create CONTAINS edges from parent to each child.
        for child_ns in self._selected:
            try:
                self._model.add_edge(parent_symbol, child_ns)
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to create edge to {child_ns}: {e}")

        return parent_symbol
