#!/bin/bash

# Exit on error
set -e

echo "Installing .NET Interactive..."

# Install .NET Interactive
dotnet tool install -g Microsoft.dotnet-interactive

# Install Jupyter kernel for .NET Interactive
dotnet interactive jupyter install

echo ".NET Interactive installation complete!"
echo "Verify installation with: jupyter kernelspec list" 