# Ubuntu 계정 관리 콘솔 (SSH)

Ubuntu 서버의 계정을 SSH로 원격 관리하는 웹 도구입니다. 웹 UI에 로그인한 뒤
대상 서버의 SSH 접속 정보(비밀번호 또는 SSH Key, 포트는 22 또는 임의 지정값)를
입력하면, 백엔드가 해당 서버에 SSH로 접속해 `useradd` / `userdel` / `usermod` /
`groupadd` 등을 실행합니다.

## 지원 기능

1. **계정 생성** — `useradd`. 홈 디렉토리가 이미 존재하는지 먼저 검증(`test -d`)한 뒤,
   존재하면 기존 디렉토리를 재사용하고 소유권을 재설정합니다(덮어쓰기).
2. **계정 삭제** — `userdel -r` 실행 후 계정/홈 디렉토리/`/var/spool/mail/<user>`
   메일함이 실제로 삭제되었는지 각각 재확인하고, 남아있으면 추가로 강제 삭제합니다.
3. **Primary 그룹 변경** — `usermod -g`.
4. **Secondary 그룹 변경** — `usermod -G`(전체 교체) 또는 `usermod -aG`(추가).

모든 작업은 검증 → 실행 → 결과 확인의 단계별 명령으로 쪼개어 실행되며, 각 단계의
명령어/표준출력/표준에러/종료코드/성공여부가 전부 기록됩니다. 성공/실패와 무관하게
모든 시도가 `backend/logs/actions.log` (JSON Lines)에 남고, 웹 UI 하단 "실행 로그"
에서 조회할 수 있습니다. 각 로그에는 웹 UI에 로그인한 작업자 계정(`logged_in_as`)도
함께 기록됩니다.

## 웹 UI 로그인 인증

- 세션 쿠키 기반 로그인입니다(`HttpOnly`, `SameSite=Lax`). 비밀번호는
  PBKDF2-HMAC-SHA256으로 해시하여 `backend/data/users.json`에 저장하며,
  평문 비밀번호는 어디에도 저장되지 않습니다.
- 공개 회원가입 기능은 없습니다 — 계정은 서버에서 `manage_users.py` CLI로만
  추가/삭제/비밀번호 변경합니다(아래 "최초 실행" 참고).
- 동일 IP+아이디 조합으로 5분 내 5회 로그인 실패 시 5분간 잠깁니다(무차별
  대입 방지).
- 세션 서명 키(`SECRET_KEY`)는 환경변수로 지정하지 않으면 `backend/data/secret_key`
  파일에 자동 생성되어 재시작해도 세션이 유지됩니다.

## 최초 실행 — 내부망에서 직접 확인하는 방법

아래는 내부망(사내망/VPN)에 있는 Ubuntu 서버 한 대에 이 콘솔을 설치해 실행하고,
같은 네트워크의 브라우저로 접속해 확인하는 전체 절차입니다.

### 1) 콘솔을 실행할 서버 준비

콘솔 자체는 어떤 Ubuntu(또는 Python 3.10+가 되는) 서버에서 실행해도 되고,
계정을 관리하려는 대상 서버와 같은 서버일 필요는 없습니다. 다만 콘솔 서버는
관리 대상 Ubuntu 서버들의 SSH(기본 22번, 또는 각 서버에서 사용 중인 포트)에
네트워크로 접근할 수 있어야 합니다.

```bash
git clone <이 저장소 URL>
cd ubuntu-/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 첫 관리자 계정 만들기

방법 A — CLI로 직접 추가(권장):

```bash
python manage_users.py add admin
# 비밀번호 입력(8자 이상), 확인 입력
```

방법 B — 최초 기동 시 환경변수로 자동 생성:

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD='최초비밀번호'
```

`backend/data/users.json`이 아직 없을 때만 자동 생성되므로, 이후에는
`ADMIN_PASSWORD`를 계속 노출해둘 필요가 없습니다(생성 후 unset 하세요).

### 3) 서버 기동

```bash
# (필요시) 세션 서명 키를 직접 고정하고 싶다면:
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

python run.py
# 기본: HOST=0.0.0.0 PORT=8000
```

`0.0.0.0`으로 바인딩되므로 같은 내부망의 다른 PC에서도 접근 가능합니다.
포트를 바꾸려면 `PORT=8080 python run.py` 처럼 환경변수를 지정하세요.

방화벽(ufw)을 쓰는 경우 내부망 대역만 허용하는 것을 권장합니다:

```bash
sudo ufw allow from 10.0.0.0/8 to any port 8000 proto tcp
```

콘솔 서버의 내부 IP 확인:

```bash
hostname -I
```

### 4) 브라우저로 접속 확인

같은 내부망의 PC/노트북에서:

1. `http://<콘솔서버 내부IP>:8000` 접속 → 세션이 없으므로 자동으로
   `/login` 페이지로 이동합니다.
2. 2)에서 만든 관리자 계정으로 로그인 → 메인 화면(`/`)으로 이동하고,
   우측 상단에 로그인한 계정명이 표시됩니다.
3. "1. 대상 서버 연결 정보"에 실제 관리 대상 Ubuntu 서버의
   호스트/포트(기본 22)/SSH 로그인 계정/인증 방식(비밀번호 또는 SSH Key)을
   입력 후 **연결 테스트** 클릭 → "연결 성공"이 뜨는지 확인합니다.
4. "2. 작업 선택"에서 테스트용 계정으로 **계정 생성**을 한 번 실행해보고,
   대상 서버에서 `id <생성한계정>` 으로 실제로 만들어졌는지 확인합니다.
