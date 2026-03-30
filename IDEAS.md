# SGET Feature Ideas

Potential features for future development, roughly ordered by impact.

## High Value, Low Effort

### Fit-to-View Keyboard Shortcut
Press `F` to re-fit the graph view after zooming/panning too far. Currently easy to lose your place in a large graph. Implementation: call `_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)` on keypress.

### Status Bar Selection Summary
Show "Selected: 3 Objects, 1 Room" in the status bar instead of just highlighting nodes. Useful context before grouping or deleting. Wire to `selection_changed` signal.

### Delete Confirmation Dialog
Currently the Delete key removes nodes immediately with no undo. A "Delete 5 nodes and their edges?" confirmation prompt would prevent accidental data loss. Simple `QMessageBox.question()` in `delete_selected()`.

## High Value, Moderate Effort

### Boundary Visualization
Render Room polygon boundaries as persistent semi-transparent overlays on the graph view. We already store `boundary_x`/`boundary_y` on Room nodes but don't visualize them after creation. On `graph_loaded`, iterate Room nodes with boundary data and create `QGraphicsPolygonItem` overlays. Toggle visibility with the Room layer checkbox.

### Search / Filter
A text field (top of the graph view or in a toolbar) to search for nodes by symbol, class, or name. Matching nodes highlighted, non-matching dimmed. With 166+ nodes, finding a specific one by clicking is tedious. Could also filter the graph to show only matching nodes.

### Auto-Refresh from DB
Detect when the chat agent (or another external process) modifies Neo4j, and refresh SGET's cache automatically. Options:
- Poll Neo4j on a timer (e.g., every 5 seconds, compare node count)
- Refresh on window focus (`QWidget.focusInEvent`)
- File-based signal (agent writes a trigger file, SGET watches with `QFileSystemWatcher`)

Window focus is the simplest and least intrusive.

## Medium Value, Higher Effort

### Undo/Redo
Wrap all model mutations in `QUndoCommand` subclasses and push onto a `QUndoStack`. Every mutation already flows through the model's `add_node`/`remove_node`/`update_node`/`add_edge`/`remove_edge` methods, so the wiring points are clear. Each command stores enough state to reverse itself (e.g., `RemoveNodeCommand` saves the full node properties and connected edges for restoration).

### Batch Property Editing
Select multiple nodes and change a property on all of them at once. Example: select 10 objects classified as "unknown" and reclassify them all as "tree". The property panel would show shared properties when multiple nodes of the same layer are selected, with an "Apply to All" button.

### Export to Image
Save the current graph view as PNG or SVG for papers and presentations. `QGraphicsScene.render()` to a `QPainter` on a `QImage` or `QSvgGenerator`. Add File → Export Image menu action.

### Node Color Modes
Toggle coloring by different attributes instead of always by layer:
- By layer (current default)
- By class (all "tree" nodes same color, all "box" nodes different)
- By parent room (all objects in Room R1 share a color)
- Custom attribute (user picks a property, values mapped to a color scale)

Add a dropdown to the layer panel or a View menu option.

### Minimap
Small overview widget (corner of the graph view or separate dock) showing the full graph at a tiny scale with a rectangle indicating the current viewport. Click the minimap to navigate. Useful for large graphs where zoom makes it hard to maintain spatial orientation. Qt provides `QGraphicsView` which can be pointed at the same scene with a different transform.

## Deferred

### 3D Visualization
Add a 3D viewport using PyVista/pyvistaqt alongside the 2D view. The original plan included this but it was deferred to focus on the 2D editing workflow. Would show nodes at their true 3D positions with bounding boxes and allow 3D picking.
