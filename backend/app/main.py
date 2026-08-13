"""Web backend for Ubuntu account administration over SSH.

Exposes 4 operations (account create/delete, primary/secondary group
change) plus a connection test and a log viewer. Every call - success or
failure - is written to logs/actions.log via app.logger.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import operations
from .logger import read_entries, write_entry
from .schemas import (
    ConnectionTestRequest,
    CreateAccountRequest,
    DeleteAccountRequest,
    PrimaryGroupChangeRequest,
    SecondaryGroupChangeRequest,
)
from .ssh_manager import ConnectionConfig, SSHConnectionError, SSHSession
from .validation import ValidationError

app = FastAPI(title="Ubuntu Account Admin over SSH")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def _to_config(conn) -> ConnectionConfig:
    return ConnectionConfig(
        host=conn.host,
        port=conn.port,
        username=conn.ssh_username,
        auth_method=conn.auth_method,
        password=conn.password,
        private_key=conn.private_key,
        private_key_passphrase=conn.private_key_passphrase,
    )


def _outcome_to_log(action: str, conn, target: dict, outcome: operations.OperationOutcome | None, error: str | None) -> dict:
    return {
        "action": action,
        "operator": conn.operator,
        "ssh_host": conn.host,
        "ssh_port": conn.port,
        "ssh_username": conn.ssh_username,
        "auth_method": conn.auth_method,
        "target": target,
        "success": bool(outcome.success) if outcome else False,
        "message": outcome.message if outcome else (error or "알 수 없는 오류"),
        "steps": [dataclasses.asdict(s) for s in outcome.steps] if outcome else [],
    }


def _run_operation(action: str, conn, target: dict, fn):
    try:
        config = _to_config(conn)
        with SSHSession(config) as session:
            outcome = fn(session)
    except (SSHConnectionError, ValidationError) as exc:
        entry = _outcome_to_log(action, conn, target, None, str(exc))
        write_entry(entry)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = _outcome_to_log(action, conn, target, outcome, None)
    write_entry(entry)
    return entry


@app.post("/api/connection/test")
def test_connection(req: ConnectionTestRequest):
    conn = req.connection
    try:
        config = _to_config(conn)
        with SSHSession(config) as session:
            result = session.run("연결 테스트", "whoami && uname -a", privileged=False)
    except SSHConnectionError as exc:
        entry = _outcome_to_log("connection_test", conn, {}, None, str(exc))
        write_entry(entry)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = {
        "action": "connection_test",
        "operator": conn.operator,
        "ssh_host": conn.host,
        "ssh_port": conn.port,
        "ssh_username": conn.ssh_username,
        "auth_method": conn.auth_method,
        "target": {},
        "success": result.success,
        "message": "SSH 연결 성공" if result.success else "SSH 연결은 되었으나 명령 실행 실패",
        "steps": [dataclasses.asdict(result)],
    }
    write_entry(entry)
    return entry


@app.post("/api/account/create")
def create_account(req: CreateAccountRequest):
    return _run_operation(
        "account_create",
        req.connection,
        {"username": req.username},
        lambda session: operations.create_account(
            session,
            username=req.username,
            primary_group=req.primary_group,
            secondary_groups=req.secondary_groups,
            home_dir=req.home_dir,
            shell=req.shell,
            password=req.password,
            comment=req.comment,
            create_missing_groups=req.create_missing_groups,
        ),
    )


@app.post("/api/account/delete")
def delete_account(req: DeleteAccountRequest):
    return _run_operation(
        "account_delete",
        req.connection,
        {"username": req.username},
        lambda session: operations.delete_account(session, username=req.username),
    )


@app.post("/api/group/primary")
def change_primary_group(req: PrimaryGroupChangeRequest):
    return _run_operation(
        "primary_group_change",
        req.connection,
        {"username": req.username, "new_group": req.new_group},
        lambda session: operations.change_primary_group(
            session,
            username=req.username,
            new_group=req.new_group,
            create_missing_group=req.create_missing_group,
        ),
    )


@app.post("/api/group/secondary")
def change_secondary_groups(req: SecondaryGroupChangeRequest):
    return _run_operation(
        "secondary_group_change",
        req.connection,
        {"username": req.username, "groups": req.groups, "mode": req.mode},
        lambda session: operations.change_secondary_groups(
            session,
            username=req.username,
            groups=req.groups,
            mode=req.mode,
            create_missing_groups=req.create_missing_groups,
        ),
    )


@app.get("/api/logs")
def get_logs(limit: int = 100):
    return {"entries": read_entries(limit=limit)}


# --- static frontend -------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
