"""SSH connectivity + remote command execution (paramiko).

Supports the two connection methods requested by the platform:
  * "password"    - plain SSH login using a username/password ("명령어 방식")
  * "private_key" - SSH public-key auth, key supplied as pasted text
                     ("SSH Key 방식")

All remote user/group administration commands require root. If the SSH
login account is not `root`, every privileged command is transparently
wrapped in `sudo -n bash -c '...'` so it fails fast (and is logged
clearly) instead of hanging on an interactive password prompt when the
login account does not have passwordless sudo configured.
"""
from __future__ import annotations

import io
import shlex
from dataclasses import dataclass, field
from typing import Optional

import paramiko


class SSHConnectionError(RuntimeError):
    pass


@dataclass
class CommandResult:
    name: str
    command: str  # sanitized/display form only - never contains secrets
    stdout: str
    stderr: str
    exit_code: int
    success: bool


@dataclass
class ConnectionConfig:
    host: str
    port: int
    username: str
    auth_method: str  # "password" | "private_key"
    password: Optional[str] = None
    private_key: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    timeout: float = 15.0


def _load_private_key(key_text: str, passphrase: Optional[str]) -> paramiko.PKey:
    last_error: Optional[Exception] = None
    for key_cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey, paramiko.DSSKey):
        try:
            return key_cls.from_private_key(io.StringIO(key_text), password=passphrase or None)
        except Exception as exc:  # noqa: BLE001 - trying multiple key formats
            last_error = exc
            continue
    raise SSHConnectionError(f"개인키를 파싱할 수 없습니다: {last_error}")


class SSHSession:
    """A single connected SSH client, used to run a sequence of commands."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._client: Optional[paramiko.SSHClient] = None

    def __enter__(self) -> "SSHSession":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = dict(
            hostname=self.config.host,
            port=self.config.port,
            username=self.config.username,
            timeout=self.config.timeout,
            banner_timeout=self.config.timeout,
            auth_timeout=self.config.timeout,
        )
        try:
            if self.config.auth_method == "password":
                if not self.config.password:
                    raise SSHConnectionError("비밀번호가 입력되지 않았습니다.")
                connect_kwargs["password"] = self.config.password
                connect_kwargs["allow_agent"] = False
                connect_kwargs["look_for_keys"] = False
            elif self.config.auth_method == "private_key":
                if not self.config.private_key:
                    raise SSHConnectionError("SSH 개인키가 입력되지 않았습니다.")
                connect_kwargs["pkey"] = _load_private_key(
                    self.config.private_key, self.config.private_key_passphrase
                )
                connect_kwargs["allow_agent"] = False
                connect_kwargs["look_for_keys"] = False
            else:
                raise SSHConnectionError(f"알 수 없는 인증 방식: {self.config.auth_method}")

            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            raise SSHConnectionError(f"SSH 인증 실패: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - surfaced to caller/log as connection failure
            raise SSHConnectionError(f"SSH 연결 실패({self.config.host}:{self.config.port}): {exc}") from exc

        self._client = client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def wrap_privileged(self, cmd: str) -> str:
        if self.config.username == "root":
            return cmd
        return f"sudo -n bash -c {shlex.quote(cmd)}"

    def run(self, name: str, command: str, *, privileged: bool = True, display_command: Optional[str] = None) -> CommandResult:
        """Execute `command` on the remote host.

        `display_command` is what gets stored/shown in logs and the API
        response - pass a secret-free version of the command whenever
        `command` itself embeds a password (e.g. the chpasswd step).
        """
        if self._client is None:
            raise SSHConnectionError("SSH 세션이 연결되어 있지 않습니다.")

        actual_command = self.wrap_privileged(command) if privileged else command
        stdin, stdout, stderr = self._client.exec_command(actual_command, timeout=30)
        stdin.close()
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()

        return CommandResult(
            name=name,
            command=display_command or command,
            stdout=out,
            stderr=err,
            exit_code=exit_code,
            success=(exit_code == 0),
        )
