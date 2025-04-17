import json

notebook = {
    "cells": [
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "console.log(\"Hello, world!\");"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "JavaScript (Node.js)",
            "language": "javascript",
            "name": "javascript"
        },
        "language_info": {
            "file_extension": ".js",
            "mimetype": "application/javascript",
            "name": "javascript"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open('js-demo-new.ipynb', 'w') as f:
    json.dump(notebook, f, indent=2)

print("JavaScript notebook created successfully!") 