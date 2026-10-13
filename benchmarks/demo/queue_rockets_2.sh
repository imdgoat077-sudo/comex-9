#!/bin/sh
# waits for the first queue (flag file), then re-runs copy 2 with the same model as every other run (env override only)
cd "$(dirname "$0")/../.." || exit 1
while [ ! -f benchmarks/demo/queue_done.flag ]; do sleep 5; done
export DEMO_HOLD_S=90 MODEL_NAME=ag/gemini-3.8-flash
.venv/bin/python benchmarks/demo/rocket_excalidraw.py copy2fix_v2 /private/tmp/claude-501/comex-copy2 > benchmarks/demo/rocket_copy2fix_v2.out 2>&1
echo DONE > benchmarks/demo/queue2_done.flag
