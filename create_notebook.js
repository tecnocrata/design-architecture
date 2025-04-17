const fs = require('fs');

const notebookContent = {
  cells: [
    {
      cell_type: "code",
      execution_count: null,
      metadata: {},
      outputs: [],
      source: [
        "print('Hello, world!')"
      ]
    }
  ],
  metadata: {
    kernelspec: {
      display_name: "Python 3",
      language: "python",
      name: "python3"
    },
    language_info: {
      name: "python"
    }
  },
  nbformat: 4,
  nbformat_minor: 2
};

fs.writeFileSync('python-demo.ipynb', JSON.stringify(notebookContent, null, 2));
console.log('Python notebook created successfully!'); 