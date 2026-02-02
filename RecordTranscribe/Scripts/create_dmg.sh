#!/bin/bash
#
# Create a DMG installer for RecordTranscribe
#
# Usage: ./create_dmg.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_NAME="RecordTranscribe"
BUILD_DIR="${PROJECT_DIR}/build"
APP_BUNDLE="${BUILD_DIR}/Build/Products/Release/${APP_NAME}.app"
DMG_NAME="${APP_NAME}-$(date +%Y%m%d)"
DMG_PATH="${BUILD_DIR}/${DMG_NAME}.dmg"
STAGING_DIR="${BUILD_DIR}/dmg-staging"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if app bundle exists
if [ ! -d "$APP_BUNDLE" ]; then
    log_error "App bundle not found at: ${APP_BUNDLE}"
    log_error "Run bundle_python.sh first!"
    exit 1
fi

# Clean up previous staging
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

# Copy app to staging
log_info "Staging application..."
cp -R "${APP_BUNDLE}" "${STAGING_DIR}/"

# Create Applications symlink
ln -s /Applications "${STAGING_DIR}/Applications"

# Remove old DMG if exists
rm -f "${DMG_PATH}"

# Create DMG
log_info "Creating DMG..."
hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${STAGING_DIR}" \
    -ov -format UDZO \
    "${DMG_PATH}"

# Clean up staging
rm -rf "${STAGING_DIR}"

# Get DMG size
DMG_SIZE=$(du -h "${DMG_PATH}" | cut -f1)

log_info ""
log_info "DMG created successfully!"
log_info "  Path: ${DMG_PATH}"
log_info "  Size: ${DMG_SIZE}"
log_info ""
log_info "To install:"
log_info "  1. Open ${DMG_PATH}"
log_info "  2. Drag RecordTranscribe to Applications"
