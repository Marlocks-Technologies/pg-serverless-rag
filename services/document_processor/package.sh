#!/bin/bash
set -e

# Package the document processor Lambda function
echo "Packaging document processor Lambda function..."

# Clean previous builds
rm -rf package/
rm -f document-processor.zip

# Create package directory
mkdir -p package

# Copy handler and source files
echo "Copying source files..."
cp -r src/* package/

# Create zip file
echo "Creating function zip..."
cd package
zip -r ../function.zip .
cd ..

echo "Lambda function package created: function.zip"
echo "Size: $(du -h function.zip | cut -f1)"
echo ""
echo "Note: This function requires the shared library Lambda layer to be attached."
