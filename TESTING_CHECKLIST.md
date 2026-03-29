# SGET Demo Testing Checklist

## Launch
- [ ] `source ~/software/mit/virtual-envs/sget/bin/activate`
- [ ] `sget --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json`
- [ ] Window opens without errors

## Graph View
- [ ] Nodes visible in horizontal bands (Rooms top, MeshPlaces middle, Objects bottom)
- [ ] Nodes colored differently per layer (red Rooms, orange MeshPlaces, green Objects)
- [ ] Edges drawn between nodes (dashed for CONTAINS, solid for intralayer)
- [ ] Node labels readable (nodeSymbol + class name)

## Navigation
- [ ] Mouse wheel zooms in/out
- [ ] Click and drag on empty space pans the view
- [ ] Rubber-band select: click+drag selects multiple nodes

## Selection
- [ ] Click a node → gold highlight appears
- [ ] Click a different node → previous deselects, new one highlights
- [ ] Ctrl+click → adds to selection (multiple gold highlights)
- [ ] Click empty space → clears selection

## Layer Panel
- [ ] Left dock shows 5 layers with colored swatches and node counts
- [ ] Counts match: ~5 Rooms, ~96 MeshPlaces, ~65 Objects, 0 Places, 0 Buildings
- [ ] Uncheck "Objects" → all green nodes disappear, their edges too
- [ ] Re-check "Objects" → they reappear
- [ ] Uncheck "MeshPlaces" → orange nodes and their CONTAINS edges disappear

## Property Panel
- [ ] Click a node → right panel shows its properties (nodeSymbol, layer, position, class, etc.)
- [ ] Click a different node → panel updates
- [ ] Select multiple nodes → panel shows "N nodes selected"
- [ ] Click empty space → panel shows "No node selected"
- [ ] Edit a node's name → click Apply → name updates in the model
- [ ] Edit position → Apply → node properties updated (verify via re-selecting)
- [ ] Change class dropdown → Apply → class updated

## Add Node (Phase 6)
- [ ] Edit → Add Node (Ctrl+N) → dialog opens
- [ ] Pick a layer → class dropdown populates with relevant labels
- [ ] Set position, name, class → OK → node appears in graph view
- [ ] New node appears in correct layer band
- [ ] Layer panel count increments
- [ ] Select the new node → properties show in property panel

## Delete Node (Phase 6)
- [ ] Select a node → press Delete key → node disappears from view
- [ ] Connected edges also disappear
- [ ] Layer panel count decrements
- [ ] Select multiple nodes → Delete → all removed

## Edge Operations (Phase 6)
- [ ] Select exactly 2 nodes → right-click → "Add Edge" appears in context menu
- [ ] Click "Add Edge" → edge line appears between the two nodes
- [ ] Click an edge to select it (edge becomes highlighted)
- [ ] Select edge → right-click → "Delete Edge" → edge disappears
- [ ] Nodes remain after edge deletion

## Save Round-trip
- [ ] File → Save As JSON → save to `/tmp/test_output.json`
- [ ] File → Open JSON → load `/tmp/test_output.json` → graph looks the same
- [ ] Add a node, save, reload → new node persists
- [ ] Delete a node, save, reload → node is gone

## File Menu
- [ ] File → Open JSON → pick a different file → graph rebuilds
- [ ] File → Quit (or Ctrl+Q) → app closes

## Status Bar
- [ ] Shows "Loaded: N nodes, M edges" after loading
- [ ] Shows "Added O(66) (Object)" after adding a node
- [ ] Shows file path after saving

## Notes
Write any bugs, quirks, or feature requests below:

-
