#!/usr/bin/env python3
"""CLI for managing web UI login accounts (independent of the running server).

Usage (run from the backend/ directory, ideally inside the venv):
  python manage_users.py add <username>
  python manage_users.py passwd <username>
  python manage_users.py remove <username>
  python manage_users.py list
"""
import argparse
import getpass
import sys

from app import auth

MIN_PASSWORD_LEN = 8


def _prompt_password(label: str) -> str:
    password = getpass.getpass(f"{label}: ")
    confirm = getpass.getpass(f"{label} 확인: ")
    if password != confirm:
        print("비밀번호가 일치하지 않습니다.", file=sys.stderr)
        sys.exit(1)
    if len(password) < MIN_PASSWORD_LEN:
        print(f"비밀번호는 {MIN_PASSWORD_LEN}자 이상이어야 합니다.", file=sys.stderr)
        sys.exit(1)
    return password


def cmd_add(args: argparse.Namespace) -> None:
    if args.username in auth.list_users():
        print(f"이미 존재하는 사용자입니다: {args.username}", file=sys.stderr)
        sys.exit(1)
    password = _prompt_password("비밀번호")
    auth.add_user(args.username, password)
    print(f"사용자 '{args.username}' 추가 완료")


def cmd_passwd(args: argparse.Namespace) -> None:
    if args.username not in auth.list_users():
        print(f"존재하지 않는 사용자입니다: {args.username}", file=sys.stderr)
        sys.exit(1)
    password = _prompt_password("새 비밀번호")
    auth.add_user(args.username, password)
    print(f"사용자 '{args.username}' 비밀번호 변경 완료")


def cmd_remove(args: argparse.Namespace) -> None:
    if auth.remove_user(args.username):
        print(f"사용자 '{args.username}' 삭제 완료")
    else:
        print(f"존재하지 않는 사용자입니다: {args.username}", file=sys.stderr)
        sys.exit(1)


def cmd_list(_args: argparse.Namespace) -> None:
    users = auth.list_users()
    if not users:
        print("등록된 사용자가 없습니다.")
        return
    for u in users:
        print(u)


def main() -> None:
    parser = argparse.ArgumentParser(description="웹 UI 로그인 계정 관리")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="사용자 추가")
    p_add.add_argument("username")
    p_add.set_defaults(func=cmd_add)

    p_passwd = sub.add_parser("passwd", help="비밀번호 변경")
    p_passwd.add_argument("username")
    p_passwd.set_defaults(func=cmd_passwd)

    p_remove = sub.add_parser("remove", help="사용자 삭제")
    p_remove.add_argument("username")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="사용자 목록 조회")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
