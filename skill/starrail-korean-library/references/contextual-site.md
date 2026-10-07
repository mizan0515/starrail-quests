# 맥락을 연결하는 스타레일 자료집

## 입력과 추가 로컬 표

기존 추출물을 보존하고 별도 사이트를 만든다. 구조 스냅샷은 고정 커밋을 기록하고 공개 TextMap을 본문 보충에 사용하지 않는다. 필요한 보조 경로는 Story, ExcelOutput, Config/Level/Mission이며 추가 연결 조사에는 NPCDialogue·PropDialogue·Maze를 읽을 수 있다.

```powershell
python -X utf8 "<skill>/scripts/extend_tables.py" --game-data "<StarRail_Data>" --structure "<snapshot>" --output "<new extended.json>" --tables SubMission MissionChapterConfig MainMissionPack RelicConfig
```

`extend_tables.py`는 공개 첫 세 행으로 필드 배치를 식별하고 모든 로컬 행과 정확한 EOF를 검증한다. 활성 필드가 모호하면 중단한다. MissionChapterConfig의 ChapterName·StageName·ChapterDesc는 로컬 문자열 키다. 템플릿은 키가 ID/필드명과 일치하는지 확인하고, 보조 구조의 해시로 **로컬** 한국어 TextMap 제목을 읽는다. 공개 한국어 제목을 복사하지 않는다.

## 사이트 생성과 편집

`assets/reading-site`를 빈 프로젝트 디렉터리에 복사한다. 템플릿의 editorial/topics.json은 해설 형식과 이미 검토한 예시다. 새 설치본에서 인용 원문이 실제로 일치하는지 다시 검사한다. 예시 문서 ID를 신규 자료의 정답으로 고정하지 않는다.

```powershell
python -X utf8 "<site>/tools/prepare.py" --library "<preserved library>" --structure "<snapshot>" --extended "<extended.json>"
Copy-Item -LiteralPath "<site>/data/catalog.json" -Destination "<site>/public/catalog.json"
```

공식 Astro·Starlight를 프로젝트 안에 설치하고 잠금 파일을 유지한다. 전역 설치나 인증 값 복사는 필요 없다. 새 버전에서는 공식 요구사항을 확인한다. 검증한 조합은 Astro 7.3.6, Starlight 0.42.5, Node 24, pnpm 11.19.0이며, `satteri` 직접 의존성과 SSR external 설정을 유지한다.

```powershell
pnpm install --ignore-scripts --frozen-lockfile
$env:ASTRO_TELEMETRY_DISABLED='1'
$env:SITE_BASE='/<repository-name>'
node node_modules/astro/bin/astro.mjs build
python -X utf8 tools/preview.py --root dist --port 8794
```

SITE_BASE는 공개 프로젝트 주소와 일치해야 한다. 루트 사이트라면 `/`다. 파일 URL 대신 localhost에서 검색을 검증한다.

## 임무 읽기

1. 종류와 세계, 로컬 챕터 우선순위로 묶는다. NextTrack 참조는 챕터 안에서만 목록 순서의 보조로 쓴다. 타 챕터 참조 때문에 세계가 뒤섞이면 안 된다.
2. MainMissionPack의 배열 안에서 제목·종류·세계·챕터가 모두 같은 항목을 통합한다. 단계·대사·출처는 모두 보존하고 이전 문서 URL은 대표 문서로 연결한다.
3. SubMission 목표·설명과 MissionInfo의 Sequence/AnySequence/MultiSequence를 대조한다. 선택 경로와 동시 조건을 하나의 실제 회차 순서로 단정하지 않는다.
4. 장면과 단계는 정확한 ParamStr1/FinishKey 관계를 우선한다. 내용 대조만으로 배치한 장면에는 편집자 배치를 명시한다. 미연결 장면은 추가 대화로 남긴다.
5. DS/Story 숫자, 누락 해시를 주요 제목으로 보여주지 않는다. 출처 details에서는 재검증할 수 있도록 원래 값을 보존한다.

## 설정 해설의 편집 기준

자료 종류는 원문 탐색의 축이고, 해설의 축은 질문과 관계다. 예: 영생을 생물학·계층·신앙 변화·인물의 기억에 연결하고, 보리인을 종족·사냥단·정치적 소속으로 구분한다. 페나코니는 기억 물질·공간·밈을 구분한 뒤 조사자의 이해관계와 역사 편집을 함께 읽는다.

각 해설은 `id/title/world/deck/terms/sections/relations/reading/caution`을 갖는다. section마다 본문과 evidence(id,needle)를 두고 원문에 실제 needle이 존재해야 생성한다. relations는 방향을 읽을 수 있는 문장으로 쓰고 근거 문서를 지정한다. reading에는 각 자료를 읽을 이유를 적는다. caution은 그 해설의 구체적 시점·서술자·추측 경계를 설명한다. 별도 일반 경고문을 반복하지 않는다.

