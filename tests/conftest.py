from tests import _config
import pytest
from dataclasses import dataclass
import typing as t

def pytest_configure(config:pytest.Config):
    _config.verbose = t.cast(int, config.getoption("verbose")) or 0
