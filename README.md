# Mongodantic

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/cocreators-ee/mongodantic/publish.yaml)](https://github.com/cocreators-ee/mongodantic/actions/workflows/publish.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Security: bandit](https://img.shields.io/badge/security-bandit-green.svg)](https://github.com/PyCQA/bandit)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/cocreators-ee/mongodantic/blob/master/.pre-commit-config.yaml)
[![PyPI](https://img.shields.io/pypi/v/mongodantic-python)](https://pypi.org/project/mongodantic-python/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mongodantic-python)](https://pypi.org/project/mongodantic-python/)
[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

Python async database models for MongoDB using Pydantic base models. It should work on Python 3.9+, maybe 3.8,
not quite sure.

## Motivation

It's usually a good idea to have a simple layer on your DB that doesn't try to do too much, but takes care of
the basic things like validating your data and mapping database records to class instances, and overall
providing basic database access helpers. [Pydantic](https://docs.pydantic.dev) does a great job at the typing
of models and validating data, and just needs a bit of database logic around it to provide all the
capabilities commonly needed.

There are similar libraries already for other databases that serve as inspiration for this, e.g.
[firedantic](http://github.com/ioxiocom/firedantic) for Firestore, and
[arangodantic](https://github.com/ioxiocom/arangodantic) for ArangoDB.

## Installation

It's a Python library, what do you expect?

```bash
pip install mongodantic-python
# OR
poetry add mongodantic-python
```

## Usage

Small example of how you can use this library (also in [readme_example.py](./readme_example.py)).

```python
import asyncio
from datetime import datetime
from typing import Optional, Sequence

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import Field

# IndexModel and ASCENDING are just passed through from pymongo
from mongodantic import ASCENDING, IndexModel, Model, ModelNotFoundError, set_database

MONGODB_CONNECT_STR = "mongodb://localhost:27017"  # Point to your MongoDB server


class User(Model):
  # Indexes are automatically created when model is accessed
  indexes: Sequence[IndexModel] = [
    IndexModel(
      keys=[
        ("name", ASCENDING),
      ]
    ),
  ]

  # id property is automatically added - stored as _id in MongoDB

  # Pydantic typing + Field usage works great
  created: datetime = Field(default_factory=datetime.now)
  name: Optional[str] = None

  # You can of course add methods
  def greet(self):
    print(f"Hello, {self.name} from {self.created}")

  async def rename(self):
    self.name = f"Another {self.name}"
    await self.save()

  # You can also run code after loading objects from DB
  async def after_load(self) -> None:
    self.greet()


async def main():
  # Configure the DB connection at the start of your application
  print("Connecting to DB")
  client = AsyncIOMotorClient(MONGODB_CONNECT_STR)
  db = client["my_test_db"]
  set_database(db)

  # You can use this for cleanup
  # for user in await User.find({}):
  #     await user.delete()

  # And just use the models
  print("Creating user")
  user = User()
  await user.save()

  print("Updating user")
  user.name = "Test"
  await user.save()

  print("Renaming user")
  await user.rename()

  # Load up a specific one if you know the str representation of its id
  print("Searching by ID")
  user_again = await User.get_by_id(user.id)
  assert user_again.name == "Another Test"

  # Find many
  # {} is a Pymongo filter, if filtering by id make sure you use "_id" key and ObjectId() for value
  print("Finding all users")
  users = await User.find({})
  assert len(users) == 1

  # Counting
  for idx in range(0, 9):
    u = User(name=f"user-{idx + 1}")
    await u.save()

  # Add a user that sorts to the end
  u = User(name="zuser")
  await u.save()

  assert await User.count() == 11
  assert await User.count({"name": user.name}) == 1

  # Pagination
  users = await User.find({"name": {"$ne": user.name}}, skip=3, limit=3)
  assert len(users) == 3
  for u in users:
    print(u.name)

  # Load up the first matching entry
  print("Finding a user by name")
  test_user = await User.find_one({"name": "Another Test"})
  assert test_user.id == user.id

  # Sorting
  print("Sorting")
  users = await User.find({}, sort="name")
  for u in users:
    print(u.name)

  last_by_name = await User.find_one({}, sort=[("name", pymongo.DESCENDING)])
  print(last_by_name.name)

  print("Deleting users")
  for u in users:
    await u.delete()

  try:
    print("Attempting reload")
    await user.reload()
    raise Exception("User was supposed to be deleted")
  except ModelNotFoundError:
    print("User not found")


if __name__ == "__main__":
  asyncio.run(main())
```

## Development

Issues and PRs are welcome!

Please open an issue first to discuss the idea before sending a PR so that you know if it would be wanted or
needs re-thinking or if you should just make a fork for yourself.

For local development, make sure you install [pre-commit](https://pre-commit.com/#install), then run:

```bash
pre-commit install
poetry install
poetry run ptw .  # Hit Ctrl+C when done with your changes
poetry run python readme_example.py
```

## License

The code is released under the BSD 3-Clause license. Details in the [LICENSE.md](./LICENSE.md) file.

# Financial support

This project has been made possible thanks to [Cocreators](https://cocreators.ee) and
[Lietu](https://lietu.net). You can help us continue our open source work by supporting us on
[Buy me a coffee](https://www.buymeacoffee.com/cocreators).

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/cocreators)
