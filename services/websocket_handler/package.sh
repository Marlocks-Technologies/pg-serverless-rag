#!/bin/bash
set -e

echo "Packaging websocket-handler Lambda function..."

# Clean previous build
rm -rf package
rm -f function.zip

# Create package directory
mkdir -p package

# Copy source files
echo "Copying source files..."
cp -r src/* package/

# Create function zip
echo "Creating function zip..."
cd package
zip -r ../function.zip . > /dev/null
cd ..

# Clean up
rm -rf package

echo "Lambda function package created: function.zip"
SIZE=$(ls -lh function.zip | awk '{print $5}')
echo "Size: $SIZE"
echo ""
echo "Note: This function requires the shared library Lambda layer to be attached."
