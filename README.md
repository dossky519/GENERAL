# Ubuntu 계정 관리 콘솔 (SSH)

Ubuntu 서버의 계정을 SSH로 원격 관리하는 웹 도구입니다. 웹 UI에서 대상 서버의
SSH 접속 정보(비밀번호 또는 SSH Key)를 입력하면, 백엔드가 해당 서버에 SSH로
접속해 `useradd` / `userdel` / `usermod` / `groupadd` 등을 실행합니다.

## 지원 기능

1. **계정 생성** — `useradd`. 홈 디렉토리가 이미 존재하는지 먼저 검증(`test -d`)한 뒤,
   존재하면 기존 디렉토리를 재사용하고 소유권을 재설정합니다(덮어쓰기).
2. **계정 삭제** — `userdel -r` 실행 후 홈 디렉토리와 `/var/spool/mail/<user>`
   메일함이 실제로 삭제되었는지 재확인하고, 남아있으면 추가로 강제 삭제합니다.
3. **Primary 그룹 변경** — `usermod -g`.
4. **Secondary 그룹 변경** — `usermod -G`(전체 교체) 또는 `usermod -aG`(추가).

모든 작업은 검증 → 실행 → 결과 확인의 단계별 명령으로 쪼개어 실행되며, 각 단계의
명령어/표준출력/표준에러/종료코드/성공여부가 전부 기록됩니다. 성공/실패와 무관하게
모든 시도가 `backend/logs/actions.log` (JSON Lines)에 남고, 웹 UI 하단 "실행 로그"
에서 조회할 수 있습니다.

## 실행 방법

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py       # http://0.0.0.0:8000
```

브라우저에서 `http://<서버>:8000` 접속 → 연결 정보 입력 → 작업 탭 선택 → 실행.

## 대상 서버 요구사항

- SSH 로그인 계정은 `root`이거나, `useradd`/`userdel`/`usermod`/`groupadd`를
  비밀번호 없이 실행할 수 있는 `sudo` 권한(NOPASSWD)이 있어야 합니다.
  `root`가 아닌 계정으로 로그인하면 모든 관리 명령을 자동으로
  `sudo -n bash -c '...'` 로 감싸서 실행하며, sudo 권한이 없으면 해당 단계가
  실패로 기록됩니다.
- 인증 방식은 비밀번호 또는 SSH 개인키(PEM 텍스트 붙여넣기, 선택적 passphrase)
  둘 다 지원합니다.

## 보안 주의사항

- 이 도구는 원격 서버에 대해 루트 권한 작업(계정 생성/삭제, 그룹 변경)을
  수행하므로, **반드시 신뢰할 수 있는 내부망/VPN에서만** 접근 가능하게
  배포하고, 앞단에 인증(예: 리버스 프록시 + SSO, Basic Auth 등)을
  추가하는 것을 강력히 권장합니다. 현재 코드 자체에는 웹 UI 로그인 인증이
  포함되어 있지 않습니다.
- 배포 시 HTTPS(TLS)를 반드시 적용하세요 — SSH 비밀번호/개인키가
  브라우저→백엔드 구간에서 평문으로 전송됩니다.
- 입력된 SSH 비밀번호/개인키는 디스크에 저장하지 않고 요청 처리 중에만
  메모리에서 사용됩니다. 로그(`actions.log`)에는 비밀번호/개인키가 절대
  기록되지 않으며, 계정 생성 시 설정한 초기 비밀번호도 로그에는 `****` 로
  마스킹됩니다.
- 사용자명/그룹명은 Debian `adduser` 규칙(`^[a-z_][a-z0-9_-]*\$?$`)으로
  검증하며, 모든 값은 원격 실행 전 `shlex.quote` 로 셸 이스케이프됩니다.

## 디렉토리 구조

```
backend/
  app/
    main.py          FastAPI 라우트
    ssh_manager.py    SSH 연결/명령 실행 (paramiko)
    operations.py     4가지 작업의 단계별 로직
    validation.py     사용자명/그룹명/경로 검증
    logger.py         JSON Lines 감사 로그
  requirements.txt
  run.py
frontend/
  index.html / style.css / app.js   단일 페이지 UI
```
