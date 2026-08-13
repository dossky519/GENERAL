"""Web backend for Ubuntu account administration over SSH.

Exposes 4 operations (account create/delete, primary/secondary group
change) plus a connection test and a log viewer, all gated behind a
session-cookie login (see app.auth). Every call - success or failure -
is written to logs/actions.log via app.logger, tagged with the
logged-in operator.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, operations
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

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"


@app.on_event("startup")
def _on_startup() -> None:
    auth.bootstrap_from_env()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_login(request: Request) -> str:
    token = request.cookies.get(auth.COOKIE_NAME)
    username = auth.verify_session_token(token) if token else None
    if not username:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return username


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    throttle_key = f"{client_ip}:{req.username}"
    if auth.is_locked_out(throttle_key):
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.")

    if not auth.authenticate(req.username, req.password):
        auth.record_failed_attempt(throttle_key)
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    auth.clear_attempts(throttle_key)
    token = auth.create_session_token(req.username)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=auth.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )
    return {"ok": True, "username": req.username}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: str = Depends(require_login)):
    return {"username": user}


# ---------------------------------------------------------------------------
# Account operations (all require login)
# ---------------------------------------------------------------------------

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


def _outcome_to_log(
    action: str,
    conn,
    target: dict,
    outcome: operations.OperationOutcome | None,
    error: str | None,
    logged_in_as: str,
) -> dict:
    return {
        "action": action,
        "logged_in_as": logged_in_as,
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


def _run_operation(action: str, conn, target: dict, user: str, fn):
    try:
        config = _to_config(conn)
        with SSHSession(config) as session:
            outcome = fn(session)
    except (SSHConnectionError, ValidationError) as exc:
        entry = _outcome_to_log(action, conn, target, None, str(exc), user)
        write_entry(entry)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = _outcome_to_log(action, conn, target, outcome, None, user)
    write_entry(entry)
    return entry


@app.post("/api/connection/test")
def test_connection(req: ConnectionTestRequest, user: str = Depends(require_login)):
    conn = req.connection
    try:
        config = _to_config(conn)
        with SSHSession(config) as session:
            result = session.run("연결 테스트", "whoami && uname -a", privileged=False)
    except SSHConnectionError as exc:
        entry = _outcome_to_log("connection_test", conn, {}, None, str(exc), user)
        write_entry(entry)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entry = {
        "action": "connection_test",
        "logged_in_as": user,
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
def create_account(req: CreateAccountRequest, user: str = Depends(require_login)):
    return _run_operation(
        "account_create",
        req.connection,
        {"username": req.username},
        user,
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
def delete_account(req: DeleteAccountRequest, user: str = Depends(require_login)):
    return _run_operation(
        "account_delete",
        req.connection,
        {"username": req.username},
        user,
        lambda session: operations.delete_account(session, username=req.username),
    )


@app.post("/api/group/primary")
def change_primary_group(req: PrimaryGroupChangeRequest, user: str = Depends(require_login)):
    return _run_operation(
        "primary_group_change",
        req.connection,
        {"username": req.username, "new_group": req.new_group},
        user,
        lambda session: operations.change_primary_group(
            session,
            username=req.username,
            new_group=req.new_group,
            create_missing_group=req.create_missing_group,
        ),
    )


@app.post("/api/group/secondary")
def change_secondary_groups(req: SecondaryGroupChangeRequest, user: str = Depends(require_login)):
    return _run_operation(
        "secondary_group_change",
        req.connection,
        {"username": req.username, "groups": req.groups, "mode": req.mode},
        user,
        lambda session: operations.change_secondary_groups(
            session,
            username=req.username,
            groups=req.groups,
            mode=req.mode,
            create_missing_groups=req.create_missing_groups,
        ),
    )


@app.get("/api/logs")
def get_logs(limit: int = 100, user: str = Depends(require_login)):
    return {"entries": read_entries(limit=limit)}


# --- static frontend -------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/login")
    def login_page():
        return FileResponse(str(FRONTEND_DIR / "login.html"))

    @app.get("/")
    def index(request: Request):
        token = request.cookies.get(auth.COOKIE_NAME)
        if not (token and auth.verify_session_token(token)):
            return RedirectResponse(url="/login")
        return FileResponse(str(FRONTEND_DIR / "index.html"))
