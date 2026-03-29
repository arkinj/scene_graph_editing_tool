"""
Application entry point for SGET.

Parses CLI arguments, connects to Neo4j, optionally loads a JSON scene graph,
and launches the main window.

The labelspace arguments (--object-labelspace, --room-labelspace) specify
YAML files that map semantic label IDs to human-readable class names (e.g.,
``{34: "box", 2: "tree"}``).  These are required by heracles' bulk load to
populate the ``class`` property on Neo4j nodes.  If not provided, they
default to heracles' bundled labelspace files.
"""

import argparse
import sys

from heracles.utils import get_labelspace
from PySide6.QtWidgets import QApplication, QMessageBox

from sget.backend.scene_graph_model import SceneGraphModel
from sget.main_window import MainWindow


def parse_args():
    parser = argparse.ArgumentParser(
        prog="sget",
        description="Scene Graph Editing Tool — load, view, edit, and save 3D scene graphs",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="neo4j://127.0.0.1:7687",
        help="Neo4j bolt URI (default: neo4j://127.0.0.1:7687)",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username (default: neo4j)",
    )
    parser.add_argument(
        "--neo4j-password",
        default="neo4j_pw",
        help="Neo4j password (default: neo4j_pw)",
    )
    parser.add_argument(
        "--neo4j-db",
        default="neo4j",
        help="Neo4j database name (default: neo4j)",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Path to a scene graph JSON file to load on startup",
    )
    parser.add_argument(
        "--object-labelspace",
        default="ade20k_mit_label_space.yaml",
        help="YAML labelspace file for objects (default: heracles bundled ade20k)",
    )
    parser.add_argument(
        "--room-labelspace",
        default="b45_label_space.yaml",
        help="YAML labelspace file for rooms (default: heracles bundled b45)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    app = QApplication(sys.argv)
    model = SceneGraphModel()

    # Connect to Neo4j.
    try:
        model.connect(args.neo4j_uri, args.neo4j_user, args.neo4j_password, args.neo4j_db)
    except Exception as e:
        QMessageBox.critical(None, "Neo4j Connection Error", str(e))
        sys.exit(1)

    # Load labelspaces so heracles can map semantic IDs to class names.
    try:
        object_labels = get_labelspace(args.object_labelspace)
        room_labels = get_labelspace(args.room_labelspace)
    except Exception as e:
        QMessageBox.critical(None, "Labelspace Error", f"Failed to load labelspace: {e}")
        sys.exit(1)
    # get_labelspace returns {int_id: str_name}; model wants {str_name: int_id}.
    model.set_labelspaces(
        object_labels={v: k for k, v in object_labels.items()},
        room_labels={v: k for k, v in room_labels.items()},
    )

    # Create and show the main window.
    window = MainWindow(model)
    window.show()

    # Load a file if specified on the command line.
    if args.file:
        try:
            model.load_from_json(args.file)
        except Exception as e:
            QMessageBox.critical(window, "Load Error", str(e))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
