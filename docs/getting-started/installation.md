# Installation

## Requirements

- Python 3.9+
- pip

## Install from PyPI

```bash
pip install antflow
```

## Install from Source

```bash
git clone https://github.com/rodolfonobrega/antflow.git
cd antflow
pip install -e ".[dev]"
```

## Verify Installation

```python
import antflow
print(antflow.__version__)
```

## Optional Dependencies

### Development Tools

Install development dependencies for testing and linting:

```bash
pip install -e ".[dev]"
```

This includes:
- pytest and pytest-asyncio for testing
- mypy for type checking
- ruff for linting

### Documentation Tools

Install documentation dependencies to build the docs locally:

```bash
pip install -e ".[docs]"
```

This includes:
- MkDocs and Material theme
- mkdocstrings for API documentation generation
