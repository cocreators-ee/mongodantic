from typing import Optional, Sequence

from mongodantic import ASCENDING, IndexModel, Model


class User(Model):
    indexes: Sequence[IndexModel] = [
        IndexModel([("first_name", ASCENDING), ("last_name", ASCENDING)]),
        IndexModel([("external_uuid", ASCENDING)], unique=True),
        IndexModel([("last_login", ASCENDING)], expireAfterSeconds=5),
    ]

    external_uuid: str
    first_name: str
    last_name: str
    last_login: int
    new_prop: Optional[str]

    async def after_load(self):
        if not self.new_prop:
            self.new_prop = "new"


async def test_user_model():
    u1 = User(
        external_uuid="abc-123",
        first_name="Test",
        last_name="Testerson",
        last_login=123,
    )
    await u1.save()

    u2 = await User.get_by_id(u1.id)
    assert u2.external_uuid == u1.external_uuid
    assert u2.new_prop == "new"

    assert len(await User.find({"first_name": "Test"})) == 1

    u2.first_name = "Another"
    u2.new_prop = "old"

    await u2.save()
    await u1.reload()

    assert u1.first_name == "Another"
    assert u1.new_prop == "old"

    await u1.delete()

    assert len(await User.find({})) == 0


async def test_pagination():
    for u in range(0, 100):
        user = User(
            external_uuid=f"user-{u}",
            first_name=f"First {u+1}",
            last_name=f"Last {u+1}",
            last_login=u,
        )
        await user.save()

    assert await User.count() == 100
    assert await User.count({"external_uuid": "user-4"}) == 1

    users = await User.find({"last_login": {"$gte": 10}}, skip=10, limit=10)

    idx = 20
    for u in users:
        assert u.external_uuid == f"user-{idx}"
        idx += 1
