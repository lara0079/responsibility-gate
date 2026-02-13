from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid
import json
from datetime import datetime, timezone
from threading import Lock
from pathlib import Path

app = FastAPI(title="Responsibility Gate", version="0.1")

DATABASE = Path("storage.json")
db_lock = Lock()


class RiskLevel(str, Enum):
    low = "low"
    high = "high"


class DecisionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    executed = "executed"
    rejected = "rejected"


class AIDecision(BaseModel):
    action: str = Field(..., min_length=1, description="Proposed action to be executed")
    justification: str = Field(..., min_length=1, description="Why the system proposes this action")
    risk_level: RiskLevel = Field(..., description="low or high")


class AuthorizeRequest(BaseModel):
    authorizer: str = Field(..., min_length=1, description="Human authority assuming responsibility")
    note: Optional[str] = Field(default=None, description="Optional note (why approved)")


class RejectRequest(BaseModel):
    authorizer: str = Field(..., min_length=1, description="Human authority rejecting the action")
    reason: str = Field(..., min_length=1, description="Reason for rejection")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_data() -> dict:
    if not DATABASE.exists():
        return {}
    try:
        return json.loads(DATABASE.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Storage corrupted or unreadable")


def save_data(data: dict) -> None:
    DATABASE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.post("/ai-decision")
def receive_decision(decision: AIDecision):
    """
    AI submits a proposed action + justification + risk.
    High-risk actions become PENDING (blocked until human binding).
    Low-risk actions become APPROVED automatically.
    """
    with db_lock:
        data = load_data()
        decision_id = str(uuid.uuid4())

        status = DecisionStatus.approved if decision.risk_level == RiskLevel.low else DecisionStatus.pending

        data[decision_id] = {
            "decision_id": decision_id,
            "action": decision.action,
            "justification": decision.justification,
            "risk_level": decision.risk_level,
            "status": status,
            "created_at": now_utc_iso(),
            "authorized_by": None,
            "authorized_at": None,
            "authorization_note": None,
            "rejected_by": None,
            "rejected_at": None,
            "rejection_reason": None,
            "executed_at": None,
            "execution_result": None,
        }

        save_data(data)

    return {"decision_id": decision_id, "status": status}


@app.get("/decision/{decision_id}")
def get_decision(decision_id: str):
    with db_lock:
        data = load_data()
        if decision_id not in data:
            raise HTTPException(status_code=404, detail="Not found")
        return data[decision_id]


@app.get("/pending")
def list_pending():
    with db_lock:
        data = load_data()
        return [d for d in data.values() if d["status"] == DecisionStatus.pending]


@app.post("/authorize/{decision_id}")
def authorize_decision(decision_id: str, req: AuthorizeRequest):
    """
    Human authority explicitly assumes responsibility and approves execution.
    """
    with db_lock:
        data = load_data()
        if decision_id not in data:
            raise HTTPException(status_code=404, detail="Not found")

        if data[decision_id]["status"] != DecisionStatus.pending:
            raise HTTPException(status_code=409, detail="Decision is not pending")

        data[decision_id]["status"] = DecisionStatus.approved
        data[decision_id]["authorized_by"] = req.authorizer
        data[decision_id]["authorized_at"] = now_utc_iso()
        data[decision_id]["authorization_note"] = req.note

        save_data(data)

    return {"message": "Decision approved", "decision_id": decision_id}


@app.post("/reject/{decision_id}")
def reject_decision(decision_id: str, req: RejectRequest):
    """
    Human authority rejects the action and records a reason.
    """
    with db_lock:
        data = load_data()
        if decision_id not in data:
            raise HTTPException(status_code=404, detail="Not found")

        if data[decision_id]["status"] not in [DecisionStatus.pending, DecisionStatus.approved]:
            raise HTTPException(status_code=409, detail="Decision cannot be rejected in its current status")

        data[decision_id]["status"] = DecisionStatus.rejected
        data[decision_id]["rejected_by"] = req.authorizer
        data[decision_id]["rejected_at"] = now_utc_iso()
        data[decision_id]["rejection_reason"] = req.reason

        save_data(data)

    return {"message": "Decision rejected", "decision_id": decision_id}


@app.post("/execute/{decision_id}")
def execute_decision(decision_id: str):
    """
    Simulated execution endpoint:
    - If NOT approved -> blocked.
    - If high-risk and not authorized_by -> blocked.
    - If approved -> executes and logs execution.
    """
    with db_lock:
        data = load_data()
        if decision_id not in data:
            raise HTTPException(status_code=404, detail="Not found")

        d = data[decision_id]

        if d["status"] != DecisionStatus.approved:
            raise HTTPException(status_code=403, detail="Execution blocked: not approved")

        if d["risk_level"] == RiskLevel.high and not d["authorized_by"]:
            raise HTTPException(status_code=403, detail="Execution blocked: high-risk requires human authorization")

        d["status"] = DecisionStatus.executed
        d["executed_at"] = now_utc_iso()
        d["execution_result"] = "Executed action: {}".format(d["action"])

        save_data(data)

    return {"message": "Executed", "decision_id": decision_id}
