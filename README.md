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
# Install spark_dsg (C++ build, requires cmake)
pip install -e ../Spark-DSG/

# Install heracles
pip install -e ../heracles/heracles/

# Install SGET
pip install -e ".[dev]"
```

### 4. Set up pre-commit hooks

```bash
pre-commit install
```

## Running

> **Note:** The GUI is under active development. The backend (Neo4j CRUD layer
> and central model) is complete. The graphical interface is not yet implemented.

```bash
# Launch with default settings (coming soon)
sget

# Specify Neo4j connection and load a scene graph file
sget --neo4j-uri neo4j://127.0.0.1:7687 \
     --neo4j-user neo4j \
     --neo4j-password neo4j_pw \
     --file path/to/scene_graph.json
```

## Running Tests

Tests require a running Neo4j instance on `localhost:7687` with credentials `neo4j`/`neo4j_pw`.

```bash
pytest
```
