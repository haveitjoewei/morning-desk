import json
from pathlib import Path


def load_wardrobe(path=None):
    path = Path(path) if path else Path(__file__).with_name("items.json")
    return json.loads(path.read_text())