5. 웹 UI 하단 "4. 실행 로그"에서 방금 수행한 작업의 각 단계별 명령/출력/
   성공여부가 기록되는지 확인합니다.
6. 테스트가 끝나면 같은 계정으로 **계정 삭제**를 실행해 홈 디렉토리와
   `/var/spool/mail` 메일함까지 정리되는지 확인합니다.

### 5) 로그아웃 / 계정 관리

- 우측 상단 "로그아웃" 버튼으로 세션 쿠키를 제거할 수 있습니다.
- 계정 추가/비밀번호 변경/삭제/목록은 서버에서:

```bash
cd backend && source .venv/bin/activate
python manage_users.py add <아이디>
python manage_users.py passwd <아이디>
python manage_users.py remove <아이디>
python manage_users.py list
```

### 상시 운영으로 전환하려면

터미널을 닫아도 계속 떠 있어야 한다면 systemd 서비스로 등록하는 것을
권장합니다(nohup/백그라운드 실행보다 재시작/로그 관리가 쉽습니다):

```ini
# /etc/systemd/system/ubuntu-account-console.service
[Unit]
Description=Ubuntu Account Admin Console
After=network.target

[Service]
WorkingDirectory=/opt/ubuntu-/backend
Environment=HOST=0.0.0.0
Environment=PORT=8000
ExecStart=/opt/ubuntu-/backend/.venv/bin/python run.py
Restart=on-failure
User=someuser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ubuntu-account-console
```

## 대상 서버(관리 대상 Ubuntu) 요구사항

- SSH 로그인 계정은 `root`이거나, `useradd`/`userdel`/`usermod`/`groupadd`를
  비밀번호 없이 실행할 수 있는 `sudo` 권한(NOPASSWD)이 있어야 합니다.
  `root`가 아닌 계정으로 로그인하면 모든 관리 명령을 자동으로
  `sudo -n bash -c '...'` 로 감싸서 실행하며, sudo 권한이 없으면 해당 단계가
  실패로 기록됩니다.
- SSH 포트는 기본 22번이며, 웹 UI의 "포트" 입력값을 그대로 사용해 접속합니다
  (22번이 아닌 포트를 쓰는 서버도 지원).
- 인증 방식은 비밀번호 또는 SSH 개인키(PEM 텍스트 붙여넣기, 선택적 passphrase)
  둘 다 지원합니다.

## 보안 주의사항

- 이 도구는 원격 서버에 대해 루트 권한 작업(계정 생성/삭제, 그룹 변경)을
  수행하므로, **반드시 신뢰할 수 있는 내부망/VPN에서만** 접근 가능하게
  배포하세요. 웹 UI 자체 로그인(위 섹션)이 있지만, 그렇다고 인터넷에
  직접 노출해도 되는 것은 아닙니다.
- 배포 시 HTTPS(TLS)를 반드시 적용하세요(리버스 프록시로 TLS 종료 권장) —
  SSH 비밀번호/개인키/로그인 비밀번호가 브라우저→백엔드 구간에서 평문으로
  전송됩니다. HTTPS 뒤에 두는 경우 `COOKIE_SECURE=true` 환경변수로 세션
  쿠키에 `Secure` 속성을 켜세요.
- 입력된 SSH 비밀번호/개인키는 디스크에 저장하지 않고 요청 처리 중에만
  메모리에서 사용됩니다. 로그(`actions.log`)에는 비밀번호/개인키가 절대
  기록되지 않으며, 계정 생성 시 설정한 초기 비밀번호도 로그에는 `****` 로
  마스킹됩니다.
- 웹 UI 로그인 비밀번호 해시(`backend/data/users.json`)와 세션 서명 키
  (`backend/data/secret_key`)는 `.gitignore`에 포함되어 있어 저장소에
  커밋되지 않으며, 파일 권한도 소유자만 읽기/쓰기(600)로 제한됩니다.
- 사용자명/그룹명은 Debian `adduser` 규칙(`^[a-z_][a-z0-9_-]*\$?$`)으로
  검증하며, 모든 값은 원격 실행 전 `shlex.quote` 로 셸 이스케이프됩니다.

## 환경변수 요약

| 변수 | 기본값 | 설명 |
|---|---|---|
| `HOST` | `0.0.0.0` | 콘솔 서버 바인딩 주소 |
| `PORT` | `8000` | 콘솔 서버 포트 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | (없음) | `users.json`이 비어있을 때만 최초 1회 관리자 계정 자동 생성 |
| `SECRET_KEY` | 자동 생성(`backend/data/secret_key`) | 세션 쿠키 서명 키 |
| `SESSION_TTL_SECONDS` | `28800`(8시간) | 로그인 세션 유지 시간 |
| `COOKIE_SECURE` | `false` | `true`로 설정 시 세션 쿠키에 `Secure` 속성 적용(HTTPS 필수) |

## 디렉토리 구조

```
backend/
  app/
    main.py          FastAPI 라우트 (+로그인 가드)
    auth.py           로그인 인증 (비밀번호 해시/세션 토큰/무차별대입 방지)
    ssh_manager.py    SSH 연결/명령 실행 (paramiko)
    operations.py     4가지 작업의 단계별 로직
    validation.py     사용자명/그룹명/경로 검증
    logger.py         JSON Lines 감사 로그
  manage_users.py     웹 UI 로그인 계정 관리 CLI
  requirements.txt
  run.py
frontend/
  index.html / style.css / app.js     메인 콘솔 UI
  login.html / login.js               로그인 화면
```
