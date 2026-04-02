"""
Snapshot panel for saving and restoring scene graph states.

Design
------
Snapshots are JSON files stored in a ``.sget_snapshots/`` directory next to
the loaded scene graph file.  Each snapshot is a full scene graph export
(via the model's ``save_to_json``), so restoring one is equivalent to
loading a new file.

The panel shows a list of saved snapshots with metadata (name, timestamp,
node/edge counts) and provides Save, Restore, and Delete operations.

Snapshot file naming: ``{name}_{timestamp}.json`` where the timestamp
ensures uniqueness even if the user reuses a name.  Metadata (display name,
node/edge counts) is stored in the JSON filename and read back from the
file on disk.

The snapshot directory is determined by the path of the currently loaded
file.  If no file has been loaded (or the model was populated some other
way), the panel shows a message asking the user to load a file first.
"""

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sget.backend.scene_graph_model import SceneGraphModel
from sget.utils.colors import LAYER_STYLES

# Name of the hidden directory that stores snapshots alongside the DSG file.
_SNAPSHOT_DIR_NAME = ".sget_snapshots"


class SnapshotPanel(QWidget):
    """Dock widget for managing scene graph snapshots."""

    def __init__(self, model: SceneGraphModel, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._snapshot_dir: Path | None = None

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignTop)

        # Save button.
        self._save_btn = QPushButton("Save Snapshot")
        self._save_btn.clicked.connect(self._on_save)
        outer.addWidget(self._save_btn)

        # Scrollable list of snapshots.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._list_container)
        outer.addWidget(scroll)

        # Placeholder when no snapshots exist.
        self._empty_label = QLabel("No snapshots yet")
        self._empty_label.setStyleSheet("color: #888;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._list_layout.addWidget(self._empty_label)

        # Refresh the list when a graph is loaded.
        self._model.graph_loaded.connect(self._refresh_list)

    def set_snapshot_dir(self, loaded_file_path: str):
        """Set the snapshot directory based on the loaded file's location.

        Called by MainWindow after loading a file.  Creates the directory
        if it doesn't exist.  Auto-saves an "initial" snapshot so the user
        can always revert to the original state.
        """
        parent_dir = Path(loaded_file_path).parent
        self._snapshot_dir = parent_dir / _SNAPSHOT_DIR_NAME
        self._snapshot_dir.mkdir(exist_ok=True)

        # Auto-save the initial state if no snapshots exist yet.
        existing = list(self._snapshot_dir.glob("*.json"))
        if not existing:
            self._save_snapshot("initial_load")

        self._refresh_list()

    # ------------------------------------------------------------------
    # Save / Restore / Delete
    # ------------------------------------------------------------------

    def _on_save(self):
        """Prompt for a name and save the current state as a snapshot."""
        if self._snapshot_dir is None:
            QMessageBox.information(self, "Snapshots", "Load a scene graph file first.")
            return

        name, ok = QInputDialog.getText(self, "Save Snapshot", "Snapshot name:")
        if not ok or not name.strip():
            return

        name = name.strip().replace(" ", "_")
        self._save_snapshot(name)

    def _save_snapshot(self, name: str):
        """Save the current state as a named snapshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        n_nodes = sum(self._model.node_count(s.layer_label) for s in LAYER_STYLES)
        n_edges = len(self._model.get_edges())
        filename = f"{name}__{timestamp}__{n_nodes}n_{n_edges}e.json"

        path = self._snapshot_dir / filename
        try:
            self._model.save_to_json(str(path))
            self._refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Snapshot Error", str(e))

    def _on_restore(self, path: Path):
        """Restore a snapshot by loading it as the current scene graph."""
        reply = QMessageBox.question(
            self,
            "Restore Snapshot",
            f"Restore '{path.name}'?\nThis will replace the current scene graph.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._model.load_from_json(str(path))
        except Exception as e:
            QMessageBox.critical(self, "Restore Error", str(e))

    def _on_delete(self, path: Path):
        """Delete a snapshot file."""
        reply = QMessageBox.question(
            self,
            "Delete Snapshot",
            f"Delete '{path.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            path.unlink()
            self._refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", str(e))

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _refresh_list(self):
        """Rebuild the snapshot list from the directory on disk."""
        # Clear existing entries.
        while self._list_layout.count() > 0:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if self._snapshot_dir is None or not self._snapshot_dir.exists():
            self._empty_label = QLabel("Load a file to enable snapshots")
            self._empty_label.setStyleSheet("color: #888;")
            self._empty_label.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(self._empty_label)
            return

        # List snapshot files, newest first.
        snapshots = sorted(self._snapshot_dir.glob("*.json"), key=os.path.getmtime, reverse=True)

        if not snapshots:
            label = QLabel("No snapshots yet")
            label.setStyleSheet("color: #888;")
            label.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(label)
            return

        for snap_path in snapshots:
            entry = self._make_entry_widget(snap_path)
            self._list_layout.addWidget(entry)

    def _make_entry_widget(self, path: Path) -> QWidget:
        """Create a widget for a single snapshot entry.

        Parses the filename to extract: display name, timestamp, node/edge counts.
        Filename format: ``{name}__{timestamp}__{nodes}n_{edges}e.json``
        """
        entry = QWidget()
        layout = QVBoxLayout(entry)
        layout.setContentsMargins(4, 4, 4, 4)

        # Parse filename.
        stem = path.stem  # e.g., "before_rooms__20260329_142300__166n_443e"
        parts = stem.split("__")

        display_name = parts[0].replace("_", " ") if len(parts) >= 1 else stem
        timestamp_str = ""
        counts_str = ""

        if len(parts) >= 2:
            # Parse timestamp: 20260329_142300 → 2026-03-29 14:23:00
            try:
                ts = datetime.strptime(parts[1], "%Y%m%d_%H%M%S")
                timestamp_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                timestamp_str = parts[1]

        if len(parts) >= 3:
            counts_str = parts[2].replace("_", ", ").replace("n", " nodes").replace("e", " edges")

        # Name label (bold).
        name_label = QLabel(f"<b>{display_name}</b>")
        layout.addWidget(name_label)

        # Metadata line.
        meta_parts = [s for s in [timestamp_str, counts_str] if s]
        if meta_parts:
            meta_label = QLabel(" | ".join(meta_parts))
            meta_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(meta_label)

        # Buttons row.
        btn_row = QHBoxLayout()
        restore_btn = QPushButton("Restore")
        restore_btn.clicked.connect(lambda _, p=path: self._on_restore(p))
        btn_row.addWidget(restore_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda _, p=path: self._on_delete(p))
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Visual separator.
        entry.setStyleSheet("QWidget { border-bottom: 1px solid #ddd; }")

        return entry
