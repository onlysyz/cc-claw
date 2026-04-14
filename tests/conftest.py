"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Pre-import PIL.Image so @patch('PIL.Image') works in tests
try:
    from PIL import Image  # noqa: F401
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
