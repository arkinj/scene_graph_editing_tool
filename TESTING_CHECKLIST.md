# SGET Testing Checklist

## Launch ✅
- [x] `source ~/software/mit/virtual-envs/sget/bin/activate`
- [x] `sget --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json`
- [x] Window opens without errors
- [x] Layout: graph view (center), layer panel (left), properties (right), snapshots (right)

## Graph View — Spatial Layout ✅
- [x] Nodes positioned spatially (reflecting real-world x,y coordinates)
- [x] Nodes colored by layer (red Rooms, orange MeshPlaces, green Objects)
- [x] Intralayer edges visible (solid gray lines between sibling nodes)
- [x] CONTAINS edges hidden by default (no dashed lines on initial load)
- [x] Node labels readable (nodeSymbol + class name)

## Navigation ✅
- [x] Mouse wheel zooms in/out
- [x] Click and drag on empty space pans the view
- [x] Shift+drag for rubber-band select
- [x] Press `F` to fit the graph to the viewport after zooming

## Search / Filter ✅
- [x] Search bar visible above the graph view
- [x] Type "seating" → only seating nodes at full opacity, others dimmed
- [x] Clear search → all nodes restored to full opacity
- [x] Type "R1" → press Enter → Room R1 gets selected
- [x] Type nonsense → no nodes match, all dimmed

## Selection ✅
- [x] Click a node → gold highlight appears
- [x] Click a different node → previous deselects, new one highlights
- [x] Ctrl+click → adds to selection (multiple gold highlights)
- [x] Click empty space → clears selection
- [x] Status bar shows selection summary: "Selected: 3 Objects, 1 Room"

## Layer Panel ✅
- [x] Left dock shows 5 layers with colored swatches and node counts
- [x] Counts match: ~5 Rooms, ~96 MeshPlaces, ~65 Objects, 0 Places, 0 Buildings
- [x] Uncheck "Objects" → all green nodes disappear, their edges too
- [x] Re-check "Objects" → they reappear
- [x] "Show CONTAINS edges" checkbox (unchecked by default)
- [x] Check it → dashed CONTAINS edges appear between layers
- [x] Uncheck → CONTAINS edges disappear again

## Property Panel ✅
- [x] Click a node → right panel shows properties (nodeSymbol, layer, position, class)
- [x] Click a different node → panel updates
- [x] Select multiple nodes → panel shows "N nodes selected"
- [x] Click empty space → panel shows "No node selected"
- [x] Edit a node's name → click Apply → name persists (re-select to verify)
- [x] Edit position → Apply → node moves visually in graph view
- [x] Change class dropdown → Apply → class updated

## Add Node
- [ ] Edit → Add Node (Ctrl+N) → dialog opens
- [ ] Pick a layer → class dropdown populates with relevant labels
- [ ] Set position, name, class → OK → node appears in graph view
- [ ] Layer panel count increments
- [ ] Select the new node → properties show in property panel

## Delete (with confirmation)
- [ ] Select a node → press Delete → confirmation dialog appears
- [ ] Click "No" → nothing deleted
- [ ] Click "Yes" → node and connected edges disappear
- [ ] Layer panel count decrements
- [ ] Select multiple nodes → Delete → "Delete N node(s)?" prompt → confirm → all removed

## Edge Operations
- [ ] Select exactly 2 different nodes → right-click → "Add Edge" in context menu
- [ ] Click "Add Edge" → edge line appears between the two nodes
- [ ] Select only 1 node → right-click → no "Add Edge" option (self-edge prevented)
- [ ] Click an edge to select it
- [ ] Select edge → right-click → "Delete Edge" → confirm → edge disappears
- [ ] Nodes remain after edge deletion

