from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import threading
import uuid
from typing import Any, Iterable


# PARTPILOT:AUTHENTICATED_LIVE_SYNC_BROKER:V687
LIVE_SYNC_TOPICS = (
    "inventory",
    "catalogues",
    "projects",
    "reservations",
    "history",
    "preferences",
    "account",
    "integrations.api_keys",
    "integrations.mcp",
    "backups",
)
LIVE_SYNC_TOPIC_SET = frozenset(LIVE_SYNC_TOPICS)
DEFAULT_REPLAY_LIMIT = 256
DEFAULT_SUBSCRIBER_QUEUE_LIMIT = 128


@dataclass(frozen=True)
class LiveInvalidationEvent:
    generation: str
    sequence: int
    topics: tuple[str, ...]
    resource: dict[str, int | str] | None

    @property
    def event_id(self) -> str:
        return f"{self.generation}:{self.sequence}"

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topics": list(self.topics),
        }
        if self.resource is not None:
            payload["resource"] = dict(self.resource)
        return payload


@dataclass(frozen=True)
class LiveSyncDelivery:
    event_type: str
    event_id: str
    data: dict[str, Any]


@dataclass
class _Subscription:
    token: str
    pending: deque[LiveInvalidationEvent]
    overflowed: bool = False


class LiveSyncBroker:
    def __init__(
        self,
        *,
        generation: str | None = None,
        replay_limit: int = DEFAULT_REPLAY_LIMIT,
        subscriber_queue_limit: int = DEFAULT_SUBSCRIBER_QUEUE_LIMIT,
    ) -> None:
        if replay_limit < 1:
            raise ValueError("Live-sync replay limit must be positive")
        if subscriber_queue_limit < 1:
            raise ValueError(
                "Live-sync subscriber queue limit must be positive"
            )
        normalized_generation = (
            generation.strip() if generation is not None else uuid.uuid4().hex
        )
        if (
            not normalized_generation
            or ":" in normalized_generation
            or "\n" in normalized_generation
            or "\r" in normalized_generation
        ):
            raise ValueError("Live-sync generation is invalid")

        self._generation = normalized_generation
        self._replay_limit = replay_limit
        self._subscriber_queue_limit = subscriber_queue_limit
        self._lock = threading.RLock()
        self._sequence = 0
        self._revisions = {
            topic: 0
            for topic in LIVE_SYNC_TOPICS
        }
        self._replay: deque[LiveInvalidationEvent] = deque(
            maxlen=replay_limit
        )
        self._subscriptions: dict[str, _Subscription] = {}

    @property
    def generation(self) -> str:
        return self._generation

    def _state_locked(self) -> dict[str, Any]:
        return {
            "generation": self._generation,
            "sequence": self._sequence,
            "revisions": dict(self._revisions),
        }

    def state(self) -> dict[str, Any]:
        with self._lock:
            return self._state_locked()

    def _normalize_topics(
        self,
        topics: Iterable[str],
    ) -> tuple[str, ...]:
        requested: set[str] = set()
        for topic in topics:
            normalized = topic.strip()
            if not normalized:
                raise ValueError("Live-sync topic cannot be empty")
            requested.add(normalized)

        if not requested:
            raise ValueError("At least one live-sync topic is required")

        unknown = requested - LIVE_SYNC_TOPIC_SET
        if unknown:
            raise ValueError(
                "Unknown live-sync topics: "
                + ", ".join(sorted(unknown))
            )

        return tuple(
            topic
            for topic in LIVE_SYNC_TOPICS
            if topic in requested
        )

    def _normalize_resource(
        self,
        resource: dict[str, object] | None,
    ) -> dict[str, int | str] | None:
        if resource is None:
            return None

        extra = set(resource) - {"type", "id"}
        if extra:
            raise ValueError(
                "Live-sync resource hints only allow type and id"
            )

        resource_type = resource.get("type")
        resource_id = resource.get("id")
        if not isinstance(resource_type, str):
            raise ValueError("Live-sync resource type must be text")
        resource_type = resource_type.strip()
        if not resource_type or len(resource_type) > 64:
            raise ValueError("Live-sync resource type is invalid")

        if isinstance(resource_id, bool):
            raise ValueError("Live-sync resource id cannot be boolean")
        if isinstance(resource_id, int):
            normalized_id: int | str = resource_id
        elif isinstance(resource_id, str):
            normalized_text = resource_id.strip()
            if not normalized_text or len(normalized_text) > 128:
                raise ValueError("Live-sync resource id is invalid")
            normalized_id = normalized_text
        else:
            raise ValueError(
                "Live-sync resource id must be integer or text"
            )

        return {
            "type": resource_type,
            "id": normalized_id,
        }

    def _delivery_for_event(
        self,
        event: LiveInvalidationEvent,
    ) -> LiveSyncDelivery:
        return LiveSyncDelivery(
            event_type="invalidate",
            event_id=event.event_id,
            data=event.payload(),
        )

    def _ready_locked(self) -> LiveSyncDelivery:
        return LiveSyncDelivery(
            event_type="ready",
            event_id=f"{self._generation}:{self._sequence}",
            data=self._state_locked(),
        )

    def _resync_locked(self, reason: str) -> LiveSyncDelivery:
        data = self._state_locked()
        data["reason"] = reason
        return LiveSyncDelivery(
            event_type="resync",
            event_id=f"{self._generation}:{self._sequence}",
            data=data,
        )

    def publish(
        self,
        topics: Iterable[str],
        *,
        resource: dict[str, object] | None = None,
    ) -> LiveInvalidationEvent:
        normalized_topics = self._normalize_topics(topics)
        normalized_resource = self._normalize_resource(resource)

        with self._lock:
            self._sequence += 1
            for topic in normalized_topics:
                self._revisions[topic] += 1

            event = LiveInvalidationEvent(
                generation=self._generation,
                sequence=self._sequence,
                topics=normalized_topics,
                resource=normalized_resource,
            )
            self._replay.append(event)

            for subscription in self._subscriptions.values():
                if subscription.overflowed:
                    continue
                if (
                    len(subscription.pending)
                    >= self._subscriber_queue_limit
                ):
                    subscription.pending.clear()
                    subscription.overflowed = True
                    continue
                subscription.pending.append(event)

            return event

    def _parse_event_id(
        self,
        event_id: str,
    ) -> tuple[str, int] | None:
        generation, separator, sequence_text = event_id.rpartition(":")
        if (
            not separator
            or not generation
            or not sequence_text.isdigit()
        ):
            return None
        return generation, int(sequence_text)

    def _initial_deliveries_locked(
        self,
        last_event_id: str | None,
    ) -> list[LiveSyncDelivery]:
        if last_event_id is None:
            return [self._ready_locked()]

        parsed = self._parse_event_id(last_event_id.strip())
        if parsed is None:
            return [self._resync_locked("invalid_last_event_id")]

        generation, last_sequence = parsed
        if generation != self._generation:
            return [self._resync_locked("generation_changed")]
        if last_sequence > self._sequence:
            return [self._resync_locked("sequence_ahead")]

        if last_sequence < self._sequence:
            if not self._replay:
                return [self._resync_locked("replay_unavailable")]
            earliest = self._replay[0].sequence
            if last_sequence < earliest - 1:
                return [self._resync_locked("replay_window_exceeded")]

        deliveries = [
            self._delivery_for_event(event)
            for event in self._replay
            if event.sequence > last_sequence
        ]
        deliveries.append(self._ready_locked())
        return deliveries

    def subscribe(
        self,
        last_event_id: str | None = None,
    ) -> tuple[str, tuple[LiveSyncDelivery, ...]]:
        with self._lock:
            token = uuid.uuid4().hex
            initial = self._initial_deliveries_locked(last_event_id)
            self._subscriptions[token] = _Subscription(
                token=token,
                pending=deque(),
            )
            return token, tuple(initial)

    def poll(
        self,
        subscription_token: str,
    ) -> LiveSyncDelivery | None:
        with self._lock:
            subscription = self._subscriptions.get(
                subscription_token
            )
            if subscription is None:
                return None

            if subscription.overflowed:
                subscription.overflowed = False
                subscription.pending.clear()
                return self._resync_locked("subscriber_overflow")

            if not subscription.pending:
                return None

            return self._delivery_for_event(
                subscription.pending.popleft()
            )

    def unsubscribe(self, subscription_token: str) -> None:
        with self._lock:
            self._subscriptions.pop(subscription_token, None)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)


def encode_sse_delivery(delivery: LiveSyncDelivery) -> str:
    payload = json.dumps(
        delivery.data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"id: {delivery.event_id}\n"
        f"event: {delivery.event_type}\n"
        f"data: {payload}\n\n"
    )


live_sync_broker = LiveSyncBroker()


def publish_live_invalidation(
    topics: Iterable[str],
    *,
    resource: dict[str, object] | None = None,
) -> LiveInvalidationEvent:
    return live_sync_broker.publish(
        topics,
        resource=resource,
    )
