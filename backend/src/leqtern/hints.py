"""
Hints for an exercise: the answering model can show them as a deck of cards, from a nudge to
nearly the solution, which the reader turns over one at a time.
"""

from typing import Any

from pydantic import BaseModel, Field

HINTS_TOOL: dict[str, Any] = {
    "name": "show_hints",
    "description": (
        "Show hints for an exercise as cards they turn over one at a time, each more helpful "
        "than the last: from a nudge to nearly the solution, never the answer itself. Use it "
        "when they want help with an exercise rather than the solution. You decide how many."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"hints": {"type": "array", "items": {"type": "string"}}},
        "required": ["hints"],
    },
}


class HintsInput(BaseModel):
    hints: list[str] = Field(min_length=1, max_length=10)


class Hints(BaseModel):
    """Hints as the chat keeps them: with how many the reader has turned over."""

    items: list[str]
    revealed: int = 0


def hints_text(hints: Hints) -> str:
    """The hints as the model reads them back in the conversation."""
    lines = [f"[Hints shown as cards; they turned over {hints.revealed} of {len(hints.items)}]"]
    lines += [f"{i}. {hint}" for i, hint in enumerate(hints.items, 1)]
    return "\n".join(lines)


def answer_text(text: str, hints: Hints | None) -> str:
    """An answer's text, followed by any hints it showed."""
    if not hints:
        return text
    return f"{text.strip()}\n\n{hints_text(hints)}".strip()
