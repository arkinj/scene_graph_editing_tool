"""
Dialog for grouping selected nodes under a new parent node.

Design
------
The user selects several nodes in a lower layer (e.g., Places), then invokes
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

When called from the polygon drawing tool, the dialog also receives boundary
vertices that are stored on the Room node as ``boundary_x``/``boundary_y``
properties in Neo4j.

Target layer filtering
----------------------
The dialog includes a "Child layer" dropdown that controls which of the
provided nodes are actually used as children.  This is useful when the
polygon tool captures nodes from multiple layers — the user can narrow
down to just Places, just MeshPlaces, or keep all.  Default is
"Places + MeshPlaces" (the natural children of a Room).
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
        boundary: list[tuple[float, float]] | None = None,
    ):
        super().__init__(parent)
        self._model = model
        self._all_selected = list(selected_symbols)
        self._boundary = boundary
        self.setWindowTitle("Group Nodes")
        self.setMinimumWidth(350)

        form = QFormLayout(self)

        # Determine available layers from the selected nodes.
        self._node_layer_map = {ns: model.get_node_layer(ns) for ns in selected_symbols}
        available_layers = sorted(set(self._node_layer_map.values()) - {None})

        if not available_layers:
            form.addRow(QLabel("Error: no valid nodes selected."))
            buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
            buttons.rejected.connect(self.reject)
            form.addRow(buttons)
            self._valid = False
            return

        self._valid = True

        # --- Child layer filter ---
        # Determines which of the selected nodes become children.
        # Default includes Places + MeshPlaces (the natural children of a Room).
        self._child_filter_combo = QComboBox()
        self._child_filter_combo.addItem("All selected", "all")
        for layer in available_layers:
            style = STYLE_BY_LABEL.get(layer)
            display = style.display_name if style else layer
            self._child_filter_combo.addItem(f"{display} only", layer)
        # If Places+MeshPlaces are both present, add a combined option.
        if "Place" in available_layers and "MeshPlace" in available_layers:
            self._child_filter_combo.insertItem(1, "Places + MeshPlaces", "Place+MeshPlace")
            self._child_filter_combo.setCurrentIndex(1)
        self._child_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        form.addRow("Include:", self._child_filter_combo)

        # Show count of included nodes.
        self._count_label = QLabel()
        form.addRow("Nodes:", self._count_label)

        # --- Parent layer picker ---
        self._parent_combo = QComboBox()
        form.addRow("Parent layer:", self._parent_combo)

        # Class for the parent.
        self._class_combo = QComboBox()
        self._class_combo.setEditable(True)
        self._parent_combo.currentIndexChanged.connect(self._on_parent_layer_changed)
        form.addRow("Parent class:", self._class_combo)

        # Name for the parent.
        self._name_edit = QLineEdit()
        form.addRow("Parent name:", self._name_edit)

        # Boundary info (if provided by polygon tool).
        if boundary:
            form.addRow("Boundary:", QLabel(f"{len(boundary)} vertices (from polygon)"))

        # OK/Cancel.
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        # Initialize based on default filter.
        self._on_filter_changed()

    def _get_filtered_symbols(self) -> list[str]:
        """Get the node symbols that pass the current child layer filter."""
        filter_value = self._child_filter_combo.currentData()
        if filter_value == "all":
            return list(self._all_selected)
        elif filter_value == "Place+MeshPlace":
            return [
                ns for ns, layer in self._node_layer_map.items() if layer in ("Place", "MeshPlace")
            ]
        else:
            return [ns for ns, layer in self._node_layer_map.items() if layer == filter_value]

    def _on_filter_changed(self):
        """Update the node count and parent layer options when filter changes."""
        filtered = self._get_filtered_symbols()
        self._count_label.setText(str(len(filtered)))

        # Determine valid parent layers based on the filtered children's layers.
        child_layers = {self._node_layer_map[ns] for ns in filtered if ns in self._node_layer_map}

        # Collect all valid parent layers across child layers.
        parent_options = set()
        for cl in child_layers:
            for pl in _PARENT_LAYERS.get(cl, []):
                parent_options.add(pl)

        self._parent_combo.clear()
        for label in sorted(parent_options):
            style = STYLE_BY_LABEL.get(label)
            display = style.display_name if style else label
            self._parent_combo.addItem(display, label)

        self._on_parent_layer_changed()

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
        CONTAINS edges from the parent to each child.  If boundary data
        was provided (from polygon tool), stores it on the parent node.

        Returns the new parent's nodeSymbol, or None if cancelled.
        """
        if self.exec() != QDialog.Accepted or not self._valid:
            return None

        filtered = self._get_filtered_symbols()
        if not filtered:
            return None

        parent_label = self._parent_combo.currentData()
        parent_symbol = _next_node_symbol(self._model, parent_label)

        # Compute centroid of filtered children's positions.
        positions = []
        for ns in filtered:
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

        # Store boundary from polygon tool (if provided).
        if self._boundary and parent_label == "Room":
            parent_props["boundary_x"] = [pt[0] for pt in self._boundary]
            parent_props["boundary_y"] = [pt[1] for pt in self._boundary]

        # Create the parent node.
        try:
            self._model.add_node(parent_label, parent_symbol, parent_props)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create parent: {e}")
            return None

        # Create CONTAINS edges from parent to each child.
        for child_ns in filtered:
            try:
                self._model.add_edge(parent_symbol, child_ns)
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to create edge to {child_ns}: {e}")

        return parent_symbol
