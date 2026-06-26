import asyncio

from src.memory.redis_manager import RedisManager


class FakeRedisPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.operations = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def hincrby(self, key, field, amount):
        self.operations.append(("hincrby", key, field, amount))

    def hset(self, key, field, value):
        self.operations.append(("hset", key, field, value))

    def expire(self, key, ttl):
        self.operations.append(("expire", key, ttl))

    async def execute(self):
        for operation in self.operations:
            if operation[0] == "hincrby":
                _, key, field, amount = operation
                current = int(self.redis.hashes.setdefault(key, {}).get(field, 0) or 0)
                self.redis.hashes[key][field] = str(current + int(amount))
            elif operation[0] == "hset":
                _, key, field, value = operation
                self.redis.hashes.setdefault(key, {})[field] = str(value)
            elif operation[0] == "expire":
                _, key, ttl = operation
                self.redis.expirations[key] = ttl
        return []


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.expirations = {}

    def pipeline(self, transaction=True):
        return FakeRedisPipeline(self)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))


def test_redis_manager_records_and_reads_shared_webhook_metrics():
    manager = RedisManager()
    manager.enabled = True
    manager.redis = FakeRedis()

    asyncio.run(manager.record_webhook_metric("telegram", "received"))
    asyncio.run(
        manager.record_webhook_metric(
            "telegram",
            "rejected",
            "Invalid Telegram webhook secret",
        )
    )
    metrics = asyncio.run(manager.get_webhook_metrics(("telegram", "slack")))

    assert metrics["telegram"]["received"] == 1
    assert metrics["telegram"]["rejected"] == 1
    assert metrics["telegram"]["last_event_at"] is not None
    assert metrics["telegram"]["last_error"] == "Invalid Telegram webhook secret"
    assert metrics["slack"]["received"] == 0
    assert manager.redis.expirations["webhook_metrics:telegram"] == 604800
