# Contributing to AntFlow

Thank you for your interest in contributing to AntFlow! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/rodolfonobrega/AntFlow.git
cd AntFlow
```

2. Install in development mode with dev dependencies:
```bash
pip install -e ".[dev]"
```

## Development Workflow

### Running Tests

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_executor.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=antflow --cov-report=html
```

### Code Quality

#### Linting

We use `ruff` for linting:
```bash
ruff check antflow/
```

Auto-fix issues:
```bash
ruff check --fix antflow/
```

#### Type Checking

We use `mypy` for type checking:
```bash
mypy antflow/
```

#### Formatting

Format code with ruff:
```bash
ruff format antflow/
```

### Running Examples

Test examples to ensure they work:
```bash
python examples/basic_executor.py
python examples/basic_pipeline.py
python examples/advanced_pipeline.py
python examples/real_world_example.py
```

## Code Style Guidelines

### General Principles

- Write clear, readable code
- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write descriptive docstrings
- Keep functions focused and single-purpose

### Docstring Format

Use Google-style docstrings:

```python
async def my_function(x: int, y: str = "default") -> bool:
    """
    Brief description of what the function does.

    Args:
        x: Description of x parameter
        y: Description of y parameter with default

    Returns:
        Description of return value

    Raises:
        ValueError: Description of when this is raised
    """
    pass
```

### Type Hints

Always use type hints:

```python
from typing import Any, Dict, List, Optional

async def process_items(
    items: List[Dict[str, Any]],
    timeout: Optional[float] = None
) -> List[Any]:
    pass
```

### Import Organization

Organize imports in this order:
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
import asyncio
import logging
from typing import Any, List

from tenacity import retry

from antflow.exceptions import AntFlowError
from antflow.types import TaskFunc
```

## Testing Guidelines

### Writing Tests

- Use `pytest` for all tests
- Mark async tests with `@pytest.mark.asyncio`
- Write descriptive test names
- Test both success and failure cases
- Include docstrings in test functions

Example:

```python
import pytest
from antflow import AsyncExecutor

@pytest.mark.asyncio
async def test_executor_handles_task_failure():
    """Test that executor properly handles and propagates task failures."""
    async def failing_task(x):
        raise ValueError("Task failed")

    async with AsyncExecutor(max_workers=2) as executor:
        future = executor.submit(failing_task, 1)

        with pytest.raises(ValueError, match="Task failed"):
            await future.result()
```

### Test Coverage

- Aim for >90% code coverage
- Test edge cases and error conditions
- Include integration tests for complex workflows

## Pull Request Process

### Before Submitting

1. Run all tests: `pytest tests/ -v`
2. Run linting: `ruff check antflow/`
3. Run type checking: `mypy antflow/`
4. Ensure examples still work
5. Update documentation if needed
6. Add tests for new features

### PR Guidelines

1. **Title**: Use a clear, descriptive title
   - Good: "Add support for async iterables in Pipeline.feed_async()"
   - Bad: "Fix bug"

2. **Description**: Include:
   - What changes were made
   - Why the changes were necessary
   - How to test the changes
   - Any breaking changes

3. **Commits**:
   - Write clear commit messages
   - Keep commits focused and atomic
   - Reference issues when applicable

4. **Code Review**:
   - Be responsive to feedback
   - Make requested changes promptly
   - Ask questions if feedback is unclear

## Adding New Features

### Feature Request Process

1. Open an issue describing the feature
2. Discuss the design and approach
3. Wait for approval before implementing
4. Follow the implementation guidelines below

### Implementation Guidelines

1. **Start with types**: Define new types/protocols in `types.py`
2. **Add exceptions**: Define specific exceptions in `exceptions.py`
3. **Implement core logic**: Add main implementation
4. **Write tests**: Comprehensive test coverage
5. **Add documentation**: Update relevant docs
6. **Add examples**: Create example demonstrating the feature
7. **Update API reference**: Document all public APIs

### Backward Compatibility

- Maintain backward compatibility when possible
- Deprecate features before removing them
- Document breaking changes clearly
- Provide migration guides for major changes

## Documentation

### Types of Documentation

1. **API Documentation**: `docs/api_reference.md`
2. **User Guides**: `docs/executor.md`, `docs/pipeline.md`
3. **Examples**: `examples/` directory
4. **README**: High-level overview and quick start

### Documentation Standards

- Use clear, concise language
- Include code examples
- Show both simple and advanced usage
- Keep documentation in sync with code

## Reporting Issues

### Bug Reports

Include:
- Python version
- AntFlow version
- Minimal reproducible example
- Expected behavior
- Actual behavior
- Stack trace if applicable

### Feature Requests

Include:
- Clear description of the feature
- Use cases and motivation
- Proposed API (if applicable)
- Examples of how it would be used

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on what is best for the community

### Communication

- Use GitHub Issues for bugs and features
- Use GitHub Discussions for questions
- Be patient and helpful with others

## Release Process

(For maintainers)

1. Update version in `_version.py`
2. Update CHANGELOG.md
3. Run full test suite
4. Build and test package locally
5. Create git tag
6. Push to PyPI
7. Create GitHub release

## Questions?

If you have questions about contributing, feel free to:
- Open an issue
- Start a discussion on GitHub
- Reach out to maintainers

Thank you for contributing to AntFlow! 🚀
