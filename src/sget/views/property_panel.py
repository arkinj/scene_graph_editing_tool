"""
Node property editor panel.

Design
------
When a single node is selected, this panel displays its properties in an
editable form.  The user can modify values and click "Apply" to push changes
to Neo4j through the model.

The panel adapts its fields based on the node's layer:
- All nodes: nodeSymbol (read-only), layer (read-only), position (x/y/z)
- Objects: + name, class, bbox_center, bbox_dim
- Rooms, MeshPlaces: + class
- Places, Buildings: (no extra fields)

When multiple nodes are selected, the panel shows a count summary instead.
When nothing is selected, the panel is empty.

Neo4j Point3D values
--------------------
Neo4j returns 3D coordinates as ``neo4j.spatial.CartesianPoint`` objects,
which behave like sequences [x, y, z].  We read them as such and convert
back to [x, y, z] lists for ``model.update_node()``.
"""

from heracles import constants as hc
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import STYLE_BY_LABEL

# Large range for position spinboxes — scene graphs can span wide areas.
_POS_MIN = -10000.0
_POS_MAX = 10000.0
_POS_DECIMALS = 4


class PropertyPanel(QWidget):
    """Dock widget content for viewing and editing node properties."""

    def __init__(self, model: SceneGraphModel, graph_view=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._graph_view = graph_view
        self._current_symbol: str | None = None

        # Outer layout with scroll area — the form can grow tall for Objects.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self._form_container = QWidget()
        scroll.setWidget(self._form_container)
        self._form_layout = QFormLayout(self._form_container)

        # Placeholder shown when nothing is selected.
        self._empty_label = QLabel("No node selected")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888;")
        self._form_layout.addRow(self._empty_label)

        # Track editable widgets so we can read values on Apply.
        self._widgets: dict[str, QWidget] = {}
        self._apply_btn: QPushButton | None = None

        # Listen for selection changes.
        self._model.selection_changed.connect(self._on_selection_changed)
        self._model.node_updated.connect(self._on_node_updated)

    def _on_selection_changed(self, selected: list):
        if len(selected) == 1:
            self._show_node(selected[0])
        elif len(selected) > 1:
            self._show_multi(len(selected))
        else:
            self._show_empty()

    def _on_node_updated(self, node_symbol: str, layer_label: str):
        """Refresh if the updated node is currently displayed."""
        if self._current_symbol == node_symbol:
            self._show_node(node_symbol)

    # ------------------------------------------------------------------
    # Display states
    # ------------------------------------------------------------------

    def _clear_form(self):
        """Remove all rows from the form layout."""
        while self._form_layout.rowCount() > 0:
            self._form_layout.removeRow(0)
        self._widgets = {}
        self._apply_btn = None
        self._current_symbol = None

    def _show_empty(self):
        self._clear_form()
        self._empty_label = QLabel("No node selected")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888;")
        self._form_layout.addRow(self._empty_label)

    def _show_multi(self, count: int):
        self._clear_form()
        label = QLabel(f"{count} nodes selected")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #888;")
        self._form_layout.addRow(label)

    def _show_node(self, node_symbol: str):
        """Populate the form with the node's current properties."""
        self._clear_form()
        self._current_symbol = node_symbol

        props = self._model.get_node(node_symbol)
        layer_label = self._model.get_node_layer(node_symbol)
        if props is None or layer_label is None:
            self._show_empty()
            return

        style = STYLE_BY_LABEL.get(layer_label)

        # --- Read-only fields ---
        self._form_layout.addRow("Node ID:", self._make_readonly(props.get("nodeSymbol", "")))
        self._form_layout.addRow(
            "Layer:", self._make_readonly(style.display_name if style else layer_label)
        )
        if "attr_type" in props:
            self._form_layout.addRow("Type:", self._make_readonly(props["attr_type"]))

        # --- Lock toggle (controls whether the node can be dragged) ---
        if self._graph_view is not None:
            locked = self._graph_view.is_node_locked(node_symbol)
            lock_cb = QCheckBox("Locked")
            lock_cb.setChecked(locked)
            lock_cb.toggled.connect(
                lambda checked, ns=node_symbol: self._graph_view.set_node_locked(ns, checked)
            )
            self._form_layout.addRow("Position:", lock_cb)

        # --- Position fields ---
        center = props.get("center", [0, 0, 0])
        pos_widget, pos_spins = self._make_vec3("pos", center)
        self._form_layout.addRow("", pos_widget)

        # --- Name (Objects have this, may be empty string) ---
        if "name" in props:
            name_edit = QLineEdit(str(props["name"]))
            self._widgets["name"] = name_edit
            self._form_layout.addRow("Name:", name_edit)

        # --- Class (Objects, Rooms, MeshPlaces) ---
        if "class" in props:
            class_combo = QComboBox()
            class_combo.setEditable(True)
            # Populate with known labels from the model's labelspace.
            current_class = str(props["class"])
            labels = self._model.get_object_labels()
            if layer_label == hc.ROOMS:
                labels = self._model.get_room_labels()

            class_names = sorted(labels.keys()) if labels else []
            if current_class and current_class not in class_names:
                class_names.insert(0, current_class)

            class_combo.addItems(class_names)
            idx = class_combo.findText(current_class)
            if idx >= 0:
                class_combo.setCurrentIndex(idx)
            self._widgets["class"] = class_combo
            self._form_layout.addRow("Class:", class_combo)

        # --- Radii (MeshPlaces with TravNodeAttributes) ---
        if "min_radius" in props:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 10000.0)
            spin.setDecimals(4)
            spin.setValue(float(props["min_radius"]))
            self._widgets["min_radius"] = spin
            self._form_layout.addRow("Min Radius:", spin)

        if "max_radius" in props:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 10000.0)
            spin.setDecimals(4)
            spin.setValue(float(props["max_radius"]))
            self._widgets["max_radius"] = spin
            self._form_layout.addRow("Max Radius:", spin)

        # --- Bounding box (Objects only) ---
        if "bbox_center" in props:
            bc = props["bbox_center"]
            bc_widget, _ = self._make_vec3("bbox_center", bc)
            self._form_layout.addRow("BBox Center:", bc_widget)

        if "bbox_dim" in props:
            bd = props["bbox_dim"]
            bd_widget, _ = self._make_vec3("bbox_dim", bd)
            self._form_layout.addRow("BBox Size:", bd_widget)

        # --- Boundary (Rooms with polygon data, or Place2d Point3D list) ---
        if "boundary_x" in props and "boundary_y" in props:
            n_verts = len(props["boundary_x"])
            self._form_layout.addRow("Boundary:", self._make_readonly(f"{n_verts} vertices"))
        elif "boundary" in props and isinstance(props["boundary"], list):
            self._form_layout.addRow(
                "Boundary:", self._make_readonly(f"{len(props['boundary'])} points")
            )

        # --- Read-only info fields ---
        if "color_r" in props:
            rgb = f"({props['color_r']}, {props['color_g']}, {props['color_b']})"
            self._form_layout.addRow("Color:", self._make_readonly(rgb))

        if "registered" in props:
            self._form_layout.addRow("Registered:", self._make_readonly(str(props["registered"])))

        if "distance" in props:
            self._form_layout.addRow("Distance:", self._make_readonly(f"{props['distance']:.4f}"))

        if "is_active" in props:
            self._form_layout.addRow("Active:", self._make_readonly(str(props["is_active"])))

        if "first_observed_ns" in props:
            val = props["first_observed_ns"]
            display = str(val) if not isinstance(val, list) else f"[{len(val)} timestamps]"
            self._form_layout.addRow("First Observed:", self._make_readonly(display))

        if "radii" in props:
            self._form_layout.addRow("Radii:", self._make_readonly(f"{len(props['radii'])} rays"))

        # --- Apply button ---
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        self._form_layout.addRow("", self._apply_btn)

    # ------------------------------------------------------------------
    # Apply changes
    # ------------------------------------------------------------------

    def _on_apply(self):
        """Collect edited values and push to the model."""
        if self._current_symbol is None:
            return

        updates = {}

        # Collect vec3 fields (center, bbox_center, bbox_dim).
        for key in ("pos", "bbox_center", "bbox_dim"):
            x_key = f"{key}_x"
            if x_key in self._widgets:
                x = self._widgets[x_key].value()
                y = self._widgets[f"{key}_y"].value()
                z = self._widgets[f"{key}_z"].value()
                # "pos" maps to the "center" property in Neo4j.
                prop_name = "center" if key == "pos" else key
                updates[prop_name] = [x, y, z]

        # Scalar fields.
        if "name" in self._widgets:
            updates["name"] = self._widgets["name"].text()

        if "class" in self._widgets:
            class_name = self._widgets["class"].currentText()
            updates["class"] = class_name
            # Register the label if the user typed a new one.
            layer_label = self._model.get_node_layer(self._current_symbol)
            if layer_label == hc.ROOMS:
                self._model.add_room_label(class_name)
            elif layer_label in (hc.OBJECTS, hc.MESH_PLACES):
                self._model.add_object_label(class_name)

        for radius_key in ("min_radius", "max_radius"):
            if radius_key in self._widgets:
                updates[radius_key] = self._widgets[radius_key].value()

        if updates:
            try:
                self._model.update_node(self._current_symbol, updates)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.critical(self, "Update Error", str(e))

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _make_readonly(self, text: str) -> QLabel:
        label = QLabel(str(text))
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _make_vec3(self, key_prefix: str, values) -> tuple[QWidget, list[QDoubleSpinBox]]:
        """Create a vertical stack of 3 spin boxes for a 3D vector.

        Stacked vertically so the property panel can stay narrow and give
        more room to the central graph view.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        spins = []
        for i, axis in enumerate(("x", "y", "z")):
            spin = QDoubleSpinBox()
            spin.setRange(_POS_MIN, _POS_MAX)
            spin.setDecimals(_POS_DECIMALS)
            spin.setValue(float(values[i]))
            spin.setPrefix(f"{axis}: ")
            layout.addWidget(spin)
            widget_key = f"{key_prefix}_{axis}"
            self._widgets[widget_key] = spin
            spins.append(spin)

        return container, spins
