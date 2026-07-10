#!/usr/bin/env bash
# Build and deploy DC-ShiftMaster Web to Amazon S3.
#
# Usage:
#   ./build_and_deploy.sh <S3_BUCKET_NAME>
#
# Prerequisites:
#   - Python with flet installed (pip install flet)
#   - AWS CLI configured with appropriate credentials
#
# Example:
#   ./build_and_deploy.sh my-shiftmaster-bucket

set -euo pipefail

BUCKET="${1:?Usage: $0 <S3_BUCKET_NAME>}"
BUILD_DIR="build/web"

echo "==> Building Flet web app..."
flet build web --output "$BUILD_DIR"

# Verify index.html exists
if [ ! -f "$BUILD_DIR/index.html" ]; then
    echo "ERROR: index.html not found in $BUILD_DIR"
    exit 1
fi

echo "==> index.html found in $BUILD_DIR"

echo "==> Deploying to s3://$BUCKET ..."
aws s3 sync "$BUILD_DIR" "s3://$BUCKET" \
    --delete \
    --cache-control "max-age=3600"

echo "==> Done. Site available at:"
echo "    http://$BUCKET.s3-website-$(aws configure get region).amazonaws.com"
