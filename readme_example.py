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

    # id properly is automatically added - stored as _id in MongoDB

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
