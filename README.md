# SGET — Scene Graph Editing Tool

Desktop application for loading, viewing, editing, and saving 3D scene graphs. Uses a Neo4j database as the live backend via [heracles](https://github.com/GoldenZephyr/heracles), with scene graph serialization via [spark_dsg](https://github.com/MIT-SPARK/Spark-DSG).

## Prerequisites

- Python 3.10+
- Neo4j 5.x (via Docker)
- `libeigen3-dev` (required to build spark_dsg: `sudo apt install libeigen3-dev`)
- `cmake` (required to build spark_dsg)
- `spark_dsg` and `heracles` installed (see below)

## Setup

### 1. Start Neo4j (Docker)

```bash
docker run -d --name neo4j-sget \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4j_pw \
  neo4j:5.25.1
```

### 2. Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
# Install spark_dsg (C++ build, requires cmake + libeigen3-dev)
pip install -e path/to/Spark-DSG/

# Install heracles
# As of 2026-04-21, this project expects heracles at commit 1a96017
# (robust-node-handling branch) for TravNodeAttributes support.
cd path/to/heracles && git checkout robust-node-handling && cd -
pip install -e path/to/heracles/heracles/

# Install SGET
pip install -e ".[dev]"
```

### 4. Set up pre-commit hooks

```bash
pre-commit install
```

## Running

```bash
# Load a scene graph file (connects to Neo4j with default credentials)
sget --file path/to/scene_graph.json

# Specify Neo4j connection
sget --neo4j-uri neo4j://127.0.0.1:7687 \
     --neo4j-user neo4j \
     --neo4j-password neo4j_pw \
     --file path/to/scene_graph.json
```

### CLI Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--neo4j-uri` | `neo4j://127.0.0.1:7687` | Neo4j bolt URI |
| `--neo4j-user` | `neo4j` | Neo4j username |
| `--neo4j-password` | `neo4j_pw` | Neo4j password |
| `--neo4j-db` | `neo4j` | Neo4j database name |
| `--file` | *(none)* | JSON scene graph file to load on startup |

## Features

### Viewing
- **2D spatial graph view** with nodes positioned by their 3D coordinates (x, -y projection)
- **Layer panel** with checkboxes to toggle layer visibility and node counts
- **Mesh visualization** as a background layer with opacity slider
- **Boundary overlays** for rooms and places (polygon, bounding box, radii)
- **Zoom/pan** with mouse wheel and drag
- **Color-coded nodes** by layer
- **Search** to find nodes by name or symbol

### Selection & Properties
- **Click** to select a node, **Ctrl+click** for multi-select, **rubber-band** drag for area select
- **Property panel** shows selected node's attributes (position, name, class, bounding box)
- **Edit and Apply** to push changes to Neo4j
- **Per-node locking** to prevent accidental drag movement

### Editing
- **Add Node** (Ctrl+N): dialog to pick layer, position, name, and class
- **Delete** (Delete key): remove selected nodes or edges
- **Add Edge**: right-click with 2 nodes selected
- **Delete Edge**: select an edge and press Delete or right-click
- **Group** (Ctrl+G): select nodes in a layer, create a parent node in the higher layer with CONTAINS edges

### Navigation
- **Focus on subtree**: select a node and focus the view on it and its descendants (BFS on CONTAINS edges)
- Layer toggles respect the focused set

### File I/O
- **File → Open JSON**: load a scene graph (clears and repopulates Neo4j)
- **File → Save As JSON**: export current Neo4j state back to JSON via heracles (optionally include mesh data)
- **File → Connect to Neo4j**: change Neo4j credentials without restarting
- **File → Refresh from DB** (Ctrl+Shift+R): re-read the database into the view (useful after external edits)

### Snapshots
- **Save/restore named snapshots** of the scene graph state
- Snapshot panel in the right dock below the property panel

## Running Tests

Tests require a running Neo4j instance on `localhost:7687` with credentials `neo4j`/`neo4j_pw`.

```bash
pytest                          # All tests
pytest tests/test_neo4j_crud.py # Just the CRUD layer
pytest tests/test_scene_graph_model.py  # Model tests
pytest -k "selection"           # Tests matching a keyword
```

## Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```
