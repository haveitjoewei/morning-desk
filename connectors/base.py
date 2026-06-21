from dataclasses import dataclass


@dataclass
class RawEvent:
    source: str
    title: str
    body: str
    metadata: dict


class Connector:
    source = "unknown"

    def fetch(self):
        raise NotImplementedError
