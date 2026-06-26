import os
from cryptography.fernet import Fernet

# A valid master key for the whole test session (crypto reads env lazily).
os.environ.setdefault("MASTER_ENCRYPTION_KEY", Fernet.generate_key().decode())

import pytest
from aiportfolio.config import load_base_raw


@pytest.fixture
def base_cfg():
    return load_base_raw()


@pytest.fixture
def account():
    return {"equity": 1000.0, "cash": 1000.0}
