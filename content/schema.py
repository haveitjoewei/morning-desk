from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo


VISIBLE_URGENCY = {"today", "urgent"}


@dataclass
class PriorityItem:
    title: str
    source: str
    urgency: str
    reason: str
    suggested_action: str
    summary: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "source": self.source,
            "urgency": self.urgency,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "summary": self.summary,
        }


@dataclass
class BriefingContent:
    generated_at: str
    date_label: str
    weather: dict
    outfit: dict
    briefing: str
    calendar: list[dict]
    priority_items: list[PriorityItem] = field(default_factory=list)
    journal_prompt: str = ""

    @classmethod
    def from_parts(
        cls,
        *,
        generated_at=None,
        date_label=None,
        weather=None,
        outfit=None,
        briefing="",
        calendar=None,
        priority_items=None,
        journal_prompt="",
    ):
        now = generated_at or datetime.now(ZoneInfo("Australia/Sydney"))
        if isinstance(now, datetime):
            generated_at = now.isoformat(timespec="seconds")
            date_label = date_label or now.strftime("%A, %-d %B")

        return cls(
            generated_at=generated_at,
            date_label=date_label or "",
            weather=weather or {},
            outfit=outfit or {},
            briefing=briefing,
            calendar=calendar or [],
            priority_items=[
                item for item in (priority_items or []) if item.urgency in VISIBLE_URGENCY
            ],
            journal_prompt=journal_prompt,
        )

    def to_dict(self):
        return {
            "generated_at": self.generated_at,
            "date_label": self.date_label,
            "weather": self.weather,
            "outfit": self.outfit,
            "briefing": self.briefing,
            "calendar": self.calendar,
            "priority_items": [item.to_dict() for item in self.priority_items],
            "journal_prompt": self.journal_prompt,
        }
