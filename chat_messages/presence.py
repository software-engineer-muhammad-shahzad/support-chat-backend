"""Online/offline presence — Redis only, never the database.

A user counts as "online" while at least one of their WebSocket connections
is alive and has heartbeated recently. Nothing here is persisted to
Postgres: it's throwaway, per-connection state that should vanish the
moment Redis is empty or a connection goes quiet, not survive a restart.

Storage: one Redis hash per user, `presence:<user_id>`, mapping each of
their live `channel_name`s to "1". The hash's TTL is refreshed on every
connect/heartbeat, so a connection that drops without a clean disconnect
(laptop closed, network yanked) self-expires within PRESENCE_TTL instead
of leaving someone stuck "online" forever. Using a hash (not a plain key)
means one browser tab closing doesn't mark a user offline while another
tab/conversation is still open.

Every public function is fail-safe: presence is best-effort ephemeral data,
so if Redis is unreachable we log it and act as if everyone's offline,
rather than let a Redis outage break conversations/messages themselves.

Circuit breaker: a *reachable-but-down* Redis (connection refused) fails
fast, but an *unreachable* one (firewalled, wrong host) can take the full
socket timeout to fail — and every conversation/message response checks
Redis once per participant. Under normal polling that's enough blocked
Redis attempts, each paying a full timeout, to genuinely stall the app
(exactly what happened before this existed: real request timeouts on
totally unrelated endpoints). So: one failure trips the breaker, and every
call for the next REDIS_RETRY_SECONDS returns the safe default instantly,
with no connection attempt at all, until it's time to probe again.
"""

import logging
import time

import redis
from django.conf import settings

# A connection must heartbeat within this many seconds or it's presumed
# dead. The frontend pings well under this (see useChatWebSocket).
PRESENCE_TTL = 45

# How long to skip Redis entirely after it fails, before probing again.
REDIS_RETRY_SECONDS = 15

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_down_until = 0.0


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
    return _client


def _circuit_open() -> bool:
    """True while we're deliberately not even trying Redis."""
    return time.monotonic() < _down_until


def _trip_circuit() -> None:
    global _down_until
    _down_until = time.monotonic() + REDIS_RETRY_SECONDS


def _key(user_id) -> str:
    return f"presence:{user_id}"


def touch(user_id, channel_name: str) -> None:
    """Mark one connection alive (used on connect and on every heartbeat)."""
    if _circuit_open():
        return
    try:
        client = get_client()
        key = _key(user_id)
        client.hset(key, channel_name, "1")
        client.expire(key, PRESENCE_TTL)
    except redis.exceptions.RedisError:
        _trip_circuit()
        logger.warning("presence.touch: Redis unavailable, skipping", exc_info=True)


def release(user_id, channel_name: str) -> None:
    """Drop one connection; the user goes offline once none remain."""
    if _circuit_open():
        return
    try:
        client = get_client()
        key = _key(user_id)
        client.hdel(key, channel_name)
        if client.hlen(key) == 0:
            client.delete(key)
    except redis.exceptions.RedisError:
        _trip_circuit()
        logger.warning("presence.release: Redis unavailable, skipping", exc_info=True)


def is_online(user_id) -> bool:
    if _circuit_open():
        return False
    try:
        return get_client().hlen(_key(user_id)) > 0
    except redis.exceptions.RedisError:
        _trip_circuit()
        logger.warning(
            "presence.is_online: Redis unavailable, reporting offline", exc_info=True
        )
        return False


def bulk_online_ids(user_ids) -> set:
    """Which of these user ids currently have at least one live connection."""
    ids = [uid for uid in dict.fromkeys(user_ids) if uid is not None]
    if not ids or _circuit_open():
        return set()
    try:
        client = get_client()
        pipe = client.pipeline()
        for uid in ids:
            pipe.hlen(_key(uid))
        counts = pipe.execute()
        return {uid for uid, count in zip(ids, counts) if count > 0}
    except redis.exceptions.RedisError:
        _trip_circuit()
        logger.warning(
            "presence.bulk_online_ids: Redis unavailable, reporting none online",
            exc_info=True,
        )
        return set()
