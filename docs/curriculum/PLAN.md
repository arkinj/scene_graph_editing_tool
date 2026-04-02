# Onboarding Curriculum Plan

## Context
SGET has grown to ~5,200 lines across 15 modules with two external dependencies (spark_dsg, heracles) and a Neo4j backend. A new developer (grad student / new team member) needs a structured introduction to understand the codebase before contributing. The curriculum is a series of runnable Jupyter notebooks.

## Target Audience
- Python proficient
- New to spark_dsg, heracles, Neo4j, and PySide6
- Doesn't need a deep tutorial on external tools — just enough to understand how SGET uses them

## Prerequisites for Running
- Virtual environment activated (`source ~/software/mit/virtual-envs/sget/bin/activate`)
- Neo4j running on localhost:7687 (Docker)
- SGET, spark_dsg, and heracles installed

## Notebook Structure

### Notebook 1: Scene Graphs & spark_dsg (`01_scene_graphs.ipynb`)
What a 3D scene graph is, how to load/inspect one with spark_dsg. Layers, nodes, edges, NodeSymbol, NetworkX conversion.

### Notebook 2: The Neo4j Backend (`02_neo4j_backend.ipynb`)
Connecting to Neo4j, heracles bulk load, Cypher queries, SGET CRUD layer, round-trip export.

### Notebook 3: Architecture & The Model (`03_architecture.ipynb`)
Model-signal-view pattern, SceneGraphModel demo (signals, CRUD), layer configuration (LAYER_STYLES as single source of truth, hierarchy order vs raw IDs).

### Notebook 4: Layout & Navigation (`04_layout_and_navigation.ipynb`)
Spatial layout (x,-y projection), navigation controls (pan, zoom, fit, rubber-band, search/filter).

### Notebook 5: GUI & Interaction (`05_gui_and_interaction.ipynb`)
Widget tree, three interaction modes (normal, polygon draw, focus), per-node drag, selection signal flow, incremental view updates, context menu.

### Notebook 6: Extending SGET (`06_extending_sget.ipynb`)
How to add properties, dialogs, layers, panels, interaction modes. Key subsystems (subtree queries, snapshots, chat agent). Security (ALLOWED_PROPERTIES). Running tests.

## File Structure
```
docs/curriculum/
├── PLAN.md
├── 01_scene_graphs.ipynb
├── 02_neo4j_backend.ipynb
├── 03_architecture.ipynb
├── 04_layout_and_navigation.ipynb
├── 05_gui_and_interaction.ipynb
└── 06_extending_sget.ipynb
```

## Verification
- Each notebook runs top-to-bottom without errors (with Neo4j running)
- A new developer can complete all 6 notebooks in ~2-3 hours
- After completing, the developer understands enough to:
  - Read any module in the codebase
  - Add a simple feature (e.g., new property field in the panel)
  - Debug an issue with the Neo4j pipeline
