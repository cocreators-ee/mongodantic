from abc import ABC
from typing import List, Optional, Sequence, Type, TypeVar

import motor.motor_asyncio
import pydantic
from bson import ObjectId
from bson.codec_options import CodecOptions
from pymongo import IndexModel

_DB: motor.motor_asyncio.AsyncIOMotorDatabase
_ENV: str = "unknown"
_INIT_MODELS = set()

CODEC_OPTIONS = CodecOptions(tz_aware=True)
TModel = TypeVar("TModel", bound="Model")


class ModelNotFoundError(Exception):
    pass


def set_database(db: motor.motor_asyncio.AsyncIOMotorDatabase, env: str = "unknown"):
    global _DB, _ENV
    _DB = db
    _ENV = env


async def _init_db(model: Type[TModel], collection_name):
    if _DB is None:
        raise Exception(
            "You need to call set_database before attempting to access the database"
        )

    if collection_name in _INIT_MODELS:
        return

    indexes = model.__fields__["indexes"].default

    if _ENV == "unittest":
        # mongomock doesn't support codec_options
        collection = _DB.get_collection(collection_name)
    else:
        collection = _DB.get_collection(collection_name, codec_options=CODEC_OPTIONS)

    await collection.create_indexes(indexes)

    _INIT_MODELS.add(collection_name)


class Model(pydantic.BaseModel, ABC):
    # https://pymongo.readthedocs.io/en/4.1.1/api/pymongo/operations.html#pymongo.operations.IndexModel
    indexes: Sequence[IndexModel]
    id: Optional[str]

    class Config:
        # IndexModel validation is missing for pydantic so it requires this
        arbitrary_types_allowed = True

    @classmethod
    def get_collection_name(cls) -> str:
        return cls.__name__

    @classmethod
    async def make(cls, **data) -> TModel:
        instance = cls(**data)
        await instance.after_load()
        return instance

    def get_data(self) -> dict:
        data = self.dict(by_alias=True)
        del data["id"]
        del data["indexes"]

        return data

    async def reload(self) -> None:
        coll = await self._get_collection()
        doc = await coll.find_one({"_id": ObjectId(self.id)})
        if not doc:
            raise ModelNotFoundError()

        del doc["_id"]
        item = self.__class__(id=self.id, **doc)
        for key in item.get_data():
            setattr(self, key, getattr(item, key))

        await self.after_load()

    async def after_load(self) -> None:
        pass

    async def save(self) -> None:
        data = self.get_data()
        if not self.id:
            id = ObjectId()
        else:
            id = ObjectId(self.id)

        coll = await self._get_collection()
        result = await coll.replace_one(
            {"_id": id},
            data,
            upsert=True,
        )

        if result.upserted_id:
            self.id = str(result.upserted_id)

    async def delete(self) -> bool:
        if not self.id:
            raise Exception("Can't delete a model without an ID")

        coll = await self._get_collection()
        res = await coll.delete_one({"_id": ObjectId(self.id)})
        return res.deleted_count == 1

    @classmethod
    async def find(
        cls,
        filter,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[TModel]:
        models = []
        coll = await cls._get_collection()

        cursor = coll.find(filter)
        if skip:
            cursor.skip(skip)
        if limit:
            cursor.limit(limit)

        async for doc in cursor:
            id = str(doc["_id"])
            del doc["_id"]
            models.append(await cls.make(id=id, **doc))
        return models

    @classmethod
    async def count(cls, filter=None) -> int:
        if not filter:
            filter = {}

        coll = await cls._get_collection()
        return await coll.count_documents(filter)

    @classmethod
    async def find_one(cls, filter) -> TModel:
        coll = await cls._get_collection()
        doc = await coll.find_one(filter)
        if not doc:
            raise ModelNotFoundError()

        id = str(doc["_id"])
        del doc["_id"]

        return await cls.make(id=id, **doc)

    @classmethod
    async def get_by_id(cls, id: str) -> TModel:
        return await cls.find_one({"_id": ObjectId(id)})

    @classmethod
    async def _get_collection(cls) -> motor.motor_asyncio.AsyncIOMotorCollection:
        name = cls.get_collection_name()
        await _init_db(cls, name)

        if _ENV == "unittest":
            # mongomock doesn't support codec_options
            return _DB.get_collection(name)
        else:
            return _DB.get_collection(name, codec_options=CODEC_OPTIONS)
