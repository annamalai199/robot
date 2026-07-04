"""Event bus and schemas for robot assistant communication."""

from robot_assistant.events.bus import (
    subscribe,
    unsubscribe,
    publish,
    clear_subscribers,
    get_subscriber_count,
    get_event_types,
    set_debug_logging,
)

from robot_assistant.events.schemas import (
    GestureDetectedEvent,
    IdentityResolvedEvent,
    TrackLostEvent,
    SessionStateEvent,
    ActionEvent,
    ActionBlockedEvent,
    ServoCommandEvent,
    TextInputEvent,
    ResponseEvent,
    Event,
    validate_event,
)

__all__ = [
    # Bus functions
    "subscribe",
    "unsubscribe",
    "publish",
    "clear_subscribers",
    "get_subscriber_count",
    "get_event_types",
    "set_debug_logging",
    # Event types
    "GestureDetectedEvent",
    "IdentityResolvedEvent",
    "TrackLostEvent",
    "SessionStateEvent",
    "ActionEvent",
    "ActionBlockedEvent",
    "ServoCommandEvent",
    "TextInputEvent",
    "ResponseEvent",
    "Event",
    "validate_event",
]
