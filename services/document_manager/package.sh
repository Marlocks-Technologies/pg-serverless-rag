#!/bin/bash
set -e

echo "Packaging document-manager Lambda function..."

# Clean previous build
rm -rf dist
rm -f function.zip

# Create dist directory
mkdir -p dist

# Copy source files
cp -r src/* dist/

# Create deployment package
cd dist
zip -r ../function.zip .
cd ..

# Clean up
rm -rf dist

echo "Package created: function.zip"
ls -lh function.zip
