from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.platform.dialogue.application import ConversationTurnCoordinator


def test_same_conversation_waits_until_current_lease_releases() -> None:
    coordinator = ConversationTurnCoordinator()
    conversation_id = uuid4()

    async def scenario() -> None:
        first = await coordinator.acquire(conversation_id)
        waiting = asyncio.create_task(coordinator.acquire(conversation_id))
        await asyncio.sleep(0)

        assert not waiting.done()
        assert coordinator.tracked_conversation_count == 1

        first.release()
        second = await waiting
        second.release()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_different_conversations_can_hold_leases_concurrently() -> None:
    coordinator = ConversationTurnCoordinator()

    async def scenario() -> None:
        first, second = await asyncio.gather(
            coordinator.acquire(uuid4()),
            coordinator.acquire(uuid4()),
        )
        assert coordinator.tracked_conversation_count == 2
        first.release()
        second.release()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_cancelled_waiter_releases_its_registry_reference() -> None:
    coordinator = ConversationTurnCoordinator()
    conversation_id = uuid4()

    async def scenario() -> None:
        first = await coordinator.acquire(conversation_id)
        waiting = asyncio.create_task(coordinator.acquire(conversation_id))
        await asyncio.sleep(0)

        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting

        assert coordinator.tracked_conversation_count == 1
        first.release()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_releasing_a_lease_twice_is_safe() -> None:
    coordinator = ConversationTurnCoordinator()

    async def scenario() -> None:
        lease = await coordinator.acquire(uuid4())
        lease.release()
        lease.release()

    asyncio.run(scenario())

    assert coordinator.tracked_conversation_count == 0


def test_acquire_rejects_non_uuid_conversation_identifier() -> None:
    coordinator = ConversationTurnCoordinator()

    async def scenario() -> None:
        with pytest.raises(ValueError, match="会话标识"):
            await coordinator.acquire("not-a-uuid")  # type: ignore[arg-type]

    asyncio.run(scenario())