원문에 역방향 해설 링크를 붙인다. 키워드 기반 추천은 ‘본문의 관련 용어’로 표시한다. 해설 사이의 비교 링크는 독서 질문의 연결이며 세계관상 동일성이나 인과를 뜻하지 않는다.

### 세 관점과 연결 자료

`editorial/context-atlas.json`은 실제로 읽고 대조한 편집 자료다. `nodes`에는 `id/axis/name/question/intro/terms/topic/evidence/links/timeline`을 둔다. axis는 지역·인물·세계관이며 세력·종족 등은 필요한 연결 대상이다. links에는 `target/verb/why/status/evidence`, timeline에는 `when/title/text/evidence`를 둔다. 인용은 `id/title/anchor/quote/hash/status`로 원문에 고정한다.

비교는 같은 사건, 같은 인물, 같은 사회, 질문의 비교 중 실제 범위를 명시하고, 함께 말하는 것·갈라지는 초점·편집자의 읽기를 구분한다. 다른 시기의 문서를 동시 증언으로, 문서 번호·실험 번호를 시간으로 바꾸지 않는다. 원문에 없는 인물의 실명·친밀도·동기를 만들어 넣지 않는다. 단일 기록 안의 예외와 마지막 메모도 끝까지 읽는다.

각 편집 페이지 하단에 사용한 문장과 원문 위치를 문서별로 모은다. `SourceRegister`는 모든 인용에 직접 앵커 링크를 제공하며 식별자는 접는다. `verify_site.py`는 인용 문장·문자열 식별자·앵커, 연결 대상, 하단 근거, 전체 원문 단락의 보존을 검사한다. 예시 연결 자료를 복사했으면 신규 원자료에 맞춰 검증·수정한다.

### 짧은 맥락과 읽던 자리

`Scene`의 점선 용어 링크는 원문 텍스트를 보존한다. `ContextPanel`은 현재 문장 주변과 필요한 배경·근거를 보여주며, 닫기와 Escape로 포커스를 돌린다. 더 읽는 링크에는 URL의 `from`에 원문 문장 앵커를 남기고, 출처나 다른 관점을 거쳐도 유지한다. 복귀 대상은 같은 출처의 문서 경로로 제한한다. JavaScript 실패 시 기본 설정 링크를 사용할 수 있다.

관계는 소수의 연결과 이름·이유·근거를 직접 읽을 수 있는 DOM으로 표현한다. 확인된 사건은 세로 흐름, 미확인 선후는 독립 전환점, 다른 기록자의 견해는 대조 패널을 쓴다. 모바일에서 전체 그래프나 글자를 축소하지 않는다. 구체적 편집 이유는 템플릿의 `docs/editorial/CONNECTIONS.md`에 남긴다.

## 화면과 검증

프로젝트 docs/design/DESIGN.md를 우선한다. 임무 찾기와 설정 읽기는 명확한 두 진입점으로 둔다. 첫 화면에서 실제 분류와 자료가 보여야 한다. 해설은 짧은 제목·편안한 본문·인용 카드·관계 표·추천 읽기 순서로 구성한다. 접힌 출처는 보조 정보다.

빌드 후 전체 내부 문서/자산 링크·인용 앵커·통합 URL을 검사하고, 브라우저에서 종류/세계 필터, 빈 결과, 본문 검색, 해설→원문→해설, 단계/선택지, 유물 세트 연결을 확인한다. 모바일 메뉴와 가로 넘침, 키보드 검색, 밝고 어두운 테마도 확인한다. 파일 검사만으로 검색 동작을 PASS라 하지 않는다.

## 요청된 게시

현재 저장소 HEAD를 확인하고 사용자 변경을 덮어쓰지 않는다. 생성 데이터는 tools/pack_dataset.py의 검증 ZIP 조각으로, 코드와 해설은 일반 파일로 게시할 수 있다. tools/restore_dataset.py는 조각/ZIP/개별 파일 해시와 경로를 모두 검사한다. GitHub Actions에서 복원→잠금 설치→Starlight 빌드→Pagefind→링크 검증→gh-pages 일반 커밋→Pages 빌드 요청을 수행한다. Source는 Deploy from a branch / gh-pages / (root)다. 소스가 있는 main 루트를 게시 대상으로 지정하면 독서 사이트가 나오지 않는다.

