# SGET — Scene Graph Editing Tool

## Project Overview
Desktop GUI (PySide6) for loading, viewing, editing, and saving 3D scene graphs. Uses Neo4j as a live backend via heracles, with spark_dsg for the scene graph data model and JSON serialization.

## Tech Stack
- **PySide6** — Qt GUI framework
- **QGraphicsScene/QGraphicsView** — 2D hierarchical graph visualization
- **NetworkX** — Layout computation for 2D view
- **Neo4j** (via heracles `Neo4jWrapper`) — Database backend
- **spark_dsg** — Scene graph data model (C++/pybind11 bindings)

## Project Structure
```
src/sget/
├── app.py              # Entry point, CLI args (not yet implemented)
├── main_window.py      # QMainWindow with docks, menus, toolbar (not yet implemented)
├── backend/
│   ├── neo4j_crud.py   # Single-node/edge CRUD on Neo4j (DONE, 23 tests)
│   └── scene_graph_model.py  # Central model with Qt signals (not yet implemented)
├── views/              # 2D graph view, property panel
├── widgets/            # Layer panel, connection dialog
└── utils/              # Colors, layout, helpers
tests/
├── test_neo4j_crud.py  # CRUD tests against live Neo4j (23 tests)
└── test_placeholder.py # Import smoke test
```

## Dependencies (sibling repos under ~/software/mit/sget/)
- **spark_dsg**: `~/software/mit/sget/Spark-DSG/python/` — scene graph library with Python bindings
- **heracles**: `~/software/mit/sget/heracles/heracles/` — bridges spark_dsg ↔ Neo4j

Do NOT reference copies of these repos from other locations.

## Virtual Environment
```bash
source ~/software/mit/virtual-envs/sget/bin/activate
```

## Commands
```bash
# Install (editable)
pip install -e ".[dev]"

# Run
sget
sget --neo4j-uri neo4j://127.0.0.1:7687 --neo4j-user neo4j --neo4j-password neo4j_pw

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Test
pytest
```

## Key Conventions
- Reuse heracles and spark_dsg APIs directly — don't duplicate their code
- `heracles.constants` has layer name strings: `OBJECTS`, `PLACES`, `ROOMS`, `BUILDINGS`, `MESH_PLACES`
- Node IDs use `spark_dsg.NodeSymbol(category_char, index)` — e.g., `NodeSymbol('O', 4)` for object #4
- Scene graph layers: Objects(2), Places(3), Rooms(4), Buildings(5), MeshPlaces(20)
- Neo4j edge types: intralayer (`OBJECT_CONNECTED`, `PLACE_CONNECTED`, etc.) and interlayer (`CONTAINS`)
