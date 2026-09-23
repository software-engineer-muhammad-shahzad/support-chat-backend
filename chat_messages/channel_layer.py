from channels_redis.core import RedisChannelLayer


class FastRedisChannelLayer(RedisChannelLayer):
    """`channels_redis`'s default layer, just polling far more often.

    Group messages (used for the live presence push in `consumers.py`) are
    delivered by having each waiting consumer BZPOPMIN a Redis sorted set,
    blocking for up to `brpop_timeout` (channels_redis's default: 5s) if
    nothing's there yet. On a real, unproxied Redis that's fine — Redis
    unblocks the caller the instant something is pushed, so 5s is only ever
    a worst-case ceiling for the genuinely-idle case. Measured against
    Upstash, though, delivery consistently took the *entire* 5s before a
    receiving consumer noticed a new message, suggesting their proxy
    doesn't wake blocked clients early. For a "you should see this
    essentially instantly" presence push, that's too slow — dropping the
    poll window to 1s caps the worst case far lower, at the cost of a bit
    more idle chatter with Redis per open connection.
    """

    brpop_timeout = 1