GITHUB_TOKEN으로 만든 커밋은 Pages 빌드를 자동 촉발하지 않는다. 워크플로는 공식 Pages builds API를 명시적으로 요청한다. 최초 Source 설정이 아직 없으면 생성 브랜치까지만 준비하고 설정 후 실제 배포를 확인한다. 비밀 값을 수집하거나 별도 PAT를 요구하지 않는다. 빌드 토큰의 Git 인증을 사용한 push는 원래 checkout에서 실행하고 작업 트리에서는 파일 갱신·커밋만 한다.

GitHub 연결 도구에 저장소 생성·Pages 관리 기능이 없으면 사용자에게 정확한 설정 한 가지를 요청한다. 토큰을 탐색하거나 다른 저장소에 우회 게시하지 않는다. 공개 배포 성공 SHA, 실제 사이트 본문·검색·자산을 확인한 뒤 완료로 보고한다. 사이트의 수록 범위에는 .playable 컷신 누락과 미확인 진행 연결을 계속 표시한다.

## 가독성과 버전 탐색

### 전체 수록과 대사 재생성

1. `tools/export_dialogue_browser.py --game-data <StarRail_Data> --skill <skill> --site <site> --cache <snapshot cache>`는 로컬 TalkSentenceConfig와 한국어 TextMap을 다시 디코딩한다. 고정한 버전별 표의 ID·해시 메타데이터만 사용하고 본문은 로컬에서 읽는다. 결과는 `data/dialogue-index.json`과 `data/dialogues`다. 숫자 ID 패턴으로 임무나 버전을 추측하지 않는다. 표 순서는 실행 순서가 아니다.
2. `tools/build_explorer.py --game-data <StarRail_Data> --skill <skill> --site <site> --structure <structure>`는 WorldDataConfig, StoryAtlas, LoadingDesc, RogueAeonDisplay/StoryConfig를 재파싱한다. 전체 지역·인물 기록·배경 설명·에이언즈를 `data/explorer.json`으로 만든다. 이름 미확인 기록도 제외하지 않으며 확인된 수록 수는 실행 결과에서 읽는다. 짧은 이름의 일반 단어 내부 일치를 제외한다.
3. `tools/verify_complete_data.py --site <site>`로 전수 범위를 검증한다. `--local-csv <전체대사.csv> --snapshot-cache <cache>`를 추가하면 모든 대사의 본문·화자·해시·바이트 범위 및 최초 등장 근거를 독립 대조한다. 렌더링 후 `tools/verify_site.py`로 모든 대사와 인물 이야기의 원문 보존·출처·링크를 검사한다.
4. 추가 데이터는 `tools/pack_extra.py --site <site> --output <빈 bundle 폴더>`로 묶고 원래 dataset과 함께 `tools/restore_dataset.py --bundle dataset-extra`로 복원한다. 원본 데이터 ZIP을 덮어쓰지 않는다. 게시 전 두 묶음의 복원과 검증을 확인한다.

기본 목록 전체와 해설 목록을 구분한다. 지역 상세는 표의 설명·해당 지역 자료·LoadingDesc 지역 그룹, 인물 상세는 StoryAtlas 전체 이야기와 실제 이름 언급, 에이언즈는 기록 및 지역의 적용 사례에서 시작한다. 이름 언급 목록은 사실 관계도나 인과 분석을 대신하지 않는다. 확인되지 않은 캐릭터 이름, 한국어 누락, 미연결 컷신·임무는 빈틈으로 명시한다. 모든 읽기 화면의 하단에 실제 파일 해시와 원문 근거를 넣는다.

- Pretendard Variable v1.3.9와 고정된 CDN CSS, 시스템 글꼴 fallback을 사용한다. 글꼴 로딩 전에도 본문을 표시한다. 18px 기본 크기와 높은 대비를 유지하고 선택된 사이드바 항목은 테마별 반전색을 직접 확인한다.
- 설정 카드의 연결 흐름과 해설의 장별 이동은 `editorial/reading-guides.json`에서 편집한다. 이 흐름은 편집자가 읽는 순서이며 확정된 역사 연표가 아니다.
- 버전은 `editorial/mission-versions.json`의 고정 커밋·해시와 공개 MainMission 표의 최초 등장으로 분류한다. `python -X utf8 tools/map_versions.py --cache <snapshot cache>`로 재현·검증한다. 대사 본문을 공개 TextMap에서 받지 않는다. 최초 2.6 스냅샷에 이미 있는 임무는 세부 버전 미확인으로 둔다. ID의 숫자 패턴으로 버전을 추측하지 않는다.
- 버전 페이지 → 임무 종류/세계 필터 → 임무 → 관련 설정 → 근거 원문을 실제 브라우저에서 검증한다. 대표 버전의 결과 수, 빈 결과/초기화, 모바일 오버플로, 테마별 활성 메뉴 대비, Pagefind 본문 검색을 확인한다.
