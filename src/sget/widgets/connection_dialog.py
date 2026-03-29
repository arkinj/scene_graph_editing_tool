"""
Neo4j connection dialog.

Provides a GUI alternative to the CLI args for entering Neo4j credentials.
If the model is already connected, the dialog shows the current URI and
offers to disconnect first.  On success, emits no signals itself — the
model's ``connection_changed`` signal handles that.
"""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
)

from sget.backend.scene_graph_model import SceneGraphModel


class ConnectionDialog(QDialog):
    """Modal dialog for entering Neo4j connection parameters."""

    def __init__(self, model: SceneGraphModel, parent=None):
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Connect to Neo4j")
        self.setMinimumWidth(400)

        form = QFormLayout(self)

        self._uri_edit = QLineEdit("neo4j://127.0.0.1:7687")
        form.addRow("URI:", self._uri_edit)

        self._user_edit = QLineEdit("neo4j")
        form.addRow("Username:", self._user_edit)

        self._password_edit = QLineEdit("neo4j_pw")
        self._password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Password:", self._password_edit)

        self._db_edit = QLineEdit("neo4j")
        form.addRow("Database:", self._db_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_connect)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_connect(self):
        """Attempt to connect with the entered credentials."""
        # Disconnect existing connection if any.
        if self._model.connected:
            self._model.disconnect()

        try:
            self._model.connect(
                self._uri_edit.text(),
                self._user_edit.text(),
                self._password_edit.text(),
                self._db_edit.text(),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", str(e))
