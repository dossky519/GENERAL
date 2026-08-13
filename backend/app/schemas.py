from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConnectionInfo(BaseModel):
    host: str
    port: int = 22
    ssh_username: str = Field(..., description="SSH 로그인 계정 (root 또는 passwordless sudo 계정)")
    auth_method: Literal["password", "private_key"]
    password: Optional[str] = None
    private_key: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    operator: Optional[str] = Field(None, description="작업자 식별용 메모 (로그 기록용, 선택)")


class CreateAccountRequest(BaseModel):
    connection: ConnectionInfo
    username: str
    primary_group: str
    secondary_groups: list[str] = []
    home_dir: Optional[str] = None
    shell: str = "/bin/bash"
    password: Optional[str] = None
    comment: Optional[str] = None
    create_missing_groups: bool = False


class DeleteAccountRequest(BaseModel):
    connection: ConnectionInfo
    username: str


class PrimaryGroupChangeRequest(BaseModel):
    connection: ConnectionInfo
    username: str
    new_group: str
    create_missing_group: bool = False


class SecondaryGroupChangeRequest(BaseModel):
    connection: ConnectionInfo
    username: str
    groups: list[str] = []
    mode: Literal["replace", "append"] = "replace"
    create_missing_groups: bool = False


class ConnectionTestRequest(BaseModel):
    connection: ConnectionInfo
