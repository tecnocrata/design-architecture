# Multi-Language Jupyter Development Container

This repository contains a development container setup for running Jupyter notebooks with Python support.

## Setup Instructions

1. Install [Docker](https://www.docker.com/products/docker-desktop) on your system
2. Install [Visual Studio Code](https://code.visualstudio.com/)
3. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VS Code
4. Open this repository in VS Code
5. When prompted, click "Reopen in Container" or use the command palette (F1) and select "Remote-Containers: Reopen in Container"

## Example Files

- `jupyter_python_example.ipynb`: Sample Python Jupyter notebook
- `jupyter_csharp_example.cs`: C# example code (requires additional setup, see below)
- `jupyter_javascript_example.js`: JavaScript example code (requires additional setup, see below)

## Running Examples

To run the examples, start Jupyter Notebook from the terminal:

```bash
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

Then open the provided URL in your browser.

### Python

Python support is ready to use out of the box. Simply open the `jupyter_python_example.ipynb` file or create a new notebook with the Python 3 kernel.

### C# (Optional Setup)

For C# support in Jupyter, you need to manually install .NET Interactive:

1. Install .NET 9 SDK (if not already installed)
2. Install the .NET Interactive tools:
   ```
   dotnet tool install -g Microsoft.dotnet-interactive
   dotnet interactive jupyter install
   ```

After installation, you can create a new notebook and select the ".NET Interactive" kernel.

### JavaScript (Optional Setup)

For JavaScript support in Jupyter, you would need to manually install IJavaScript:

> **Note:** IJavaScript is currently not included in the default setup due to compatibility issues with ARM64 architecture. If you're running on x86_64, you can manually install it by running:
>
> ```bash
> apt-get update && apt-get install -y libzmq3-dev
> npm install -g ijavascript
> ijsinstall
> ```

## Environment Details

The development container includes:

- Ubuntu base image
- Python 3.10 with Jupyter and essential data science packages
- .NET 7.0 SDK
- Node.js
- VS Code extensions for each language and Jupyter support
