# Installation

## Requirements

- Python 3.9+
- pip

## Install from PyPI

```bash
pip install AntFlow
```

## Install from Source

```bash
git clone https://github.com/rodolfonobrega/AntFlow.git
cd AntFlow
pip install -e ".[dev]"
```

## Verify Installation

```python
import antflow
print(antflow.__version__)
```

## Fast Event Loop (Automatic)

AntFlow automatically installs the fastest available event loop on import:

- **Linux / macOS** → [uvloop](https://github.com/MagicStack/uvloop) (included as a dependency)
- **Windows** → [winloop](https://github.com/vizonex/winloop) (included as a dependency)

No configuration needed. Just `import antflow` and the fast loop is active. If for some reason neither package is importable, AntFlow falls back to the standard asyncio loop without error.

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