## Draw Region (Polygon Tool)
- [ ] Edit → Draw Region (Ctrl+R) → cursor changes to crosshair
- [ ] Status bar shows "Drawing region: click to place vertices..."
- [ ] Click to place vertices → semi-transparent blue polygon overlay appears
- [ ] Mouse move shows preview line from last vertex to cursor
- [ ] Double-click to close → Group dialog opens with captured nodes
- [ ] Dialog shows child layer filter (default: Places + MeshPlaces)
- [ ] Set parent class → OK → new Room node created with CONTAINS edges
- [ ] Press Escape during drawing → polygon cancelled, cursor restored
- [ ] Double-click with <3 vertices → drawing cancelled (no crash)

## Group Nodes
- [ ] Select 2+ nodes in same layer (Ctrl+click) → Edit → Group (Ctrl+G)
- [ ] Dialog shows "Include" filter, node count, parent layer options
- [ ] Pick parent layer → set class → OK → parent node created
- [ ] CONTAINS edges from parent to each child (toggle "Show CONTAINS edges" to verify)
- [ ] Layer panel counts update
- [ ] Select nodes from different layers → dialog shows appropriate filter options

## Boundary Visualization
- [ ] **Room**: after creating via Draw Region, polygon boundary overlay visible
- [ ] **Room**: rooms with bounding box but no polygon show a rectangle overlay
- [ ] **TravNode (MeshPlace)**: polar polygon boundaries visible (from radii data)
- [ ] **Object**: bounding box rectangles visible as overlays
- [ ] All boundaries: semi-transparent fill with dashed border, colored by layer
- [ ] Toggle layer visibility → boundaries hide/show per layer
- [ ] Focus on subtree → only focused node boundaries visible
- [ ] To switch TravNode boundaries between polar polygon and rectangle: change `USE_POLAR_BOUNDARY` in graph_view.py

## Snapshots
- [ ] Snapshots panel visible in right dock (below Properties)
- [ ] "initial_load" snapshot auto-created on first load
- [ ] Click "Save Snapshot" → name dialog appears
- [ ] Enter a name → snapshot saved, appears in list with timestamp and node/edge counts
- [ ] Make some edits (add/delete nodes)
- [ ] Click "Restore" on the snapshot → confirm → graph reverts to saved state
- [ ] Click "Delete" on a snapshot → confirm → snapshot removed from list
- [ ] Save multiple snapshots → listed newest first
- [ ] Snapshots stored in `.sget_snapshots/` next to the loaded JSON file

## Connection Dialog
- [ ] File → Connect to Neo4j → dialog opens
- [ ] Enter correct credentials → OK → status bar shows "Connected to Neo4j"
- [ ] Enter wrong credentials → error message appears

## File I/O
- [ ] File → Open JSON → pick a file → graph rebuilds
- [ ] File → Save As JSON → save to `/tmp/test_output.json`
- [ ] File → Open JSON → load `/tmp/test_output.json` → graph looks the same
- [ ] File → Export Image → save as PNG → file contains the graph view
- [ ] File → Refresh from DB (Ctrl+Shift+R) → "Refreshed: N nodes, M edges"
- [ ] File → Quit (Ctrl+Q) → app closes

## Save Round-trip
- [ ] Load → add a node → Save As → reload → new node persists
- [ ] Load → delete a node → Save As → reload → node is gone
- [ ] Load → edit property → Apply → Save As → reload → edit persists

## Chat Agent (optional, requires OpenAI key)
- [ ] `export HERACLES_OPENAI_API_KEY='your-key'`
- [ ] `./scripts/launch_with_chat.sh --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json`
- [ ] SGET window opens, chat TUI starts in terminal
- [ ] In chat: "How many objects?" → agent returns count
- [ ] In chat: "Create a new box at 5,5,0" → agent runs CREATE Cypher
- [ ] In SGET: Ctrl+Shift+R → view refreshes with new node
- [ ] Ctrl+B to submit in chat, Ctrl+C to exit

## Notes
- **Known bug**: Neo4j database clears unexpectedly after some time (see IDEAS.md)
- Auto-refresh on window focus was removed (caused graph disappearance); use Ctrl+Shift+R instead
