# 미귀속 대사의 사용 장면 조사

2026년 10월 12일, 이슈 #20의 전체 원문 수집 중 미귀속 대사 조사 범위를 진행했다. 보존 로컬 한국어와 별도의 공식 4.6 수록본을 구분한다. 현재 설치본 전체 재추출 성공을 뜻하지 않는다.

## 조사 집합과 수록

보존 대사 240,078개에서 기존 임무 본문·보충 장면에 등장하는 87,048개를 제외한 153,030개와, 공식 추가·변경 대사 중 명시 임무 소유가 없는 3,915개를 조사했다. 두 집합의 교집합 30개는 같은 Talk ID의 보존본과 공식 4.6 표기 변경 행이다. 따라서 고유 조사 집합은 156,915개다. 숫자 접두사·폴더 이름·화자 이름을 임무 배정 근거로 쓰지 않는다.

| 배타적 판정 | 고유 대사 ID |
|---|---:|
| 정확한 대사 사용·표시·설정 참조 | 74,775 |
| 이벤트 이름만 남은 참조 | 1,594 |
| 제작 테스트 구조의 참조 | 13 |
| 현재 조사 범위에서 사용 참조 미확인 | 80,533 |

정확한 사용 참조가 있는 보존 미귀속 ID 74,743개와 공식 미귀속 ID 43개 중 11개는 같은 ID다. 74,743 + 43 − 11 = 74,775개를 사용 구조로 연결했다. 발화·UI 표시·토론 설정 참조의 역할을 구분하며, 원문이 없다는 판정과 사용 장면 미확인을 구분한다.

13,522개 사용 구조를 읽기 문서로 제공한다. 조사 집합의 구조별 참조를 중복 포함하면 89,782행이다. 같은 구조 안에 이미 임무에 연결된 원문도 있으면 앞뒤 문맥을 보존하기 위해 함께 읽는다. 이 문맥 행까지 포함한 독서 수록은 91,024행, 고유 Talk ID 75,886개다. 한국어 본문·화자는 기존 대사표를 참조하여 생성하며 원문 데이터를 복제 수정하지 않는다.

## 귀속의 의미

`TalkSentenceID`와 `TalkSentenceIDList`, VisitorBehaviorConfig의 `NpcBubbleTalkSentenceID` 직접 참조, 가장 가까운 실제 typed task, JSON pointer를 보존한다. `TalkSentence_<숫자>` 이벤트 이름만 발견된 문구는 그 이벤트에서 발화했다는 근거가 없어 일반 독서 장면에 올리지 않는다. 대사표의 ID 정의 및 복수 음성 표는 사용 장면 근거가 아니다.

VisitorBehaviorConfig의 270행은 방문객의 행동과 NPC 말풍선을 함께 기록한다. 231개 조사 ID 중 230개가 이번 추가 조사에서 사용 근거를 얻었다. 방문객의 말풍선 페이지에서 이 식별자들을 읽고, 각 참조의 VisitorID·BehaviorID·NPCID·PerformanceID 등 원자료 행 전체를 접힌 출처에서 확인할 수 있다. 이 표만으로 지역이나 임무 소속을 배정하지 않는다. 같은 문구를 참조하는 여러 행동 행도 모두 보존한다.

지리 연결은 RuntimeFloor의 명시 `FloorID`에서 `GroupPath`·JSON 경로·typed Performance 표 조회를 따라 해당 대사 구조에 도달하는 근거다. NPCList의 DialogueGroups·TalkDialogGroupIDList·FirstDialogueGroupID는 DialogueNPC의 GroupID→ActPath로, PropList는 DialogueProp의 같은 필드로 조회한다. 표의 대상 경로가 유일할 때만 채택하고 원래 엔티티 영역·필드·표 행·해시를 보존한다. Group ID와 Talk ID의 숫자가 같다는 사실만으로 대사를 귀속하지 않는다. MazePlane의 `FloorIDList`·`WorldID`와 WorldData의 문자열 해시를 대조한다. 지역과 세계의 한국어 이름은 공식 한국어 TextMap에서 읽으며 공개 TextMap 번역을 사용하지 않는다. 6,992개 사용 구조, 조사 집합의 고유 41,276개 대사에서 이 지리 경로가 확인됐다. 같은 구조가 여러 지역에서 사용되면 모두 보존한다. 지역 사용과 임무 소유, 한 회차의 실행 순서는 서로 다른 사실이다.

