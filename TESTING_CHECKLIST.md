# SGET Testing Checklist

## Launch
- [ ] `source ~/software/mit/virtual-envs/sget/bin/activate`
- [ ] `sget --file ~/software/mit/sget/heracles/heracles/examples/scene_graphs/example_dsg.json`
- [ ] Window opens without errors
- [ ] Layout: graph view (center), layer panel (left), properties (right), snapshots (right)

## Graph View — Spatial Layout
- [ ] Nodes positioned spatially (reflecting real-world x,y coordinates)
- [ ] Nodes colored by layer (red Rooms, orange MeshPlaces, green Objects)
- [ ] Intralayer edges visible (solid gray lines between sibling nodes)
- [ ] CONTAINS edges hidden by default (no dashed lines on initial load)
- [ ] Node labels readable (nodeSymbol + class name)

## Navigation
- [ ] Mouse wheel zooms in/out
- [ ] Click and drag on empty space pans the view
- [ ] Rubber-band select: click+drag selects multiple nodes
- [ ] Press `F` to fit the graph to the viewport after zooming

## Search / Filter
- [ ] Search bar visible above the graph view
- [ ] Type "seating" → only seating nodes at full opacity, others dimmed
- [ ] Clear search → all nodes restored to full opacity
- [ ] Type "R1" → press Enter → Room R1 gets selected
- [ ] Type nonsense → no nodes match, all dimmed

## Selection
- [ ] Click a node → gold highlight appears
- [ ] Click a different node → previous deselects, new one highlights
- [ ] Ctrl+click → adds to selection (multiple gold highlights)
- [ ] Click empty space → clears selection
- [ ] Status bar shows selection summary: "Selected: 3 Objects, 1 Room"

## Layer Panel
- [ ] Left dock shows 5 layers with colored swatches and node counts
- [ ] Counts match: ~5 Rooms, ~96 MeshPlaces, ~65 Objects, 0 Places, 0 Buildings
- [ ] Uncheck "Objects" → all green nodes disappear, their edges too
- [ ] Re-check "Objects" → they reappear
- [ ] "Show CONTAINS edges" checkbox (unchecked by default)
- [ ] Check it → dashed CONTAINS edges appear between layers
- [ ] Uncheck → CONTAINS edges disappear again

## Property Panel
- [ ] Click a node → right panel shows properties (nodeSymbol, layer, position, class)
- [ ] Click a different node → panel updates
- [ ] Select multiple nodes → panel shows "N nodes selected"
- [ ] Click empty space → panel shows "No node selected"
- [ ] Edit a node's name → click Apply → name persists (re-select to verify)
- [ ] Edit position → Apply → node properties updated
- [ ] Change class dropdown → Apply → class updated

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
- [ ] After creating a Room via Draw Region, the Room's polygon boundary is visible
- [ ] Boundary shown as semi-transparent overlay with dashed border
- [ ] Uncheck "Rooms" in layer panel → boundary overlay disappears
- [ ] Re-check → boundary reappears

## Snapshots
- [ ] Snapshots panel visible in right dock (below Properties)
- [ ] Shows "No snapshots yet" initially
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

## Auto-Refresh
- [ ] Alt-tab away from SGET and back → graph refreshes from DB
- [ ] Status bar does NOT flash errors during normal alt-tab
- [ ] If Neo4j is modified externally, alt-tab back picks up changes

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
- [ ] Alt-tab to SGET → view auto-refreshes with new node
- [ ] Ctrl+B to submit in chat, Ctrl+C to exit

## Notes
Write any bugs, quirks, or feature requests below:

-
