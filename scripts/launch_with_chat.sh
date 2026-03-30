#!/bin/bash
# Launch SGET alongside the chat agent.
#
# Usage:
#   ./scripts/launch_with_chat.sh --file path/to/scene_graph.json
#
# Prerequisites:
#   - Virtual environment activated
#   - Neo4j running on localhost:7687
#   - HERACLES_OPENAI_API_KEY set
#   - heracles_agents installed: pip install -e ~/software/mit/sget/heracles_agents/[openai]
#
# This script launches SGET in the background and the chat agent in the
# foreground. When you exit the chat (Ctrl+C), SGET is also terminated.
# Both processes share the same Neo4j database. After the agent modifies
# the graph, press Ctrl+Shift+R in SGET to refresh the view.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SGET_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$SGET_DIR/config"
CHATDSG="$HOME/software/mit/sget/heracles_agents/examples/chatdsg/chatdsg.py"

# Check prerequisites.
if [ -z "$HERACLES_OPENAI_API_KEY" ]; then
    echo "Error: HERACLES_OPENAI_API_KEY is not set."
    echo "  export HERACLES_OPENAI_API_KEY='your-key'"
    exit 1
fi

if ! command -v sget &>/dev/null; then
    echo "Error: sget not found. Is the virtual environment activated?"
    exit 1
fi

if [ ! -f "$CHATDSG" ]; then
    echo "Error: chatdsg.py not found at $CHATDSG"
    echo "  Install heracles_agents: pip install -e ~/software/mit/sget/heracles_agents/[openai]"
    exit 1
fi

# Set Neo4j env vars for heracles_agents (if not already set).
export HERACLES_NEO4J_USERNAME="${HERACLES_NEO4J_USERNAME:-neo4j}"
export HERACLES_NEO4J_PASSWORD="${HERACLES_NEO4J_PASSWORD:-neo4j_pw}"
export ADT4_HERACLES_IP="${ADT4_HERACLES_IP:-127.0.0.1}"
export ADT4_HERACLES_PORT="${ADT4_HERACLES_PORT:-7687}"
export HERACLES_AGENTS_PATH="$HOME/software/mit/sget/heracles_agents"

# Launch SGET in the background.
echo "Starting SGET..."
sget "$@" &
SGET_PID=$!

# Give SGET a moment to start.
sleep 1

# Launch the chat agent in the foreground.
echo "Starting chat agent (Ctrl+B to submit, Ctrl+C to exit)..."
cd "$CONFIG_DIR"
python "$CHATDSG"

# When chat exits, also stop SGET.
echo "Shutting down SGET..."
kill $SGET_PID 2>/dev/null
wait $SGET_PID 2>/dev/null
echo "Done."