조건·선택지·참조 순서는 구조에 기록된 범위로 표시한다. 한국어가 없는 직접 참조는 개수와 식별자를 남기고 가상의 본문을 채우지 않는다. 제작 안내 원문은 제작 안내로 표시한다. 기존 임무의 primary/reference 소유 판정 및 원문 앵커는 변경하지 않는다.

## 입력과 재현

- 구조: DimbreathBot/TurnBasedGameData 고정 커밋 `8b178dd48698e5e7b12f0cc319ddab149f2ffc5c`, archive SHA-256 `e1eee10139b338e271467e1823cedb0ceba0c5c1c608771f2386639db308f02a`.
- 스캔: TextMap 본문을 제외한 JSON 137,887개를 읽었다. 사용 참조의 지원 범위는 위에 열거한 정확한 식별자 필드다. 전체 Timeline의 발화 트랙 해독을 완료했다는 주장은 아니다.
- 보존 입력: `data/dialogue-index.json`, `data/dialogues`, `data/documents`, `data/mission-dialogue-supplements.json`의 파일 해시를 overlay 근거에 고정한다.
- 공식 입력: `data/official-talk-library.json` 및 해당 공식 4.6 팩의 provenance를 고정한다. 보존본·공식본 차이는 행별 edition과 원문 복귀 주소에 보존한다.
- 생성: `python -B -X utf8 tools/build_dialogue_contexts.py --archive <고정 archive> --official-root <보존된 공식 팩> --skill <프로젝트 정본 skill>`.
- 구조·한국어 독립 대조: `python -B -X utf8 tools/verify_dialogue_contexts.py --archive <고정 archive> --official-root <보존된 공식 팩> --skill <프로젝트 정본 skill>`.
- HTML: `python -B -X utf8 tools/verify_dialogue_contexts.py --dist dist`. 모든 91,024행의 배열 순서·화자·선택지/대사 속성·혼합 역할 표시·기기와 설정 역할 표시·본문·Talk ID 앵커·대사표 복귀 링크를 대조한다. 모든 분류·120개 단위 목록의 원문 순서·중복 없는 세계 이름·장면 URL·복귀 앵커·최초 12개 표시도 대조한다.
- 표의 네이티브 행은 Python에서 정확히 직렬화한 문자열을 HTML에 표시한다. JavaScript 숫자 변환으로 64비트 SDFText 해시의 끝자리가 바뀌지 않도록 원래 정수 문자열을 보존한다. 독립 검증은 원자료 행과 직렬화 문자열, 모든 실제 HTML의 표 근거 텍스트를 각각 대조한다.
- 복원: `tools/restore_dataset.py`가 공개 overlay와 `editorial/dialogue-contexts-manifest.json`의 스키마·SHA·길이를 확인해 기존 번들 밖의 overlay만 별도로 복원한다. 기존 번들 및 원자료를 변경하지 않는다.

## 독서 진입과 확인 사례

`대화.html`에서 문구의 사용 성격을 선택한다. 각 분류는 120개 장면씩 나눠 전체 목록을 탐색하고 현재 목록의 화자·지역명·구절을 검색할 수 있다. 전체 본문은 기존 Pagefind 검색에 수록된다. 각 대사표 행에서도 사용 장면으로 이동할 수 있고, 장면에서 원래 대사표로 돌아간다. 필터·목록 페이지와 원문 앵커는 읽기 복귀 계약으로 보존한다.

장면 목록으로 복귀하면 기존 필터와 확장된 표시 개수를 먼저 복원하고, 해당 상태에서 보이는 원래 항목에만 키보드 포커스를 옮긴다. 필터에서 제외된 항목을 앵커만으로 노출하지 않는다. 같은 세계의 여러 지역은 각 지역의 근거를 유지하되 목록의 세계 이름은 한 번씩 표시한다.

