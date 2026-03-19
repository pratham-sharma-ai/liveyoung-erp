#!/bin/bash
# =============================================================
# LiveYoung ERP — Double-click this or run from Terminal
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="./python/bin/python3"

# Check if portable Python exists
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
echo "  Press Ctrl+C to stop."
echo ""

# Open browser after a short delay
(sleep 2 && open "http://localhost:8501") &

# Run Streamlit
$PYTHON -m streamlit run app/main.py \
    --server.port 8501 \
    --server.headless true \
    --server.address localhost \
    --browser.gatherUsageStats false
