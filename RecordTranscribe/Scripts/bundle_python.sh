#!/bin/bash
#
# Bundle Python environment into RecordTranscribe.app
#
# This script:
# 1. Creates a standalone Python environment
# 2. Installs all required dependencies
# 3. Copies everything into the .app bundle
# 4. Optionally pre-downloads models
#
# Usage: ./bundle_python.sh [--with-models]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_NAME="RecordTranscribe"
BUILD_DIR="${PROJECT_DIR}/build"
PYTHON_ENV_DIR="${BUILD_DIR}/python-env"
PYTHON_VERSION="3.12"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
WITH_MODELS=false
for arg in "$@"; do
    case $arg in
        --with-models)
            WITH_MODELS=true
            shift
            ;;
    esac
done

# Check for required tools
if ! command -v uv &> /dev/null; then
    log_error "uv is required but not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Find Xcode build
log_info "Looking for Xcode build..."
XCODE_BUILD=$(find ~/Library/Developer/Xcode/DerivedData/RecordTranscribe-* -path "*/Build/Products/Debug/${APP_NAME}.app" -type d 2>/dev/null | grep -v "Index.noindex" | head -1)

if [ -z "$XCODE_BUILD" ]; then
    log_error "No Xcode build found. Build the app in Xcode first (⌘B)"
    exit 1
fi

log_info "Found Xcode build: ${XCODE_BUILD}"

# Create build directory
log_info "Creating build directory..."
mkdir -p "${BUILD_DIR}"

# Create standalone Python environment
log_info "Creating standalone Python ${PYTHON_VERSION} environment..."
cd "${BUILD_DIR}"

if [ -d "${PYTHON_ENV_DIR}" ]; then
    log_warn "Removing existing Python environment..."
    rm -rf "${PYTHON_ENV_DIR}"
fi

# Use uv to create a venv with all dependencies
log_info "Creating virtual environment with uv..."
uv venv "${PYTHON_ENV_DIR}" --python ${PYTHON_VERSION}

# Install dependencies
log_info "Installing dependencies (this may take a few minutes)..."

# Core dependencies for macOS Apple Silicon
# Install numba first with correct version for Python 3.12
uv pip install --python "${PYTHON_ENV_DIR}/bin/python" \
    "numba>=0.60.0" \
    "llvmlite>=0.43.0"

# Then install the rest
uv pip install --python "${PYTHON_ENV_DIR}/bin/python" \
    "numpy>=1.26.0" \
    "mlx>=0.22.0" \
    "parakeet-mlx==0.4.0" \
    "mlx-lm>=0.19.0" \
    "huggingface-hub>=0.20.0"

log_info "Python environment created successfully!"

# Copy Xcode build to our build directory for bundling
DIST_APP="${BUILD_DIR}/${APP_NAME}.app"
log_info "Copying app bundle to build directory..."
rm -rf "${DIST_APP}"
cp -R "${XCODE_BUILD}" "${DIST_APP}"

# Bundle Python into app
log_info "Bundling Python into app..."
RESOURCES_DIR="${DIST_APP}/Contents/Resources"
mkdir -p "${RESOURCES_DIR}/PythonService"

# Copy Python service script
cp "${PROJECT_DIR}/PythonService/transcription_service.py" "${RESOURCES_DIR}/PythonService/"

# Copy Python environment
log_info "Copying Python environment (this may take a while)..."
cp -R "${PYTHON_ENV_DIR}" "${RESOURCES_DIR}/"

# Copy sound files if not already there
if [ -f "${PROJECT_DIR}/RecordTranscribe/Resources/start.mp3" ]; then
    cp "${PROJECT_DIR}/RecordTranscribe/Resources/start.mp3" "${RESOURCES_DIR}/" 2>/dev/null || true
    cp "${PROJECT_DIR}/RecordTranscribe/Resources/stop.mp3" "${RESOURCES_DIR}/" 2>/dev/null || true
fi

# Pre-download models if requested
if [ "$WITH_MODELS" = true ]; then
    log_info "Pre-downloading models (this will take a while - ~2GB)..."

    # Download models using the bundled Python
    "${RESOURCES_DIR}/python-env/bin/python" << 'PYTHON_SCRIPT'
from huggingface_hub import snapshot_download
import os

# Get the Resources directory (where this script's python lives)
resources_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
models_cache = os.path.expanduser("~/.cache/huggingface/hub")

print('Downloading Parakeet STT model...')
snapshot_download('mlx-community/parakeet-tdt-0.6b-v3')

print('Downloading Qwen cleanup model...')
snapshot_download('mlx-community/Qwen2.5-1.5B-Instruct-4bit')

print('Models downloaded to HuggingFace cache!')
print(f'Cache location: {models_cache}')
PYTHON_SCRIPT

    log_info "Models downloaded to HuggingFace cache"
fi

# Calculate bundle size
BUNDLE_SIZE=$(du -sh "${DIST_APP}" | cut -f1)
log_info ""
log_info "========================================="
log_info "Bundle complete!"
log_info "========================================="
log_info "App: ${DIST_APP}"
log_info "Size: ${BUNDLE_SIZE}"
log_info ""
log_info "To test the app:"
log_info "  open '${DIST_APP}'"
log_info ""
log_info "To create a DMG for distribution:"
log_info "  ./create_dmg.sh"
