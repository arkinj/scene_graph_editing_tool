# Onboarding Curriculum Plan

## Context
SGET has grown to ~2000 lines across 10 modules with two external dependencies (spark_dsg, heracles) and a Neo4j backend. A new developer (grad student / new team member) needs a structured introduction to understand the codebase before contributing. The curriculum is a series of runnable Jupyter notebooks.

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

**Goal**: Understand what a 3D scene graph is and how to work with one in Python.

Sections:
1. **What is a scene graph?** — Brief conceptual intro: hierarchical representation of a 3D environment. Layers represent different levels of abstraction (buildings → rooms → places → objects). Nodes have 3D positions and semantic attributes. Edges encode connectivity (sibling) and containment (parent-child).

2. **Loading a scene graph from JSON** — `spark_dsg.DynamicSceneGraph.load()` with the example DSG file. Print basic stats (num nodes, num edges, num layers).

3. **Exploring layers** — Iterate `G.layers`, show layer IDs, names, node counts. Explain the layer hierarchy: Buildings(5) → Rooms(4) → Places(3) / MeshPlaces(20) → Objects(2).

4. **Inspecting nodes** — Get a node, inspect its attributes (position, name, semantic_label, bounding_box for objects). Show the NodeSymbol system (category char + index). Demonstrate parent/child/sibling relationships.

5. **Inspecting edges** — Iterate intralayer edges (siblings) and interlayer edges (CONTAINS). Show how the hierarchy is encoded.

6. **Converting to NetworkX** — `graph_to_networkx()`, inspect the resulting nx.Graph. Brief visualization with matplotlib (optional — just to show the structure).

### Notebook 2: The Neo4j Backend (`02_neo4j_backend.ipynb`)

**Goal**: Understand how the scene graph is stored in Neo4j and how SGET reads/writes it.

Sections:
1. **Connecting to Neo4j** — `Neo4jWrapper` from heracles. Connect, run a simple `RETURN 1` query to verify.

2. **Bulk loading with heracles** — Load the example DSG into Neo4j using `initialize_db()` + `spark_dsg_to_db()`. Show what this creates: 5 node labels, indexed by nodeSymbol, with Point3D properties.

3. **Querying with Cypher** — A few practical queries: count nodes per label, find objects by class, traverse CONTAINS edges, spatial queries. Keep it concise — just enough to read the code, not a Cypher tutorial.

4. **The SGET CRUD layer** — Import `sget.backend.neo4j_crud`. Demonstrate single-node create, read, update, delete. Show edge create/delete. Explain why this exists (heracles only has bulk ops).

5. **Round-trip: Neo4j → spark_dsg → JSON** — Use `db_to_spark_dsg()` to reconstruct the scene graph, save to JSON, compare with original.

### Notebook 3: The SGET Architecture (`03_sget_architecture.ipynb`)

**Goal**: Understand how the application is structured so the developer can modify and extend it.

Sections:
1. **Architecture overview** — Diagram of the data flow (JSON → spark_dsg → Neo4j → cache → views). Explain the model-signal-view pattern.

2. **The SceneGraphModel** — Walk through key methods: `load_from_json`, `add_node`, `update_node`, `remove_node`. Show signal emissions with a SignalSpy (from the tests). Demonstrate the dual-store design (cache + Neo4j).

3. **Layer configuration** — `utils/colors.py` as single source of truth. Show how LAYER_STYLES drives the model, layout, and views.

4. **The 2D layout** — `utils/layout.py`. Compute a layout from the model cache, show the positions. Explain the hierarchical band approach.

5. **The GUI (conceptual)** — Explain the widget tree: MainWindow → GraphView (central), LayerPanel (left dock), PropertyPanel (right dock). How signals flow between model and views. How to add a new panel or view.

6. **Extending SGET** — Practical pointers: where to add a new node type, how to add a new property to the editor, how to add a new menu action.

## File Structure
```
docs/curriculum/
├── PLAN.md              # This file
├── 01_scene_graphs.ipynb
├── 02_neo4j_backend.ipynb
└── 03_sget_architecture.ipynb
```

## Verification
- Each notebook runs top-to-bottom without errors (with Neo4j running)
- A new developer can complete all 3 notebooks in ~2 hours
- After completing, the developer understands enough to:
  - Read any module in the codebase
  - Add a simple feature (e.g., new property field in the panel)
  - Debug an issue with the Neo4j pipeline
