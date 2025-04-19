# Multi-Language Jupyter Development Container

This repository contains a development container setup for running Jupyter notebooks with multiple language kernels: Python, C# (.NET), and JavaScript.

## Setup Instructions

1. Install [Docker](https://www.docker.com/products/docker-desktop) on your system
2. Install [Visual Studio Code](https://code.visualstudio.com/)
3. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VS Code
4. Open this repository in VS Code
5. When prompted, click "Reopen in Container" or use the command palette (F1) and select "Remote-Containers: Reopen in Container"

## Features

The container includes:

- Ubuntu base image
- Python 3.10 with Jupyter and data science packages
- .NET 8 SDK
- Node.js with IJavaScript kernel

## Running Jupyter Notebooks

To start Jupyter Notebook from the terminal:

```bash
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

Then open the provided URL in your browser.

## Language Support

### Python

Python is ready to use out of the box. Select the Python 3 kernel when creating a new notebook.

### C# (.NET)

C# support requires manual installation of .NET Interactive. After the container is running, execute:

```bash
.devcontainer/install-dotnet-interactive.sh
```

If successful, you can then select the ".NET Interactive" kernel when creating a notebook.

### JavaScript

JavaScript support is provided via IJavaScript. To use it, select the "JavaScript (Node.js)" kernel when creating a notebook.

Example JavaScript code:

```javascript
// Use console.log to print output
console.log("Hello, World!");

// Define variables and functions
let x = 10;
function add(a, b) {
  return a + b;
}
console.log(add(x, 5));
```

## Troubleshooting

If you encounter issues with any of the kernels:

1. Verify kernel installation:

```bash
jupyter kernelspec list
```

2. For JavaScript issues, verify IJavaScript installation:

```bash
which ijsinstall
npm list -g ijavascript
```

3. For .NET issues, verify .NET Interactive installation:

```bash
dotnet tool list -g
```

If you have trouble with .NET Interactive installation, try:

```bash
# Check current .NET version
dotnet --version

# Manually install .NET Interactive
dotnet tool install -g Microsoft.dotnet-interactive --version 1.0.505401
dotnet interactive jupyter install
```
