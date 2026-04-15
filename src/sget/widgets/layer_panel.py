"""
Layer visibility panel.

Shows one row per scene graph layer with a checkbox to toggle visibility
and a label showing the node count.  Ordered from the top of the hierarchy
(Buildings) to the bottom (Objects), matching the scene graph hierarchy.

Also includes a toggle for interlayer (CONTAINS) edges, which are hidden
by default to reduce visual clutter in dense graphs.

Checkbox changes flow through the model via ``set_layer_visibility()``
and ``set_interlayer_edges_visible()``, which emit signals that the graph
view picks up.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import LAYER_STYLES


class LayerPanel(QWidget):
    """Dock widget content showing layer toggles and node counts."""

    def __init__(self, model: SceneGraphModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._checkboxes: dict[str, QCheckBox] = {}
        self._count_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        # Quick-access buttons for common editing operations.
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Node")
        self._delete_btn = QPushButton("Delete")
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._delete_btn)
        layout.addLayout(btn_row)

        for style in LAYER_STYLES:
            row = QHBoxLayout()

            # Colored swatch — small square showing the layer color.
            swatch = QLabel()
            pixmap = QPixmap(14, 14)
            pixmap.fill(QColor(style.color))
            swatch.setPixmap(pixmap)
            row.addWidget(swatch)

            # Visibility checkbox with layer name.
            cb = QCheckBox(style.display_name)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda checked, label=style.layer_label: self._model.set_layer_visibility(
                    label, checked
                )
            )
            self._checkboxes[style.layer_label] = cb
            row.addWidget(cb)

            row.addStretch()

            # Node count.
            count = QLabel("0")
            count.setStyleSheet("color: #888;")
            self._count_labels[style.layer_label] = count
            row.addWidget(count)

            layout.addLayout(row)

        # Separator before edge toggle.
        separator = QLabel("")
        separator.setFixedHeight(8)
        layout.addWidget(separator)

        # Interlayer edge toggle — off by default to reduce clutter.
        self._interlayer_cb = QCheckBox("Show CONTAINS edges")
        self._interlayer_cb.setChecked(self._model.show_interlayer_edges)
        self._interlayer_cb.toggled.connect(self._model.set_interlayer_edges_visible)
        layout.addWidget(self._interlayer_cb)

        # Mesh opacity slider — controls the background mesh image transparency.
        mesh_row = QHBoxLayout()
        mesh_label = QLabel("Mesh opacity:")
        mesh_label.setStyleSheet("color: #888;")
        mesh_row.addWidget(mesh_label)

        self._mesh_slider = QSlider(Qt.Horizontal)
        self._mesh_slider.setRange(0, 100)
        self._mesh_slider.setValue(50)  # Default 50% opacity.
        self._mesh_slider.setToolTip("Adjust mesh background transparency")
        mesh_row.addWidget(self._mesh_slider)
        layout.addLayout(mesh_row)

        # Refresh counts when the graph is loaded.
        self._model.graph_loaded.connect(self._update_counts)

    def _update_counts(self):
        """Refresh node counts from the model's cache."""
        for style in LAYER_STYLES:
            count = self._model.node_count(style.layer_label)
            self._count_labels[style.layer_label].setText(str(count))