- `대화/context-8ca624144ab93fcc.html#talk-156020600`: 아스트로폴리스 중심 구역의 셔틀 대화. RuntimeFloor 10551001 → GroupPath 170 → LevelGraph → TalkSentenceID. 실제 Started 조건은 접힌 원문 근거에 보존한다.
- `대화/context-656b8594a18dcb5c.html#talk-155050100`: 천음의 장원에서 참조하는 문구.
- `대화/context-7ff0852d380af3e2.html#talk-100025171`: 배점 피스톨의 펄 점수 문구. 동일한 Act를 명시 호출하는 보관 캐빈·「세상 끝」 술집 경로를 함께 보존한다.
- `대화/context-514bc312e9b66a57.html#talk-500100115`: 열차 방문객의 말풍선. 행의 명시 NpcBubbleTalkSentenceID, VisitorID 1009001, BehaviorID 1, NPCID 400001을 보존한다.
- `대화/context-60466fc9af675dfc.html#talk-408001579`: 기존 임무 보충기가 탐색하지 않던 FiveDim 콘텐츠 구조에 있는 신규 공식 한국어 문구. 2차원 시티 경로를 확인한다.

## 지원 범위와 추가 표 조사

전체 137,887개 JSON에서 Talk·Sentence·Dialog를 포함하는 필드의 정수·숫자 문자열·정수 목록과 조사 ID의 교집합을 추가 조사했다. 기기별 MobileSentenceID·PcSentenceID·PadSentenceID는 PlayMusicRhythmTalk의 SimpleTalkList와 IsMultiPlatform=true를 함께 확인해 18개를 추가했다. 기본 안내와 모바일·PC·패드 안내를 본문에서 표시한다. SentenceID는 PlayPenaconyEndmostSimpleTalk의 SimpleTalkList에서 15개를 확인했다. LastToBeginTalkSentenceID는 DebateInitialize의 TestimonySettingList에서 1개를 확인하고 토론 설정 참조로 표시한다. 이 재시작 참조를 발화 순서로 해석하지 않는다.

Excel 2,253개 표도 독립 조사했다. 기존 InclinationText·ChimeraDuelMaster·MazePuzzleOrigamiColony·VisitorBehaviorConfig 외에 HeartDialDialogue의 ControlTalkList로 5개를 확인했다. HeartDialTalk의 ID는 공식 한국어 SDFText 본문과 기존 대사표의 같은 ID 본문이 정확히 같을 때만 연결한다. VoiceID가 있으면 같은 ID여야 한다. 이 검사로 조사 집합 109개를 감정 조율의 표시 문구로 추가했다. 조사 후보 중 표시 문구가 다른 142개는 이 표를 귀속 근거로 채택하지 않는다. 네이티브 SDFText 해시와 행 전체를 보존하며 독립 검증기가 실제 공식 한국어 팩으로 다시 대조한다. 표 전체의 FloorIDList를 모든 문구의 지역으로 확장하지 않는다.

HeartDialTalk의 각 행에 기록된 FloorIDList는 그 행의 설정 대상 지역으로만 표시한다. 원래 Floor ID와 RuntimeFloor·MazePlane·WorldData의 필드 및 세계 ID 대응, 공식 한국어 이름이 확인된 지역명만 본문에 연결한다. 이름이 확인되지 않은 Floor ID는 접힌 네이티브 행에 보존한다. 이 표의 설정 대상은 실제 발화 장소·실행 순서를 뜻하지 않는다. 위 41,276개 지리 연결 수치는 RuntimeFloor에서 대사 사용 구조에 도달하는 별도 근거의 조사 ID 수이며, 행별 표의 대상 지역을 합산한 값이 아니다.

TalkSentenceConfig와 TalkSentenceMultiVoice는 대사 정의와 음성 대응표다. SwordTrainingStoryLine의 이벤트 이름만으로 발화를 확정하지 않는다. ActivityHipplenSentence의 TalkSentenceName은 문자열 해시 객체, PerformanceSkipCharacter의 동명 필드는 인물 이름 문자열이다. DialogueGroups 등 Group ID 필드는 실제 NPC/Prop 표의 ActPath를 조회하는 별도 영역이다. 이 조사 결과는 이 고정 스냅샷과 위 구조 의미로 입증한 필드 범위이며, 남은 80,533개가 게임에서 쓰이지 않는다는 뜻은 아니다. 전체 Timeline 발화 트랙 해독 완료라는 주장은 하지 않는다.

