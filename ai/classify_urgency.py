def classify_urgency(event):
    text = f"{event.title} {event.body}".lower()
    if "blocking" in text or "approval" in text:
        return "urgent"
    if "awaiting reply" in text or "asked" in text:
        return "today"
    return "low"
