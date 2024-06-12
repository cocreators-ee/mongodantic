# ruff: noqa: E402 .. filterwarnings messes with import order

import warnings

warnings.filterwarnings(
    "ignore", message="pkg_resources is deprecated as an API"
)  # fake_useragent

import pytest
from mongomock_motor import AsyncMongoMockClient

from mongodantic.model import set_database


@pytest.fixture(autouse=True)
async def mongo_database():
    client = AsyncMongoMockClient()
    db = client["unittests"]
    set_database(db, True)
    yield db
    await db["User"].delete_many({})
