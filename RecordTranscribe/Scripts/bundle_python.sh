#!/bin/bash
#
# Bundle Python environment into RecordTranscribe.app
#
# This script:
# 1. Creates a standalone Python environment using python-build-standalone
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

# Activate and install dependencies
log_info "Installing dependencies..."
source "${PYTHON_ENV_DIR}/bin/activate"

# Core dependencies for macOS Apple Silicon
uv pip install \
    numpy>=1.26.0 \
    mlx>=0.22.0 \
    parakeet-mlx>=0.1.0 \
    mlx-lm>=0.19.0

log_info "Python environment created successfully!"

# Get the app bundle path
APP_BUNDLE="${PROJECT_DIR}/build/Build/Products/Release/${APP_NAME}.app"

if [ ! -d "$APP_BUNDLE" ]; then
    log_warn "App bundle not found at ${APP_BUNDLE}"
    log_warn "Build the app in Xcode first (Product > Build)"
    log_info "Python environment is ready at: ${PYTHON_ENV_DIR}"
    log_info ""
    log_info "After building in Xcode, run this script again to bundle Python."

    # Create the Resources directory structure for manual copying
    RESOURCES_DIR="${BUILD_DIR}/Resources"
    mkdir -p "${RESOURCES_DIR}/PythonService"

    # Copy Python service
    cp "${PROJECT_DIR}/PythonService/transcription_service.py" "${RESOURCES_DIR}/PythonService/"

    # Copy Python environment
    log_info "Copying Python environment to staging..."
    cp -R "${PYTHON_ENV_DIR}" "${RESOURCES_DIR}/"

    log_info ""
    log_info "Staged resources at: ${RESOURCES_DIR}"
    log_info "Copy these to: RecordTranscribe.app/Contents/Resources/"

    if [ "$WITH_MODELS" = true ]; then
        log_info ""
        log_info "Pre-downloading models..."
        MODELS_DIR="${RESOURCES_DIR}/models"
        mkdir -p "${MODELS_DIR}"

        # Download models using Python
        "${PYTHON_ENV_DIR}/bin/python" -c "
from huggingface_hub import snapshot_download
import os

models_dir = '${MODELS_DIR}'

print('Downloading Parakeet STT model...')
snapshot_download(
    'mlx-community/parakeet-tdt-0.6b-v3',
    local_dir=os.path.join(models_dir, 'parakeet-tdt-0.6b-v3'),
    local_dir_use_symlinks=False
)

print('Downloading Qwen cleanup model...')
snapshot_download(
    'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
    local_dir=os.path.join(models_dir, 'Qwen2.5-1.5B-Instruct-4bit'),
    local_dir_use_symlinks=False
)

print('Models downloaded successfully!')
"
        log_info "Models downloaded to: ${MODELS_DIR}"
    fi

    exit 0
fi

# Bundle into app
log_info "Bundling Python into app..."
RESOURCES_DIR="${APP_BUNDLE}/Contents/Resources"
mkdir -p "${RESOURCES_DIR}/PythonService"

# Copy Python service script
cp "${PROJECT_DIR}/PythonService/transcription_service.py" "${RESOURCES_DIR}/PythonService/"

# Copy Python environment
log_info "Copying Python environment (this may take a while)..."
cp -R "${PYTHON_ENV_DIR}" "${RESOURCES_DIR}/"

# Copy cleanup prompt if it exists
if [ -f "${PROJECT_DIR}/../cleanup_prompt.txt" ]; then
    cp "${PROJECT_DIR}/../cleanup_prompt.txt" "${RESOURCES_DIR}/"
fi

# Pre-download models if requested
if [ "$WITH_MODELS" = true ]; then
    log_info "Pre-downloading models..."
    MODELS_DIR="${RESOURCES_DIR}/models"
    mkdir -p "${MODELS_DIR}"

    # Download models using the bundled Python
    "${RESOURCES_DIR}/python-env/bin/python" -c "
from huggingface_hub import snapshot_download
import os

models_dir = '${MODELS_DIR}'

print('Downloading Parakeet STT model...')
snapshot_download(
    'mlx-community/parakeet-tdt-0.6b-v3',
    local_dir=os.path.join(models_dir, 'parakeet-tdt-0.6b-v3'),
    local_dir_use_symlinks=False
)

print('Downloading Qwen cleanup model...')
snapshot_download(
    'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
    local_dir=os.path.join(models_dir, 'Qwen2.5-1.5B-Instruct-4bit'),
    local_dir_use_symlinks=False
)

print('Models downloaded successfully!')
"
fi

# Calculate bundle size
BUNDLE_SIZE=$(du -sh "${APP_BUNDLE}" | cut -f1)
log_info "Bundle complete! Size: ${BUNDLE_SIZE}"

log_info ""
log_info "App bundle ready at: ${APP_BUNDLE}"
log_info ""
log_info "To test the app:"
log_info "  open '${APP_BUNDLE}'"
log_info ""
log_info "To create a DMG for distribution:"
log_info "  ./create_dmg.sh"