## 공개 빌드 크기와 보존 검증

`npm run build`는 Astro·Pagefind 빌드 뒤 `tools/optimize_publication.py`를 실행한다. 한국어 본문·원문 링크·문장 앵커와 SEO 메타데이터는 각 HTML에 보존한다. 반복되는 검색·메뉴·테마·목차·목록 탐색·푸터 UI만 원래 parser 위치에서 동기 공통 파일로 삽입한다. 동일 CSS·JS는 해시 파일로 외부화하며, Astro의 scope class만 충돌 없는 짧은 토큰으로 일관되게 대응한다. JS 비활성화 시 주요 목록의 실제 링크와 기존 비공식·권리 표시·자료 안내·GPL 소스 링크를 제공한다.

실제 runtime fetch는 reading-catalog.json·versions-data.json·atlas-data.json과 reading-data의 원문 shard 및 Pagefind를 사용한다. 이 파일들과 직접 연결된 대사원문 JSON을 보존한다. 공개 복원 mirror는 코드 저장소의 입력 그대로 유지하고, 런타임/링크 소비가 없는 명시 후보만 생성 dist에서 제외한다.

Astro의 build:done 통합 hook은 Starlight의 Pagefind hook 뒤에 위치하며, 기존 직접 Astro CLI 게시 경로에도 적용된다. 전체 gate만 검증용 환경변수로 후처리를 잠시 미뤄 이 HTML에서 기존 원문·모든 귀속·렌더링 검증을 수행한 뒤 후처리한다. `.codex-work/publication-build-report.json`에 모든 원래 HTML·CSS·JS의 SHA-256, 공통 파일 SHA, 토큰 대응, 제외 mirror를 기록한다. 공통 UI를 확장하고 토큰을 역변환한 모든 파일이 검증 전 바이트로 정확히 복구되어야 통과한다. 최종 실제 HTML에서도 기존 전체 한국어 원문과 새 장면의 모든 대사·앵커·출처 복귀 링크를 다시 대조한다. 최종 dist의 모든 파일은 합계 1,000,000,000바이트 이내여야 한다.

후처리 자체의 표식은 `data-ps`·`data-pj`·`data-pf`다. 역변환은 생성된 태그 형태와 정확한 삽입 fallback만 검색한 뒤 보고서의 완전 일치 키로 원래 문자열을 조회한다. 알려지지 않은 태그는 변환하지 않으며, 이 경우 원래 파일 SHA 대조가 실패한다. 공통 파일 수천 개의 거의 같은 URL을 정규식 대안으로 나열하지 않아 전체 재검증 비용을 줄인다. 원문·UI 재구성의 완전 일치 조건은 동일하다.

정적 검증과 실제 브라우저 점검·공개 반영은 별도 증거다. 이 문서 자체를 공개 배포 완료 증거로 사용하지 않는다.

## 이번 변경의 로컬 확인 경계

원자료 전수 대조는 귀속 74,775개·독서 91,024행·구조 13,522개를 확인했고, 표 근거 405개의 정확한 직렬화 문자열도 검증했다. 직접 Astro CLI 빌드의 build:done 경로는 원파일 34,547개와 공통 파일 1,842개의 완전 일치 재구성 검증을 통과했다. 이 빌드의 실제 dist는 994,556,005바이트다. 해당 HTML에서 모든 독서 행·표 근거와 131개 장면 목록의 순서·세계 이름·복귀 앵커도 통과했다.

이 직접 빌드 이후 페이지 간 목록 복귀 포커스와 HeartDialTalk의 행별 대상 지역 표시를 마지막 소스 변경으로 추가했다. 이 두 변경은 위 빌드 결과의 검증 범위에 포함하지 않는다. 실제 커밋 HEAD의 전체 gate와 그 결과물의 브라우저 검증에서 확인한 뒤 통합한다. 이전 원문·전체 링크 gate가 통과한 preflight 실행은 느린 최초 역변환을 중단하고 새 역변환으로 동일 파일 전부를 다시 검증했으며, 전체 gate 완료로 표시하지 않는다.
