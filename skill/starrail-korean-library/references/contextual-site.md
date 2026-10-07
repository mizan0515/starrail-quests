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

## 화면과 검증

프로젝트 docs/design/DESIGN.md를 우선한다. 임무 찾기와 설정 읽기는 명확한 두 진입점으로 둔다. 첫 화면에서 실제 분류와 자료가 보여야 한다. 해설은 짧은 제목·편안한 본문·인용 카드·관계 표·추천 읽기 순서로 구성한다. 접힌 출처는 보조 정보다.

빌드 후 전체 내부 문서/자산 링크·인용 앵커·통합 URL을 검사하고, 브라우저에서 종류/세계 필터, 빈 결과, 본문 검색, 해설→원문→해설, 단계/선택지, 유물 세트 연결을 확인한다. 모바일 메뉴와 가로 넘침, 키보드 검색, 밝고 어두운 테마도 확인한다. 파일 검사만으로 검색 동작을 PASS라 하지 않는다.

## 요청된 게시

현재 저장소 HEAD를 확인하고 사용자 변경을 덮어쓰지 않는다. 생성 데이터는 tools/pack_dataset.py의 검증 ZIP 조각으로, 코드와 해설은 일반 파일로 게시할 수 있다. tools/restore_dataset.py는 조각/ZIP/개별 파일 해시와 경로를 모두 검사한다. GitHub Actions에서 복원→잠금 설치→Starlight 빌드→Pagefind→링크 검증→gh-pages 일반 커밋→Pages 빌드 요청을 수행한다. Source는 Deploy from a branch / gh-pages / (root)다. 소스가 있는 main 루트를 게시 대상으로 지정하면 독서 사이트가 나오지 않는다.

GITHUB_TOKEN으로 만든 커밋은 Pages 빌드를 자동 촉발하지 않는다. 워크플로는 공식 Pages builds API를 명시적으로 요청한다. 최초 Source 설정이 아직 없으면 생성 브랜치까지만 준비하고 설정 후 실제 배포를 확인한다. 비밀 값을 수집하거나 별도 PAT를 요구하지 않는다. 빌드 토큰의 Git 인증을 사용한 push는 원래 checkout에서 실행하고 작업 트리에서는 파일 갱신·커밋만 한다.

GitHub 연결 도구에 저장소 생성·Pages 관리 기능이 없으면 사용자에게 정확한 설정 한 가지를 요청한다. 토큰을 탐색하거나 다른 저장소에 우회 게시하지 않는다. 공개 배포 성공 SHA, 실제 사이트 본문·검색·자산을 확인한 뒤 완료로 보고한다. 사이트의 수록 범위에는 .playable 컷신 누락과 미확인 진행 연결을 계속 표시한다.
