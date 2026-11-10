from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_world_dir() -> Path:
    return FIXTURES / "mini-world"
