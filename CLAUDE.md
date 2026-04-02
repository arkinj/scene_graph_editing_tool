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
│   ├── graph_view.py       # QGraphicsView 2D spatial graph, polygon tool, focus, search
│   └── property_panel.py   # Node property editor with Apply button + lock toggle
├── widgets/
│   ├── layer_panel.py      # Layer visibility toggles, node counts, Add/Delete buttons
│   ├── add_node_dialog.py  # Dialog for creating new nodes
│   ├── group_dialog.py     # Dialog for grouping nodes under a parent
│   ├── connection_dialog.py # Neo4j connection dialog
│   └── snapshot_panel.py   # Save/restore named scene graph snapshots
└── utils/
    ├── colors.py           # Per-layer colors, styling — single source of truth for layer order
    └── layout.py           # Spatial layout: x,-y projection from 3D node positions
tests/
├── test_neo4j_crud.py       # CRUD tests against live Neo4j (23 tests)
├── test_scene_graph_model.py # Model tests: CRUD, signals, selection, visibility (24 tests)
config/
├── agent_config.yaml        # Chat agent config (OpenAI + Cypher tool)
├── agent_prompt.yaml        # Chat agent prompt with read+write Cypher examples
scripts/
├── launch_with_chat.sh      # Launches SGET + heracles_agents chat TUI side by side
```

## Architecture Notes
- **Single source of truth for layer config**: `utils/colors.py` defines `LAYER_STYLES` (order, colors, IDs, labels). `scene_graph_model.py` derives `LAYER_ORDER` from it. Don't define layer lists elsewhere.
- **Data flow**: JSON → spark_dsg (transient) → heracles bulk load → Neo4j → model cache → views. The spark_dsg object is NOT kept in memory.
- **Model signals**: all mutations go through SceneGraphModel, which updates Neo4j + cache and emits Qt signals. Views never talk to Neo4j directly.
- **Spatial layout**: nodes positioned by actual 3D coordinates (x, -y projection). Not hierarchical bands.
- **Property panel**: converts between Neo4j's CartesianPoint format and [x,y,z] lists. The "pos" widget key maps to the "center" Neo4j property.
- **Per-node locking**: each NodeItem has a locked/unlocked state controlling drag. Property panel shows the toggle.
- **Focus on subtree**: `model.get_descendants()` does BFS on CONTAINS edges; `graph_view.focus_on_node()` hides everything else. Layer toggles respect the focused set.
- **Security**: `neo4j_crud.py` validates property names against `ALLOWED_PROPERTIES` whitelist before building dynamic Cypher SET clauses.

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

# Run with chat agent (requires heracles_agents + OpenAI key)
pip install -e ~/software/mit/sget/heracles_agents/[openai]
export HERACLES_OPENAI_API_KEY='your-key'
./scripts/launch_with_chat.sh --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json

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
- Layer hierarchy order is defined by position in `LAYER_STYLES`, NOT by raw layer IDs (MeshPlaces has ID 20 but sits below Rooms ID 4)
- Add comments explaining design choices, not just what code does
