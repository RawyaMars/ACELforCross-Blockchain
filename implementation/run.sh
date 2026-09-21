#!/usr/bin/env bash

set -euo pipefail

export PATH="$HOME/.local/graphviz/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/.local/graphviz/usr/lib/x86_64-linux-gnu:$HOME/.local/graphviz/usr/lib/x86_64-linux-gnu/graphviz"
export GVBINDIR="$HOME/.local/graphviz/usr/lib/x86_64-linux-gnu/graphviz"

cd "$(dirname "$0")/src"
python3 run_pipeline.py "$@"
