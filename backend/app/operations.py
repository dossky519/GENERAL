"""The four supported account operations, each expressed as an explicit
sequence of remote shell steps executed over an already-connected
SSHSession. Every step (including read-only checks) is captured as a
CommandResult so the caller can build a full audit log.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Optional

from .ssh_manager import CommandResult, SSHSession
from .validation import ValidationError, validate_name, validate_names, validate_path

q = shlex.quote


@dataclass
class OperationOutcome:
    action: str
    target: dict
    steps: list[CommandResult] = field(default_factory=list)
    success: bool = False
    message: str = ""


def _exists(result: CommandResult) -> bool:
    return result.success and result.stdout.strip() == "EXISTS"


# ---------------------------------------------------------------------------
# 1. Account creation
# ---------------------------------------------------------------------------

def create_account(
    session: SSHSession,
    *,
    username: str,
    primary_group: str,
    secondary_groups: list[str],
    home_dir: Optional[str],
    shell: str,
    password: Optional[str],
    comment: Optional[str],
    create_missing_groups: bool,
) -> OperationOutcome:
    username = validate_name(username, "사용자명")
    primary_group = validate_name(primary_group, "1차(Primary) 그룹")
    secondary_groups = validate_names(secondary_groups, "2차(Secondary) 그룹")
    home = validate_path(home_dir or f"/home/{username}", "홈 디렉토리 경로")
    shell = shell or "/bin/bash"

    outcome = OperationOutcome(action="account_create", target={"username": username, "home_dir": home})
    steps = outcome.steps

    r = session.run("사용자 중복 확인", f"id -u {q(username)}", privileged=False)
    steps.append(r)
    if r.success:
        outcome.success = False
        outcome.message = f"이미 존재하는 사용자입니다: {username}"
        return outcome

    r = session.run(
        "홈 디렉토리 사전 존재 검증",
        f"test -d {q(home)} && echo EXISTS || echo NOTEXISTS",
    )
    steps.append(r)
    dir_pre_existed = _exists(r)

    r = session.run("1차 그룹 존재 확인", f"getent group {q(primary_group)}", privileged=False)
    steps.append(r)
    if not r.success:
        if not create_missing_groups:
            outcome.message = f"1차 그룹 '{primary_group}' 이(가) 존재하지 않습니다."
            return outcome
        r = session.run("1차 그룹 생성", f"groupadd {q(primary_group)}")
        steps.append(r)
        if not r.success:
            outcome.message = f"1차 그룹 '{primary_group}' 생성 실패"
            return outcome

    missing_secondary: list[str] = []
    for g in secondary_groups:
        r = session.run(f"2차 그룹 존재 확인 ({g})", f"getent group {q(g)}", privileged=False)
        steps.append(r)
        if not r.success:
            missing_secondary.append(g)

    if missing_secondary:
        if not create_missing_groups:
            outcome.message = f"2차 그룹이 존재하지 않습니다: {', '.join(missing_secondary)}"
            return outcome
        for g in missing_secondary:
            r = session.run(f"2차 그룹 생성 ({g})", f"groupadd {q(g)}")
            steps.append(r)
            if not r.success:
                outcome.message = f"2차 그룹 '{g}' 생성 실패"
                return outcome

    useradd_parts = ["useradd", "-m", "-d", q(home), "-s", q(shell), "-g", q(primary_group)]
    if secondary_groups:
        useradd_parts += ["-G", q(",".join(secondary_groups))]
    if comment:
        useradd_parts += ["-c", q(comment)]
    useradd_parts.append(q(username))

    r = session.run("useradd 계정 생성", " ".join(useradd_parts))
    steps.append(r)
    if not r.success:
        outcome.message = "useradd 실행 실패"
        return outcome

    if dir_pre_existed:
        r = session.run(
            "기존 홈 디렉토리 덮어쓰기(소유권 재설정)",
            f"chown -R {q(username)}:{q(primary_group)} {q(home)}",
        )
        steps.append(r)
        if not r.success:
            outcome.message = "계정은 생성되었으나 기존 디렉토리 소유권 재설정에 실패했습니다."
            return outcome

    if password:
        r = session.run(
            "초기 비밀번호 설정",
            f"printf '%s:%s\\n' {q(username)} {q(password)} | chpasswd",
            display_command=f"printf '%s:%s' {q(username)} '****' | chpasswd",
        )
        steps.append(r)
        if not r.success:
            outcome.message = "계정은 생성되었으나 비밀번호 설정에 실패했습니다."
            return outcome

    r = session.run("생성 결과 확인", f"id {q(username)}", privileged=False)
    steps.append(r)

    outcome.success = True
    overwrite_note = " (기존 디렉토리를 재사용/덮어썼습니다)" if dir_pre_existed else ""
    outcome.message = f"계정 '{username}' 생성 완료{overwrite_note}"
    return outcome


# ---------------------------------------------------------------------------
# 2. Account deletion
# ---------------------------------------------------------------------------

def delete_account(session: SSHSession, *, username: str) -> OperationOutcome:
    username = validate_name(username, "사용자명")
    outcome = OperationOutcome(action="account_delete", target={"username": username})
    steps = outcome.steps

    r = session.run("사용자 존재 확인", f"id -u {q(username)}", privileged=False)
    steps.append(r)
    if not r.success:
        outcome.message = f"존재하지 않는 사용자입니다: {username}"
        return outcome

    r = session.run(
        "홈 디렉토리 경로 조회",
        f"getent passwd {q(username)} | cut -d: -f6",
        privileged=False,
    )
    steps.append(r)
    home_dir = r.stdout.strip() or f"/home/{username}"
    home_dir = home_dir if home_dir.startswith("/") else f"/home/{username}"

    mail_spool = f"/var/spool/mail/{username}"

    # userdel -r can exit non-zero for a non-fatal reason (e.g. mail spool
    # ownership mismatch, group still primary for another user) while still
    # having removed the account itself - so its exit code alone is not a
    # reliable signal. The account-removal check right after it is.
    r = session.run("userdel 계정 삭제 (-r: 홈 디렉토리/메일함 포함)", f"userdel -r {q(username)}")
    steps.append(r)

    r = session.run("계정 삭제 여부 확인", f"id -u {q(username)}", privileged=False)
    steps.append(r)
    if r.success:
        outcome.message = "userdel 실행 후에도 계정이 남아있습니다 (삭제 실패)"
        return outcome

    r = session.run("홈 디렉토리 잔존 확인", f"test -d {q(home_dir)} && echo EXISTS || echo NOTEXISTS")
    steps.append(r)
    if _exists(r):
        r = session.run("홈 디렉토리 강제 삭제(잔여분 정리)", f"rm -rf {q(home_dir)}")
        steps.append(r)
        if not r.success:
            outcome.message = f"계정은 삭제되었으나 홈 디렉토리 '{home_dir}' 삭제에 실패했습니다."
            return outcome

    r = session.run("메일함 잔존 확인 (/var/spool/mail)", f"test -e {q(mail_spool)} && echo EXISTS || echo NOTEXISTS")
    steps.append(r)
    if _exists(r):
        r = session.run("메일함 삭제 (/var/spool/mail)", f"rm -f {q(mail_spool)}")
        steps.append(r)
        if not r.success:
            outcome.message = f"계정/홈 디렉토리는 삭제되었으나 메일함 '{mail_spool}' 삭제에 실패했습니다."
            return outcome

    r_user = session.run("최종 확인: 사용자 삭제 여부", f"id -u {q(username)}", privileged=False)
    steps.append(r_user)
    r_home = session.run("최종 확인: 홈 디렉토리 삭제 여부", f"test -e {q(home_dir)} && echo EXISTS || echo NOTEXISTS")
    steps.append(r_home)
    r_mail = session.run("최종 확인: 메일함 삭제 여부", f"test -e {q(mail_spool)} && echo EXISTS || echo NOTEXISTS")
    steps.append(r_mail)

    outcome.success = (not r_user.success) and (not _exists(r_home)) and (not _exists(r_mail))
    if outcome.success:
        outcome.message = f"계정 '{username}' 및 홈 디렉토리/메일함 삭제 완료"
    else:
        outcome.message = f"계정 '{username}' 삭제 후 잔여 리소스가 남아있습니다. 상세 로그를 확인하세요."
    return outcome


# ---------------------------------------------------------------------------
# 3. Primary group change
# ---------------------------------------------------------------------------

def change_primary_group(
    session: SSHSession,
    *,
    username: str,
    new_group: str,
    create_missing_group: bool,
) -> OperationOutcome:
    username = validate_name(username, "사용자명")
    new_group = validate_name(new_group, "새 1차(Primary) 그룹")
    outcome = OperationOutcome(action="primary_group_change", target={"username": username, "new_group": new_group})
    steps = outcome.steps

    r = session.run("사용자 존재 확인", f"id -u {q(username)}", privileged=False)
    steps.append(r)
    if not r.success:
        outcome.message = f"존재하지 않는 사용자입니다: {username}"
        return outcome

    r = session.run("대상 그룹 존재 확인", f"getent group {q(new_group)}", privileged=False)
    steps.append(r)
    if not r.success:
        if not create_missing_group:
            outcome.message = f"그룹 '{new_group}' 이(가) 존재하지 않습니다."
            return outcome
        r = session.run("대상 그룹 생성", f"groupadd {q(new_group)}")
        steps.append(r)
        if not r.success:
            outcome.message = f"그룹 '{new_group}' 생성 실패"
            return outcome

    r = session.run("1차 그룹 변경 (usermod -g)", f"usermod -g {q(new_group)} {q(username)}")
    steps.append(r)
    if not r.success:
        outcome.message = "usermod 실행 실패"
        return outcome

    r = session.run("변경 결과 확인", f"id {q(username)}", privileged=False)
    steps.append(r)

    outcome.success = r.success and new_group in r.stdout
    outcome.message = (
        f"사용자 '{username}' 의 1차 그룹을 '{new_group}' (으)로 변경 완료"
        if outcome.success
        else f"1차 그룹 변경 명령은 성공했지만 결과 확인에 실패했습니다: {r.stdout}"
    )
    return outcome


# ---------------------------------------------------------------------------
# 4. Secondary group change
# ---------------------------------------------------------------------------

def change_secondary_groups(
    session: SSHSession,
    *,
    username: str,
    groups: list[str],
    mode: str,  # "replace" | "append"
    create_missing_groups: bool,
) -> OperationOutcome:
    username = validate_name(username, "사용자명")
    groups = validate_names(groups, "2차(Secondary) 그룹")
    if mode not in ("replace", "append"):
        raise ValidationError("mode 는 replace 또는 append 여야 합니다.")
    if mode == "append" and not groups:
        raise ValidationError("append 모드에서는 최소 1개 이상의 그룹이 필요합니다.")

    outcome = OperationOutcome(
        action="secondary_group_change",
        target={"username": username, "groups": groups, "mode": mode},
    )
    steps = outcome.steps

    r = session.run("사용자 존재 확인", f"id -u {q(username)}", privileged=False)
    steps.append(r)
    if not r.success:
        outcome.message = f"존재하지 않는 사용자입니다: {username}"
        return outcome

    missing: list[str] = []
    for g in groups:
        r = session.run(f"2차 그룹 존재 확인 ({g})", f"getent group {q(g)}", privileged=False)
        steps.append(r)
        if not r.success:
            missing.append(g)

    if missing:
        if not create_missing_groups:
            outcome.message = f"2차 그룹이 존재하지 않습니다: {', '.join(missing)}"
            return outcome
        for g in missing:
            r = session.run(f"2차 그룹 생성 ({g})", f"groupadd {q(g)}")
            steps.append(r)
            if not r.success:
                outcome.message = f"2차 그룹 '{g}' 생성 실패"
                return outcome

    flag = "-aG" if mode == "append" else "-G"
    group_arg = ",".join(groups)  # empty string is valid for -G: clears all secondary groups
    step_label = "2차 그룹 추가 (usermod -aG)" if mode == "append" else "2차 그룹 전체 교체 (usermod -G)"
    r = session.run(step_label, f"usermod {flag} {q(group_arg)} {q(username)}")
    steps.append(r)
    if not r.success:
        outcome.message = "usermod 실행 실패"
        return outcome

    r = session.run("변경 결과 확인 (id -nG)", f"id -nG {q(username)}", privileged=False)
    steps.append(r)

    outcome.success = True
    outcome.message = f"사용자 '{username}' 의 2차 그룹을 {'추가' if mode == 'append' else '교체'} 완료: {r.stdout}"
    return outcome
