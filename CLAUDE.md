# SGET — Scene Graph Editing Tool

## Project Overview
Desktop GUI (PySide6) for loading, viewing, editing, and saving 3D scene graphs. Uses Neo4j as a live backend via heracles, with spark_dsg for the scene graph data model and JSON serialization.

## Progress Tracking
Implementation progress is tracked in the plan file ONLY:
`~/.claude/plans/wondrous-moseying-wren.md`
Do NOT add status annotations (DONE, TODO, etc.) to this file or any other file.

## Tech Stack
- **PySide6** — Qt GUI framework
- **QGraphicsScene/QGraphicsView** — 2D hierarchical graph visualization
- **NetworkX** — Layout computation for 2D view
- **Neo4j** (via heracles `Neo4jWrapper`) — Database backend
- **spark_dsg** — Scene graph data model (C++/pybind11 bindings)

## Project Structure
```
src/sget/
├── app.py                  # Entry point, CLI args, Neo4j connection
├── main_window.py          # QMainWindow with graph view, layer/property docks, File menu
├── backend/
│   ├── neo4j_crud.py       # Single-node/edge CRUD on Neo4j
│   └── scene_graph_model.py # Central model: cache, Qt signals, selection
├── views/
│   ├── graph_view.py       # QGraphicsView 2D hierarchical graph
│   └── property_panel.py   # Node property editor with Apply button
├── widgets/
│   ├── layer_panel.py      # Layer visibility toggles + node counts
│   └── connection_dialog.py # Neo4j connection dialog
└── utils/
    ├── colors.py           # Per-layer colors, styling — single source of truth for layer order
    └── layout.py           # NetworkX hierarchical layout computation
tests/
├── test_neo4j_crud.py       # CRUD tests against live Neo4j
├── test_scene_graph_model.py # Model tests: CRUD, signals, selection, visibility
└── test_placeholder.py       # Import smoke test
```

## Architecture Notes
- **Single source of truth for layer config**: `utils/colors.py` defines `LAYER_STYLES` (order, colors, IDs, labels). `scene_graph_model.py` derives `LAYER_ORDER` from it. Don't define layer lists elsewhere.
- **Data flow**: JSON → spark_dsg (transient) → heracles bulk load → Neo4j → model cache → views. The spark_dsg object is NOT kept in memory.
- **Model signals**: all mutations go through SceneGraphModel, which updates Neo4j + cache and emits Qt signals. Views never talk to Neo4j directly.
- **Property panel**: converts between Neo4j's CartesianPoint format and [x,y,z] lists. The "pos" widget key maps to the "center" Neo4j property.

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

# Run (requires Neo4j running on localhost:7687)
sget --file path/to/scene_graph.json
sget --neo4j-uri neo4j://127.0.0.1:7687 --neo4j-user neo4j --neo4j-password neo4j_pw --file path.json

# Example DSG for testing
sget --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Test (requires Neo4j on localhost:7687 with neo4j/neo4j_pw)
pytest
```

## Key Conventions
- Reuse heracles and spark_dsg APIs directly — don't duplicate their code
- `heracles.constants` has layer name strings: `OBJECTS`, `PLACES`, `ROOMS`, `BUILDINGS`, `MESH_PLACES`
- Node IDs use `spark_dsg.NodeSymbol(category_char, index)` — category char varies by DSG creator (e.g., 'O' or 'o' for Objects)
- Scene graph layers: Objects(2), Places(3), Rooms(4), Buildings(5), MeshPlaces(20)
- Neo4j edge types: intralayer (`OBJECT_CONNECTED`, `PLACE_CONNECTED`, etc.) and interlayer (`CONTAINS`)
- Add comments explaining design choices, not just what code does
