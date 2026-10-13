#!/bin/sh
# runs the rocket demos one after another, never at the same time (copy 2 first, then the current code)
cd "$(dirname "$0")/../.." || exit 1
export DEMO_HOLD_S=90
.venv/bin/python benchmarks/demo/rocket_excalidraw.py copy2_v2 /private/tmp/claude-501/comex-copy2 > benchmarks/demo/rocket_copy2_v2.out 2>&1
.venv/bin/python benchmarks/demo/rocket_excalidraw.py current_v2 . > benchmarks/demo/rocket_current_v2.out 2>&1
echo QUEUE_FINISHED > benchmarks/demo/queue_done.flag
