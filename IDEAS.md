# SGET Feature Ideas

Potential features for future development, roughly ordered by impact.
Items marked with [DONE] have been implemented.

## Implemented

- [DONE] **Fit-to-view shortcut** — press `F` to re-fit the graph
- [DONE] **Status bar selection summary** — "Selected: 3 Objects, 1 Room"
- [DONE] **Delete confirmation dialog** — prompts before deleting
- [DONE] **Boundary visualization** — Room polygon overlays
- [DONE] **Search / filter** — text field dims non-matching nodes, Enter selects matches
- [DONE] **Export to image** — File → Export Image (PNG)
- [DONE] **Drag-to-reposition** — per-node lock/unlock in property panel
- [DONE] **Add Node / Delete buttons** — quick-access in left panel
- [DONE] **Add as children** — right-click to assign child nodes to a parent
- [DONE] **Snapshots** — save/restore named states in `.sget_snapshots/`
- [DONE] **Chat agent integration** — heracles_agents TUI alongside SGET

## High Value

### Focus on Subtree
Select a Room/Region node → View → Focus (or double-click) → the view hides all nodes except the selected node's descendants (children, grandchildren, etc.). For example, selecting a Room would show only its child Places/MeshPlaces and grandchild Objects. A "Show All" button or Escape returns to the full graph. Implementation:
- Query the model for all descendants of the selected node via CONTAINS edges (transitive)
- Hide all NodeItems not in the descendant set
- Optionally re-fit the view to the visible subset
- Status bar: "Focused on R1 (42 nodes)"

### Additive Rubber-Band Selection
Hold Shift and drag to add nodes to the current selection instead of replacing it. Needs interactive debugging — Qt's `RubberBandDrag` clears the scene selection before applying, which makes the merge timing tricky. Attempted and reverted; revisit with live pair-debugging.

### Node Color Modes
Toggle coloring by different attributes instead of always by layer:
- By layer (current default)
- By class (all "tree" nodes same color, all "box" nodes different)
- By parent room (all objects in Room R1 share a color)
- Custom attribute (user picks a property, values mapped to a color scale)

Add a dropdown to the layer panel or a View menu option.

### Batch Property Editing
Select multiple nodes and change a property on all of them at once. Example: select 10 objects classified as "unknown" and reclassify them all as "tree". The property panel would show shared properties when multiple nodes of the same layer are selected, with an "Apply to All" button.

## Medium Value

### Undo/Redo
Wrap all model mutations in `QUndoCommand` subclasses and push onto a `QUndoStack`. Every mutation already flows through the model's `add_node`/`remove_node`/`update_node`/`add_edge`/`remove_edge` methods, so the wiring points are clear. Each command stores enough state to reverse itself (e.g., `RemoveNodeCommand` saves the full node properties and connected edges for restoration).

### Minimap
Small overview widget (corner of the graph view or separate dock) showing the full graph at a tiny scale with a rectangle indicating the current viewport. Click the minimap to navigate. Useful for large graphs where zoom makes it hard to maintain spatial orientation.

### Auto-Refresh from DB
Detect when the chat agent modifies Neo4j and refresh automatically. Previous implementation (window focus refresh) was removed because it caused the graph to disappear. Could revisit with a smarter approach (compare node counts before refreshing, or only refresh if the DB was actually modified). Manual Ctrl+Shift+R works for now.

### Labelspace Management Overhaul
Currently labelspaces are loaded from separate YAML files (via CLI args or heracles defaults) and injected into the DSG metadata before bulk load. This is fragile — the user must know which labelspace file matches their DSG, and if no labelspace is provided, semantic labels aren't mapped to class names.

spark_dsg supports storing labelspaces in the graph metadata (via `G.set_labelspace()` / `G.get_labelspace()`), and some DSGs already embed labelspace info in their metadata (e.g., the `"labelspaces"` key with `_l2p0` nested lists). Investigation needed:
- What formats does spark_dsg use for embedded labelspaces?
- Can heracles auto-detect and use embedded labelspaces instead of requiring YAML files?
- Can we store the labelspace in Neo4j alongside the graph (as a metadata node)?
- Can SGET's UI show/edit the labelspace (e.g., rename classes)?

Goal: eliminate the need for `--object-labelspace` and `--room-labelspace` CLI args — just load the DSG and everything works.

## Known Bugs

### Neo4j Database Clears Unexpectedly
The Neo4j database sometimes empties itself after some amount of time, causing the graph to disappear from SGET. Root cause unknown — could be a Docker container restart, a TTL setting, or an external process clearing the DB. Workaround: reload the JSON file via File → Open, or restore a snapshot.

## Deferred

### 3D Visualization
Add a 3D viewport using PyVista/pyvistaqt alongside the 2D view. The original plan included this but it was deferred to focus on the 2D editing workflow.
