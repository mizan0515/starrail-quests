# 게시 데이터와 종류별 목록

Browse는 선택한 자료 종류의 reading-catalog/<category>.json만 요청한다. 각 항목의 제목·본문 검색 필드·버전·지역·정렬·원문 주소는 기존 reading-catalog.json과 같다. 전체 endpoint는 호환과 범위 대조에 유지한다. 종류 전환 중 이전 요청이 늦게 도착해도 현재 결과를 덮어쓰지 않으며 실패한 종류는 다시 요청할 수 있다.

| 산출물 | 소비자와 공개 목적 |
|---|---|
| reading-catalog.json | 전체 목록 호환·범위 대조 |
| reading-catalog/<category>.json | Browse의 선택한 종류 목록·제목과 본문 검색 |
| 문서·대사·타임라인 HTML | 고정 앵커·판본·화자·사용 문맥을 포함한 정적 독서 |
| 원문 JSON·다운로드·출처 자료 | 원문 확인과 재사용; 기존 공개 역할 유지 |
| public/reading-data, dist/reading-data | 빌드와 전체 모델·해시·인용·링크 QA |

reading-data는 빌드 시 Astro 컴포넌트에서 가져오며 브라우저 fetch 대상이 아니다. 전체 모델과 shards는 로컬 검증에 보존하고 기존 publisher가 이 디렉터리만 sender-only hide한다. graph와 graph의 blockIndex를 한 경계로 제외하며 이전 게시 사본도 rsync의 정상 삭제 대상이 된다. 공개 본문이나 링크가 해당 URL을 요구하지 않는지 검사한다.

원문과 사용 위치는 기존 source ID·화자·판본·owner 연결을 유지한다. 같은 문자열이라는 이유로 서로 다른 자료를 합치지 않는다. 이미 검증된 정적 본문과 공통 UI 게시 컴파일러를 유지한다. 게시 제외 절감과 종류별 초기 로딩 절감을 분리해 보고하며 게시 상한과 원문 역변환 검사를 완화하지 않는다.
