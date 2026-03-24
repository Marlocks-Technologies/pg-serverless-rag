#!/bin/bash
set -e

# Package the shared library as a Lambda layer
echo "Packaging shared library as Lambda layer..."

# Clean previous builds
rm -rf python/
rm -f shared-layer.zip

# Create layer directory structure
mkdir -p python/lib/python3.12/site-packages

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -t python/lib/python3.12/site-packages --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12

# Copy source files
echo "Copying source files..."
cp -r src/* python/lib/python3.12/site-packages/

# Create zip file
echo "Creating layer zip..."
zip -r shared-layer.zip python/

echo "Lambda layer package created: shared-layer.zip"
echo "Size: $(du -h shared-layer.zip | cut -f1)"
