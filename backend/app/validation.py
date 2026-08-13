"""Input validation for names that get interpolated into remote shell commands.

Even though every value is also passed through `shlex.quote` before being
sent over SSH (so shell-injection is not possible), usernames and group
names are additionally restricted to the character set that `useradd`
itself accepts. This gives fast, clear client-visible errors instead of a
confusing failure from the remote `useradd`/`usermod` binary.
"""
from __future__ import annotations

import re

# Standard Debian/Ubuntu adduser(8) NAME_REGEX (lowercase login names).
_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}\$?$")


class ValidationError(ValueError):
    pass


def validate_name(value: str, field: str) -> str:
    if not value or not _NAME_RE.match(value):
        raise ValidationError(
            f"{field} 값 '{value}' 이(가) 유효하지 않습니다. "
            "소문자로 시작하고 영문 소문자/숫자/-/_ 만 사용할 수 있습니다 (최대 32자)."
        )
    return value


def validate_names(values: list[str], field: str) -> list[str]:
    return [validate_name(v, field) for v in values]


def validate_path(value: str, field: str) -> str:
    if not value or not value.startswith("/") or ".." in value.split("/"):
        raise ValidationError(f"{field} 값 '{value}' 이(가) 유효한 절대 경로가 아닙니다.")
    return value
