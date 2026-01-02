import logging
import sys

import pytest

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

if __name__ == "__main__":
    # Run all tests in the tests/ directory
    sys.exit(pytest.main(["tests", "-v"]))
