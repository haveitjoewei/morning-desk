from connectors.base import RawEvent


def fetch_va_messages():
    return [
        RawEvent(
            source="va",
            title="Waiting on pest quote approval",
            body="VA flagged as blocking, needs your decision",
            metadata={"suggested_action": "Approve or decline quote"},
        )
    ]
