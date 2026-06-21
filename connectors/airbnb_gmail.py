from connectors.base import RawEvent


def fetch_airbnb_messages():
    return [
        RawEvent(
            source="airbnb",
            title="Guest asked about ants",
            body="Guest message awaiting reply",
            metadata={"suggested_action": "Reply or forward to VA"},
        )
    ]
