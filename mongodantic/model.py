from abc import ABC
from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

import bson
import motor.motor_asyncio
import pydantic
from bson import ObjectId
from bson.codec_options import CodecOptions
from pymongo import IndexModel

_DB: motor.motor_asyncio.AsyncIOMotorDatabase
_IS_MONGOMOCK: bool = False
_INIT_MODELS = set()

CODEC_OPTIONS = CodecOptions(tz_aware=True)
TModel = TypeVar("TModel", bound="Model")
SortParam = Sequence[Union[str, Tuple[str, Union[int, str, Mapping[str, Any]]]]]

BSON_TYPES = [
    type(None),
    bool,
    int,
    bson.int64.Int64,
    float,
    str,
    list,
    dict,
    datetime,
    bson.regex.Regex,
    bson.binary.Binary,
    bson.objectid.ObjectId,
    bson.dbref.DBRef,
    bson.code.Code,
    bytes,
]


class ModelNotFoundError(Exception):
    pass


def set_database(
    db: motor.motor_asyncio.AsyncIOMotorDatabase,
    is_mongomock: bool = False,
) -> None:
    global _DB, _IS_MONGOMOCK
    _DB = db
    _IS_MONGOMOCK = is_mongomock


def _get_collection(name: str) -> motor.motor_asyncio.AsyncIOMotorCollection:
    if _IS_MONGOMOCK:
        # mongomock doesn't support codec_options
        return _DB.get_collection(name)
    else:
        return _DB.get_collection(name, codec_options=CODEC_OPTIONS)


async def _init_db(model: Type[TModel], collection_name):
    if _DB is None:
        raise Exception(
            "You need to call set_database before attempting to access the database"
        )

    if collection_name in _INIT_MODELS:
        return

    indexes = model.model_fields["indexes"].default

    collection = _get_collection(collection_name)

    await collection.create_indexes(indexes)

    _INIT_MODELS.add(collection_name)


class Model(pydantic.BaseModel, ABC):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    # https://pymongo.readthedocs.io/en/4.1.1/api/pymongo/operations.html#pymongo.operations.IndexModel
    indexes: Sequence[IndexModel]
    id: Optional[str] = None

    @classmethod
    def get_collection_name(cls) -> str:
        return cls.__name__

    @classmethod
    async def make(cls, **data) -> TModel:
        instance = cls(**data)
        await instance.after_load()
        return instance

    def get_data(self) -> dict:
        data = self.model_dump(by_alias=True)
        del data["id"]
        del data["indexes"]

        def _convert_map(map):
            for key in map:
                item = map[key]
                t = type(item)
                if t not in BSON_TYPES:
                    map[key] = str(item)
                elif t == list:
                    map[key] = _convert_list(item)
                elif t == dict:
                    map[key] = _convert_map(item)
            return map

        def _convert_list(items):
            for idx, item in enumerate(items):
                t = type(item)
                if t not in BSON_TYPES:
                    items[idx] = str(item)
                elif t == list:
                    items[idx] = _convert_list(item)
                elif t == dict:
                    items[idx] = _convert_map(item)
            return items

        data = _convert_map(data)

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
    async def count(cls, filter=None) -> int:
        if not filter:
            filter = {}

        coll = await cls._get_collection()
        return await coll.count_documents(filter)

    @classmethod
    async def find(
        cls,
        filter,
        sort: Optional[SortParam] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[TModel]:
        models = []
        coll = await cls._get_collection()

        cursor = coll.find(filter)
        if sort:
            cursor.sort(sort)
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
    async def find_one(cls, filter, sort: Optional[SortParam] = None) -> TModel:
        coll = await cls._get_collection()
        doc = await coll.find_one(filter, sort=sort)
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

        return _get_collection(name)
