# 스타레일 · 별의 기록

[한국어 자료집 읽기](https://mizan0515.github.io/starrail-quests/)

임무는 종류 → 세계 → 챕터로 묶고, 같은 임무의 내부 진행 조각은 하나의 문서로 읽습니다. 목표와 설명이 대화·선택지의 맥락을 이어 줍니다.

설정집은 지역·인물·세계관의 18개 읽기 항목과 질문으로 묶은 해설 7편을 제공합니다. 41개 이름 있는 연결, 확인된 기록 안의 사건 흐름과 생애 전환점, 서로 다른 기록자의 관점 비교로 흩어진 원문을 함께 읽습니다. 대사의 용어를 눌러 짧은 맥락과 근거를 확인하고, 더 깊이 읽은 뒤 같은 문장으로 돌아갈 수 있습니다.

편집 페이지 하단에는 실제로 대조한 원문과 인용 위치를 명시합니다. [묶음의 이유와 화면 설계](docs/editorial/CONNECTIONS.md)에 각 질문·원문·관계·해석의 경계를 기록했습니다. 원문 서술, 기록자의 주장, 편집자의 연결을 구분합니다.

Astro Starlight와 Pagefind의 한국어 본문 검색, 세계·자료 종류 필터, 모바일 메뉴와 밝고 어두운 테마를 제공합니다.

## 재생성

Node 24, pnpm 11.19.0, Python 3.10 이상을 사용합니다.

```sh
python tools/restore_dataset.py
pnpm install --ignore-scripts --frozen-lockfile
ASTRO_TELEMETRY_DISABLED=1 SITE_BASE=/starrail-quests node node_modules/astro/bin/astro.mjs build
python tools/preview.py --root dist --port 8794
```

Windows에서는 빌드 환경변수를 `$env:ASTRO_TELEMETRY_DISABLED='1'`, `$env:SITE_BASE='/starrail-quests'`로 지정합니다. 압축 조각과 복원 파일은 SHA-256으로 대조합니다. 원문을 갱신하려면 `skill/starrail-korean-library/SKILL.md`의 추출·검증·편집 절차를 따릅니다.

## 게시

GitHub Settings → Pages → Source를 **Deploy from a branch**, Branch를 **gh-pages / (root)**로 설정합니다. main에는 소스·편집 데이터·스킬을, gh-pages에는 빌드한 HTML·검색 색인을 둡니다. main 변경 시 GitHub Actions가 데이터를 복원하고 빌드·검증한 뒤 gh-pages에 일반 커밋으로 갱신하고 Pages 빌드를 요청합니다. 공개 저장소에는 게임 클라이언트 파일, 인증 자료, 개인 절대 경로, 작업용 전체 문자열 CSV를 포함하지 않습니다.

## 수록 범위

본문은 로컬 한국어 추출물입니다. 고정된 [TurnBasedGameData 구조 스냅샷](https://github.com/DimbreathBot/TurnBasedGameData/tree/724b139d8c9c32d12552eb95745a4fee72bfe48b)은 장면·진행·해시 연결에만 사용했습니다. 컷신 .playable 대사가 연결되지 않은 부분은 안내를 표시합니다. 임무 진행 참조·선행 조건과 편집자 배치는 실제 한 회차 플레이 순서와 구분합니다.

게임 원문과 편집자 해설은 화면에서 구분합니다. 게임명과 게임 원문의 권리는 해당 권리자에게 있습니다. [명조 퀘스트 자료집](https://mizan0515.github.io/wuwa-quests/index.html)의 탐색·읽기 흐름을 참고했습니다.
