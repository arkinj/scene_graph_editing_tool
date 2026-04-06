# SGET — Scene Graph Editing Tool

Desktop application for loading, viewing, editing, and saving 3D scene graphs. Uses a Neo4j database as the live backend via the [heracles](../heracles/) library, with scene graph serialization via [spark_dsg](../Spark-DSG/).

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
python -m venv ~/software/mit/virtual-envs/sget
source ~/software/mit/virtual-envs/sget/bin/activate
```

### 3. Install dependencies

```bash
# Install spark_dsg (C++ build, requires cmake + libeigen3-dev)
pip install -e ../Spark-DSG/

# Install heracles (use the robust-node-handling branch for TravNodeAttributes support)
cd ../heracles && git checkout robust-node-handling && cd -
pip install -e ../heracles/heracles/

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

# Example DSG for testing
sget --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json

# Run with chat agent (see Chat Agent section below)
./scripts/launch_with_chat.sh --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json
```

### CLI Options

| Argument | Default | Description |
|----------|---------|-------------|
| `--neo4j-uri` | `neo4j://127.0.0.1:7687` | Neo4j bolt URI |
| `--neo4j-user` | `neo4j` | Neo4j username |
| `--neo4j-password` | `neo4j_pw` | Neo4j password |
| `--neo4j-db` | `neo4j` | Neo4j database name |
| `--file` | *(none)* | JSON scene graph file to load on startup |
| `--object-labelspace` | `ade20k_mit_label_space.yaml` | YAML labelspace for object classes |
| `--room-labelspace` | `b45_label_space.yaml` | YAML labelspace for room classes |

## Features

### Viewing
- **2D hierarchical graph view** with nodes arranged in layer bands (Buildings top → Objects bottom)
- **Layer panel** with checkboxes to toggle layer visibility and node counts
- **Zoom/pan** with mouse wheel and drag
- **Color-coded nodes** by layer

### Selection & Properties
- **Click** to select a node, **Ctrl+click** for multi-select, **rubber-band** drag for area select
- **Property panel** shows selected node's attributes (position, name, class, bounding box)
- **Edit and Apply** to push changes to Neo4j

### Editing
- **Add Node** (Ctrl+N): dialog to pick layer, position, name, and class
- **Delete** (Delete key): remove selected nodes or edges
- **Add Edge**: right-click with 2 nodes selected
- **Delete Edge**: select an edge and press Delete or right-click
- **Group** (Ctrl+G): select nodes in a layer, create a parent node in the higher layer with CONTAINS edges

### File I/O
- **File → Open JSON**: load a scene graph (clears and repopulates Neo4j)
- **File → Save As JSON**: export current Neo4j state back to JSON via heracles
- **File → Connect to Neo4j**: change Neo4j credentials without restarting
- **File → Refresh from DB** (Ctrl+Shift+R): re-read the database into the view (useful after external edits)

## Chat Agent (Natural Language Interface)

SGET can be paired with a chat agent that queries and edits the scene graph via natural language. The agent uses [heracles_agents](../heracles_agents/) to generate Cypher queries against the same Neo4j database.

### Setup

```bash
# Install heracles_agents with OpenAI support
pip install -e ~/software/mit/sget/heracles_agents/[openai]

# Set your OpenAI API key
export HERACLES_OPENAI_API_KEY='your-key'
```

### Running

```bash
# Launch SGET + chat agent together
./scripts/launch_with_chat.sh --file path/to/scene_graph.json
```

Or run them in separate terminals:

```bash
# Terminal 1: SGET
sget --file path/to/scene_graph.json

# Terminal 2: Chat agent
cd config && python ~/software/mit/sget/heracles_agents/examples/chatdsg/chatdsg.py
```

In the chat, use **Ctrl+B** to submit messages. The agent can query ("How many objects are in room R1?") and edit ("Add a new box at position 5, 5, 0"). After the agent modifies the graph, press **Ctrl+Shift+R** in SGET to refresh the view.

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
