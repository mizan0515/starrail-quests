# 형식과 근거

## 로컬 구조

- 최신 데이터는 `Persistent/DesignData/Windows`; 부트스트랩은 `StreamingAssets/DesignData/Windows`에 있었다. 카탈로그가 지정한 콘텐츠 해시와 일치하는 파일만 읽는다.
- `M_DesignV.bytes`의 관찰 형식은 66바이트 SRMI다. 28–43 바이트 콘텐츠 해시의 각 4바이트 그룹을 뒤집어 카탈로그 파일명을 만든다. 44–51 바이트는 리틀 엔디언 파일 크기다. 다른 메타 필드는 추정하지 않고 원시 hex를 보존한다.
- DesignV v4 헤더는 빅 엔디언 magic=255, version=4, fileCount, entryCount다. 파일 이름 해시 8바이트, 콘텐츠 해시 16바이트, 크기 8바이트, 엔트리 수 4바이트가 뒤따른다. 엔트리는 키 8바이트·길이 4바이트·오프셋 4바이트다. 언어 길이 2바이트와 언어·플래그가 파일 끝에 있다.
- 표는 zigzag 행 수와 필드 존재 비트마스크, unsigned varint, zigzag enum, UTF-8 문자열, 리스트, 중첩 클래스로 구성된다. 기본값 필드는 생략될 수 있다. 스키마의 비활성 예약 슬롯을 임의로 제거하지 않는다.
- Korean TextMap은 hash/legacy, 문자열, has_params의 세 필드다. 원시 해시는 64비트이며 JavaScript Number로 바꾸면 정밀도가 손실된다.

## 해석 경계

장면의 임무 소속은 공개 JSON의 정확한 임무 폴더 ID와 로컬 MainMissionID가 일치할 때 연결한다. 그 밖의 장면은 별도 자료다. 제목·화자·본문은 모두 로컬 한국어 해시에 대응한다. 공개 AvatarConfig는 AvatarID→이름 해시 관계만 보조한다.

장면 검사기는 알려진 대사 ID들의 첫 출현 순서를 만들고, 로컬 공통 팩의 엔트리 중 해당 ID를 모두 포함하는 유일 후보에서 상대 순서를 확인한다. 주변 숫자와 우연히 일치할 수 있으므로 상태 이름은 `LOCAL_ID_ORDER_MATCH`다. 실행 조건이나 호출·분기 그래프를 디코딩했다고 표현하지 않는다. 대사 하나뿐인 장면과 여러 후보가 있는 장면은 미검증이다.

누락 참조 수는 참조 발생 수다. 중복 참조가 포함되므로 고유 미번역 문자열 수와 같지 않다. 임무 제목 수, 본문 연결 임무 수, 미귀속 대사 수는 따로 보고한다. 특정 버전의 수록 수를 이후 실행의 필수 정답으로 고정하지 않는다.

컷신 영상 자체의 자막·음성, 서버에서만 제공되는 데이터, 설치되지 않은 언어·패치, 파일에 없는 내용은 이 경로로 복원하지 않는다. 바이너리 원본이 변경되면 해당 실행의 해시 근거는 다시 확인한다.

## 참고 출처

- [사용자가 지정한 명조 퀘스트 자료집](https://mizan0515.github.io/wuwa-quests/index.html): 목록·분류·장면 읽기 흐름 참고.
- [TurnBasedGameData](https://github.com/DimbreathBot/TurnBasedGameData): 장면 관계와 필드 정의를 위한 보조 JSON.
- [HSR_Downloader DesignIndex](https://github.com/Hiro420/HSR_Downloader/blob/main/HSR_Downloader/DesignIndex.cs): 이전 카탈로그 형식의 비교 자료. 내장 v4 리더는 현재 로컬 헤더·길이를 검증한다.
- [HoyoBinStruct](https://github.com/BUnipendix/HoyoBinStruct): 이전 바이너리 직렬화 형식 비교 자료. 실행하거나 코드를 통째로 가져오지 않았다.

2026-10-07 확인한 4.5 클라이언트에서는 한국어 465,908개, 대사 240,489개, 서적 본문 1,103개, 캐릭터 이야기 456개를 읽었다. 이 수치는 그 설치본의 증거이며 최신 버전 보증이 아니다.
