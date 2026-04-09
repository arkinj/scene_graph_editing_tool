"""
Application entry point for SGET.

Parses CLI arguments, connects to Neo4j, optionally loads a JSON scene graph,
and launches the main window.

Labelspaces are read from the DSG file's embedded metadata. No external
YAML files are needed.
"""

import argparse
import os
import sys

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
        default=os.environ.get("HERACLES_NEO4J_USERNAME", "neo4j"),
        help="Neo4j username (default: $HERACLES_NEO4J_USERNAME or 'neo4j')",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("HERACLES_NEO4J_PASSWORD", "neo4j_pw"),
        help="Neo4j password (default: $HERACLES_NEO4J_PASSWORD or 'neo4j_pw')",
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

    # Create and show the main window.
    # Labelspaces are extracted from the DSG file during load_from_json().
    window = MainWindow(model)
    window.show()

    # Load a file if specified on the command line.
    if args.file:
        try:
            window.statusBar().showMessage(f"Loading {args.file}...")
            app.processEvents()  # Paint before blocking load.
            model.load_from_json(args.file)
            window.set_snapshot_dir(args.file)
        except Exception as e:
            QMessageBox.critical(window, "Load Error", str(e))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
