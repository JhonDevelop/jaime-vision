"""Firewall de ações espaciais; integração real também deve passar pelo Vigia."""
from __future__ import annotations
from dataclasses import dataclass

REVERSIBLE = frozenset({"select", "open", "move_window", "zoom", "navigate", "draw", "preview"})
SENSITIVE = frozenset({"move_to_trash", "edit_file", "run_command", "install", "publish", "send", "delete_forever"})

@dataclass(frozen=True)
class ProposedAction:
    verb: str
    target_id: str
    actor: str
    confidence: float
    source: str = "gesture"

@dataclass(frozen=True)
class Decision:
    status: str
    reason: str

def evaluate(action: ProposedAction, *, unlocked: bool, owner: bool,
             explicit_voice: bool = False, threshold: float = .85) -> Decision:
    if not unlocked or not owner:
        return Decision("deny", "owner session required")
    if action.confidence < threshold:
        return Decision("deny", "low confidence")
    if action.verb in REVERSIBLE:
        return Decision("allow", "reversible")
    if action.verb in SENSITIVE:
        return Decision("review", "require explicit intent and existing Vigia policy")
    return Decision("deny", "unknown action")
