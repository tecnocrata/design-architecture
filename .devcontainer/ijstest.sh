#!/bin/bash

echo "======= Testing IJavaScript Installation ======="
echo "Node.js version:"
node --version

echo "NPM version:"
npm --version

echo "Checking for IJavaScript installation:"
npm list -g ijavascript

echo "IJavaScript executable path:"
which ijsinstall

echo "======= Jupyter Kernel Information ======="
echo "Listing all available Jupyter kernels:"
jupyter kernelspec list

echo "======= Testing console.log availability ======="
echo 'console.log("Test")' > test.js
echo "Running simple Node.js script:"
node test.js

echo "======= .NET Information ======="
echo ".NET SDK version:"
dotnet --version

echo ".NET Interactive installation:"
dotnet tool list -g

echo "======= Environment Variables ======="
echo "PATH environment variable:"
echo $PATH 