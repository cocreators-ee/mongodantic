import asyncio
from datetime import datetime
from typing import Optional, Sequence

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
    name: Optional[str]

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
    u2 = await User.get_by_id(user.id)
    assert u2.name == "Another Test"

    # Find many
    # {} is a Pymongo filter, if filtering by id make sure you use "_id" key and ObjectId() for value
    print("Finding all users")
    users = await User.find({})
    assert len(users) == 1

    # Load up the first matching entry
    print("Finding a user by name")
    test_user = await User.find_one({"name": "Another Test"})
    assert test_user.id == user.id

    print("Deleting user")
    await user.delete()

    try:
        print("Attempting reload")
        await user.reload()
        raise Exception("User was supposed to be deleted")
    except ModelNotFoundError:
        print("User not found")


if __name__ == "__main__":
    asyncio.run(main())
