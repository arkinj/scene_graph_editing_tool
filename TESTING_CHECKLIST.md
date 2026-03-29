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

## File Menu
- [ ] File → Open JSON → pick a different file → graph rebuilds
- [ ] File → Save As JSON → save to `/tmp/test_output.json`
- [ ] File → Open JSON → load `/tmp/test_output.json` → looks the same
- [ ] File → Quit (or Ctrl+Q) → app closes

## Status Bar
- [ ] Shows "Loaded: N nodes, M edges" after loading
- [ ] Shows file path after saving

## Notes
Write any bugs, quirks, or feature requests below:

-
