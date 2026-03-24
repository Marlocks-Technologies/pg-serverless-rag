#!/bin/bash
set -e

# Package the chat handler Lambda function
echo "Packaging chat handler Lambda function..."

# Clean previous builds
rm -rf package/
rm -f chat-handler.zip

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
