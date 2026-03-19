#!/bin/bash
# =============================================================
# LiveYoung ERP — Double-click this from Finder to start
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="./python/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo ""
    echo "ERROR: Portable Python not found."
    echo "Run build_mac.sh first to set up the bundle."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

echo ""
echo "  LiveYoung ERP"
echo "  Starting on http://localhost:8501"
echo "  Press Ctrl+C or close this window to stop."
echo ""

(sleep 2 && open "http://localhost:8501") &

"$PYTHON" -m streamlit run app/main.py \
    --server.port 8501 \
    --server.headless true \
    --server.address localhost \
    --browser.gatherUsageStats false
