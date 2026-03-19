#!/bin/bash
# =============================================================
# BUILD SCRIPT — Run this ONCE on a Mac to prepare the bundle.
# After this, the entire LiveYoung/ folder is portable.
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION="3.12.7"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    PLATFORM="aarch64-apple-darwin"
    echo "Detected Apple Silicon (M1/M2/M3)"
else
    PLATFORM="x86_64-apple-darwin"
    echo "Detected Intel Mac"
fi

PYTHON_URL="https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-${PYTHON_VERSION}+20241016-${PLATFORM}-install_only.tar.gz"

echo ""
echo "=== LiveYoung Mac Bundle Builder ==="
echo ""

# Step 1: Download portable Python
if [ ! -d "python" ]; then
    echo "Step 1: Downloading portable Python ${PYTHON_VERSION}..."
    curl -L -o python.tar.gz "$PYTHON_URL"
    echo "Extracting..."
    tar -xzf python.tar.gz
    rm python.tar.gz
    echo "  Done. Portable Python installed to ./python/"
else
    echo "Step 1: Portable Python already exists, skipping."
fi

PYTHON="./python/bin/python3"

# Step 2: Install pip packages locally
echo ""
echo "Step 2: Installing dependencies..."
$PYTHON -m pip install --upgrade pip --quiet
$PYTHON -m pip install -r requirements.txt --quiet
echo "  Done."

# Step 3: Seed database if not already done
if [ ! -f "data/liveyoung.db" ]; then
    echo ""
    echo "Step 3: Seeding database from Excel..."
    $PYTHON -m app.seed_from_excel
else
    echo ""
    echo "Step 3: Database already exists, skipping. Delete data/liveyoung.db to re-seed."
fi

# Step 4: Make run.sh executable
chmod +x run.sh

echo ""
echo "=== Build complete! ==="
echo ""
echo "The folder is now self-contained. Give the entire LiveYoung/ folder to the client."
echo "Client just double-clicks run.sh (or runs it from Terminal)."
echo ""
echo "Folder size:"
du -sh .
echo ""
