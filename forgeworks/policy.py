from __future__ import annotations

import hashlib
import re

TRANSITIONS: dict[str, frozenset] = {
    "PROPOSED": frozenset({"VALIDATED", "REJECTED"}),
    "VALIDATED": frozenset({"AWAITING_APPROVAL"}),
    "AWAITING_APPROVAL": frozenset({"APPROVED", "REJECTED", "EXPIRED"}),
    "APPROVED": frozenset({"EXECUTING", "EXPIRED"}),
    "EXECUTING": frozenset({"COMPLETED", "FAILED"}),
    "FAILED": frozenset({"COMPENSATING"}),
    "COMPENSATING": frozenset({"CLOSED"}),
    "COMPLETED": frozenset({"CLOSED"}),
    "REJECTED": frozenset({"CLOSED"}),
    "EXPIRED": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}

DEMO_TARGETS = frozenset({"VALIDATED", "AWAITING_APPROVAL"})

APPROVAL_POLICY: dict[str, tuple] = {
    "NORMAL": ("sales",),
    "EXPEDITE": ("procurement",),
    "ALTERNATE_PART": ("engineering", "procurement"),
}


class IllegalTransition(ValueError):
    pass


class ExecutionDisabled(PermissionError):
    pass


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def advance(record: dict, target: str) -> dict:
    current = record["state"]
    if not can_transition(current, target):
        raise IllegalTransition(f"{current} -> {target} is not in the workflow")
    if target not in DEMO_TARGETS:
        raise ExecutionDisabled(
            f"{current} -> {target} needs an authenticated approver or an operational adapter; "
            "the educational demo has neither")
    return {**record, "state": target, "history": [*record.get("history", []), target],
            "execution_allowed": False, "executed": False}


def required_approvals(action: str) -> tuple:
    if action not in APPROVAL_POLICY:
        raise ValueError(f"No approval policy for action: {action}")
    return APPROVAL_POLICY[action]


def may_approve(action: str, approver_role: str, approver_id: str, requester_id: str) -> tuple:
    if approver_role not in required_approvals(action):
        return False, f"role '{approver_role}' cannot approve {action}"
    if approver_id == requester_id:
        return False, "requester cannot approve their own request"
    return True, "eligible approver"


def idempotency_key(order_id: str, line_id: int, action: str, source_snapshot: str,
                    model_version: str) -> str:
    canonical = "|".join((order_id, str(line_id), action, source_snapshot, model_version))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class DecisionLedger:

    def __init__(self) -> None:
        self._by_key: dict[str, dict] = {}
        self.attempts = 0

    def propose(self, record: dict) -> tuple:
        self.attempts += 1
        key = record["idempotency_key"]
        if key in self._by_key:
            return self._by_key[key], False
        self._by_key[key] = dict(record)
        return self._by_key[key], True

    def __len__(self) -> int:
        return len(self._by_key)


_NOTICE = re.compile(r"\b(CMP-\d+)\b.*?\bdelay(?:ed)?\s+(?:by\s+)?(\d{1,3})\s+days?\b",
                     re.IGNORECASE | re.DOTALL)


def parse_supplier_notice(text: str) -> dict:
    match = _NOTICE.search(text)
    if not match:
        return {"component_id": None, "delay_days": None, "status": "unparsed"}
    return {"component_id": match.group(1).upper(), "delay_days": int(match.group(2)),
            "status": "unverified"}
