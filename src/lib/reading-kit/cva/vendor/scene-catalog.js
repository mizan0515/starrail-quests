/* Editable scene compositions. Canonical Elio scenes are read from the supplied local data. */
(function (global) {
  'use strict';

  const sourceScenes = new Map((global.FW_STORY || []).map(scene => [scene.id, scene]));
  const mediaByScene = {
    'hub-role': 'scene-hub-role',
    'lupa-awakens': 'scene-lupa-awakens',
    'reality-reunion': 'scene-reality-reunion'
  };
  function selectedScene(id) {
    const source = sourceScenes.get(id);
    if (!source || typeof source.title !== 'string' || typeof source.body !== 'string' || source.image !== 'assets/' + id + '.webp') {
      throw new Error('제공된 Elio 장면 자료를 먼저 불러와 주세요: ' + id);
    }
    return { id, title: source.title, body: source.body, label: source.eyebrow || '', image: mediaByScene[id] };
  }
  const chosen = global.CVA_LOCAL_SCENE_ITEMS.map(value => ({ ...value }));
  const clone = value => JSON.parse(JSON.stringify(value));
  const item = (id, title, body, label = '', image = '', value) => ({ id, title, body, label, image, ...(value === undefined ? {} : { value }) });
  const props = (eyebrow, title, body, image, caption, relationLabel, items) => ({ eyebrow, title, body, image, caption, relationLabel, items });
  function entry(variant, name, description, familyId, purpose, value) {
    return { id: 'scene-' + variant, variant, name, title: value.title, description, familyId, purpose, props: value };
  }

  const entries = [
    entry('chapter-cover', '이야기 표지', '대표 장면과 장·회차 이름, 이어 읽을 장면을 한 화면에 둡니다.', '13', 'story', props(
      'ELIO / 명조 제2장 6막', '선택한 장면에서, 이어지는 맥락으로.',
      '중추에서 벌어진 변화, 루파가 기억을 되찾는 순간, 현실에서의 재회를 따라 읽습니다.',
      'scene-hub-role', '제공된 Elio 자료에서 고른 중추 장면',
      '세 장면을 고른 읽기 예시입니다. 중간 장면은 생략했으며 전체 이야기는 원자료에서 이어 읽습니다.', clone(chosen)
    )),
    entry('scene-rail', 'Elio 장면 시간선', '축 가까이 놓인 원형 사진과 큰 장면 번호로 순서와 맥락을 함께 읽습니다.', '7', 'story', props(
      '장면을 따라 읽기', '각자의 선택은 어떻게 이어졌을까.',
      '제공된 이야기에서 고른 세 장면을 작품이 보여 준 순서로 읽습니다.',
      '', '', '연결은 이 페이지의 읽기 순서입니다. 장면 사이 간격은 실제 기간이나 새로운 인과 관계를 뜻하지 않습니다.', clone(chosen)
    )),
    entry('branch-stage', '선택과 두 갈래', '하나의 시작, 서로 다른 두 경로와 다시 만나는 결과를 구분합니다.', '2', 'story', props(
      '사건 경로 / 작성 예시', '하나의 선택에서, 서로 다른 길로.',
      '갈림점과 두 경로의 사건을 적고, 실제로 다시 만나는 경우에만 합류 결과를 이어 줍니다.',
      '', '', '작성 예시의 항목 순서는 시작 → 경로 A·B → 합류 결과입니다. 각 경로의 조건은 라벨에 적습니다.', [
        item('branch-start', '갈림점이 되는 사건', '두 경로가 갈라지는 확인된 계기를 입력합니다.', '시작'),
        item('branch-a', '함께 움직이는 경로', '다른 인물과 함께 행동할 때의 사건을 입력합니다.', '경로 A · 함께 움직일 때'),
        item('branch-b', '혼자 움직이는 경로', '혼자 행동할 때의 사건을 입력합니다.', '경로 B · 혼자 움직일 때'),
        item('branch-result', '다시 만나는 사건', '두 경로가 실제로 만나는 지점을 입력합니다.', '합류 결과')
      ]
    )),
    entry('merge-stage', '여러 사건의 합류', '별개의 입력과 마지막 공동 사건을 모이는 방향으로 보여 줍니다.', '2', 'story', props(
      '사건의 합류 / 작성 예시', '서로 다른 기록이, 하나의 사건으로.',
      '각 경로에서 확인한 기록을 따로 남기고, 무엇이 공동 사건에 이어졌는지 설명합니다.',
      '', '', '작성 예시에서 앞의 세 항목은 입력이고 마지막 항목은 공동 사건입니다. 함께 배치한 것만으로 실제 합류가 생기지는 않습니다.', [
        item('merge-a', '경로 A의 기록', '첫 경로에서 확인한 사건과 출처를 입력합니다.', '입력 · 경로 A'),
        item('merge-b', '경로 B의 기록', '다른 경로에서 확인한 사건과 출처를 입력합니다.', '입력 · 경로 B'),
        item('merge-witness', '별개의 증언', '앞의 기록과 만나는 확인된 증언을 입력합니다.', '입력 · 증언'),
        item('merge-common', '공동 사건', '여러 입력이 만나는 사건과 연결 이유를 입력합니다.', '합류 뒤 결과')
      ]
    )),
    entry('character-orbit', '중심 인물과 주변', '한 인물을 중심으로 다른 인물과의 관계를 살펴봅니다.', '6', 'relations', props(
      '인물 관계 / 작성 예시', '인물 A와 연결된 세 관계.',
      '중심 인물 A와 주변 인물의 이름을 바꾸고, 각 관계에서 누가 누구에게 무엇을 하는지 적습니다.',
      '', '확인된 인물 그림을 준비한 뒤 이미지 자리에서 선택합니다.',
      '연결선은 중심과 주변의 대응을 보여 줍니다. 도움·정보·대립의 방향은 각 항목의 라벨에 명시합니다.', [
        item('orbit-b', '인물 B', 'A에게 도움을 받는 인물과 행동의 이유를 입력합니다.', 'A → B · 도움'),
        item('orbit-c', '인물 C', 'A가 정보를 전하는 인물과 내용을 입력합니다.', 'A → C · 정보 전달'),
        item('orbit-d', '인물 D', 'A와 의견이 충돌하는 인물과 이유를 입력합니다.', 'A ↔ D · 대립')
      ]
    )),
    entry('relationship-ledger', '관계와 방향 목록', '방향이 있는 행동, 양방향 대립과 소속을 같은 기준으로 비교합니다.', '6', 'relations', props(
      '관계 기록 / 작성 예시', '누가 누구에게, 어떤 영향을 주는가.',
      '인물 이름, 관계의 방향, 행동이나 대사가 나온 장면을 한 항목에 묶습니다.',
      '', '', '→는 한 방향, ↔는 양방향, ∈는 소속입니다. 각 기호의 의미를 확인한 자료와 함께 바꾸어 쓰세요.', [
        item('relation-help', '인물 A → 인물 B', '도움을 준 행동과 그 장면의 출처를 입력합니다.', '한 방향 · 도움', '', '누가 → 누구에게'),
        item('relation-info', '인물 B → 인물 C', '정보를 전한 말과 확인한 장면을 입력합니다.', '한 방향 · 정보 전달', '', '누가 → 누구에게'),
        item('relation-conflict', '인물 C ↔ 인물 D', '서로 충돌하는 이유와 원자료를 입력합니다.', '양방향 · 대립', '', '누구 ↔ 누구'),
        item('relation-group', '인물 A ∈ 집단', '해당 집단에 속한다는 근거를 입력합니다.', '포함 · 소속', '', '인물 ∈ 집단')
      ]
    )),
    entry('item-dossier', '아이템 상세 도감', '한 아이템의 이름, 소속, 쓰임과 확인할 자료를 크게 소개합니다.', '8', 'items', props(
      '아이템 도감 / 작성 예시', '아이템 하나를, 필요한 깊이로.',
      '아이템의 실제 이름과 그림을 고르고, 쓰임을 이해하는 데 필요한 정보부터 입력합니다.',
      '', '현재는 아이템 그림을 넣을 작성 자리입니다.',
      '범주와 용도는 서로 다른 정보입니다. 실제 수치·획득 조건·설명 문구는 게임 자료에서 확인해 입력합니다.', [
        item('dossier-category', '소속 범주', '이 아이템이 속하는 큰 범주와 하위 분류를 입력합니다.', '분류'),
        item('dossier-use', '사용하는 상황', '어디에서 어떤 목적에 쓰이는지 입력합니다.', '용도'),
        item('dossier-condition', '획득하거나 사용하는 조건', '확인된 조건과 필요한 앞 단계를 입력합니다.', '조건'),
        item('dossier-source', '확인할 자료', '아이템 설명과 그림이 나온 원자료를 입력합니다.', '출처')
      ]
    )),
    entry('loadout-slots', '장비와 슬롯', '전체 구성 안에서 각 장비가 맡는 자리와 역할을 보여 줍니다.', '5', 'items', props(
      '장비 구성 / 작성 예시', '무엇을 어느 자리에 쓰는가.',
      '장비 이름과 그림을 넣고, 각 슬롯의 역할과 실제 장착 조건을 설명합니다.',
      '', '슬롯 이름과 구성은 작성 예시이며 실제 장비 화면은 원자료로 교체합니다.',
      '각 칸은 장비의 자리입니다. 칸의 크기와 위치가 실제 능력치나 중요도 순위를 뜻하지 않습니다.', [
        item('slot-weapon', '무기 이름 입력', '장비가 맡는 역할과 장착 조건을 입력합니다.', '무기 슬롯'),
        item('slot-armor', '방어구 이름 입력', '방어구의 역할과 확인된 조건을 입력합니다.', '방어구 슬롯'),
        item('slot-tool', '도구 이름 입력', '도구를 사용하는 상황과 조건을 입력합니다.', '도구 슬롯'),
        item('slot-charm', '보조 장비 이름 입력', '다른 장비와 함께 쓰는 이유를 입력합니다.', '보조 슬롯')
      ]
    )),
    entry('crafting-recipe', '재료와 제작 결과', '입력 재료와 마지막 제작 결과를 조립 관계로 보여 줍니다.', '3', 'items', props(
      '아이템 제작 / 작성 예시', '재료가 모여, 결과가 됩니다.',
      '필요한 재료와 조건을 먼저 확인한 뒤, 제작으로 얻는 결과를 설명합니다.',
      '', '', '앞의 두 항목은 입력 재료이고 마지막 항목은 제작 결과입니다. 확인되지 않은 조합식이나 수량을 만들어 넣지 않습니다.', [
        item('recipe-a', '첫 번째 재료', '확인한 재료 이름과 필요한 조건을 입력합니다.', '입력 재료 01'),
        item('recipe-b', '두 번째 재료', '다른 재료 이름과 필요한 조건을 입력합니다.', '입력 재료 02'),
        item('recipe-result', '제작 결과', '실제로 얻는 아이템과 제작 조건을 입력합니다.', '제작 뒤 결과')
      ]
    )),
    entry('nested-world', '공통 세계와 포함 항목', '하나의 공통 범위 안에서 구성 항목과 설명을 읽습니다.', '5', 'story', props(
      '세계 구조 / 작성 예시', '같은 세계 안에, 무엇이 들어 있는가.',
      '하나의 공통 범위와 그 범위에 속한 항목을 적습니다. 서로 다른 깊이의 계층은 원본 포함 관계 모듈에서 명시합니다.',
      '', '', '모든 항목이 하나의 공통 범위에 속하는 작성 예시입니다. 항목끼리의 상하 계층이나 실제 면적은 이 배치에서 주장하지 않습니다.', [
        item('world-whole', '첫 번째 구성 영역', '공통 세계 안에 속하는 구성 영역을 입력합니다.', '공통 범위에 포함'),
        item('world-continent', '두 번째 구성 영역', '같은 세계 안에 속하는 다른 영역을 입력합니다.', '공통 범위에 포함'),
        item('world-region', '세 번째 구성 영역', '공통 세계 안에서 이 영역의 역할을 입력합니다.', '공통 범위에 포함'),
        item('world-place', '네 번째 구성 영역', '같은 범위 안에서 이 영역의 역할을 입력합니다.', '공통 범위에 포함')
      ]
    )),
    entry('quest-route', '목표까지의 이동', '출발·발견·전환·행동·결과를 이동 순서로 설명합니다.', '1', 'story', props(
      '사건의 이동 / 작성 예시', '어디에서 시작해, 무엇에 도달하는가.',
      '장소와 사건을 순서대로 넣고, 다음 단계로 이동하는 이유를 함께 적습니다.',
      '', '', '항목은 따라 읽을 순서입니다. 경로의 길이에서 실제 이동 거리나 소요 시간을 추정하지 않습니다.', [
        item('route-start', '출발 장소', '이야기를 시작하는 장소와 목적을 입력합니다.', '01 · 출발'),
        item('route-clue', '단서를 만나는 곳', '다음 행동을 알게 되는 장면을 입력합니다.', '02 · 발견'),
        item('route-turn', '경로가 바뀌는 곳', '전환이 생긴 사건과 이유를 입력합니다.', '03 · 전환'),
        item('route-action', '행동이 일어나는 곳', '목표를 향해 실제로 한 행동을 입력합니다.', '04 · 행동'),
        item('route-result', '도달한 결과', '확인한 결과와 이어지는 이야기를 입력합니다.', '05 · 결과')
      ]
    )),
    entry('parallel-lanes', '여러 방송의 레인', '서로 다른 방송의 장면을 소속과 원본 시각으로 나누어 읽습니다.', '7', 'broadcast', props(
      '방송 기록 / 작성 예시', '같은 질문을, 서로 다른 방송에서.',
      '방송 A·B의 장면을 각자의 레인에 놓고 원본 시각과 앞뒤 맥락을 입력합니다.',
      '', '', '항목 순서는 A 도입·B 도입·A 주요 장면·B 주요 장면입니다. 나란한 배치만으로 동시 방송이나 같은 사건이라고 판단하지 않습니다.', [
        item('lane-a-open', '방송 A의 도입', '첫 방송의 시작 맥락과 영상 위치를 입력합니다.', '방송 A · 도입', '', '원본 시각 입력'),
        item('lane-b-open', '방송 B의 도입', '다른 방송의 시작 맥락과 영상 위치를 입력합니다.', '방송 B · 도입', '', '원본 시각 입력'),
        item('lane-a-main', '방송 A의 주요 장면', '첫 방송에서 다시 볼 후보를 입력합니다.', '방송 A · 주요 장면', '', '원본 시각 입력'),
        item('lane-b-main', '방송 B의 주요 장면', '다른 방송에서 다시 볼 후보를 입력합니다.', '방송 B · 주요 장면', '', '원본 시각 입력')
      ]
    )),
    entry('phase-ladder', '단계와 도달 상태', '탐색에서 확인까지 각 단계가 맡는 일을 구분합니다.', '1', 'intro', props(
      '단계 안내 / 작성 예시', '다음 단계에 가기 전에, 무엇을 확인할까.',
      '단계마다 해야 할 일과 다음 단계로 넘어갈 조건을 설명합니다.',
      '', '', '높이는 단계의 순서를 나타냅니다. 능력치나 작업량을 비교하는 수치 축이 아닙니다.', [
        item('phase-find', '탐색', '필요한 원자료와 범위를 찾습니다.', '첫 단계'),
        item('phase-decide', '결정', '검토할 질문과 필요한 항목을 고릅니다.', '다음 단계'),
        item('phase-do', '구성', '확인한 내용을 읽을 수 있는 순서로 놓습니다.', '실행 단계'),
        item('phase-check', '확인', '결과와 원자료를 함께 살펴봅니다.', '완료 전 확인')
      ]
    )),
    entry('feedback-ring', '확인과 되돌아보기', '결과를 살펴보고 앞 단계에 돌아가는 피드백을 설명합니다.', '4', 'broadcast', props(
      '검토 과정 / 작성 예시', '확인한 결과에서, 다음 조정으로.',
      '장면을 고른 이유와 실제 맥락을 비교하고, 필요한 부분을 다시 조정합니다.',
      '', '', '읽기 → 검토 → 조정 → 확인 → 다시 읽기의 순환입니다. 한 번 돌 때마다 성과가 늘어난다고 가정하지 않습니다.', [
        item('feedback-read', '원자료 읽기', '방송의 흐름과 후보의 출처를 확인합니다.', '입력'),
        item('feedback-review', '후보 검토', '선정 이유를 앞뒤 맥락과 비교합니다.', '검토'),
        item('feedback-adjust', '구성 조정', '빠진 맥락이나 연결이 있으면 바꿉니다.', '조정'),
        item('feedback-check', '결과 확인', '원자료와 결과를 다시 읽고 검토로 돌아갑니다.', '피드백')
      ]
    )),
    entry('before-after', '같은 기준의 전후', '출발 상태와 바뀐 상태를 같은 질문으로 비교합니다.', '9', 'intro', props(
      '전후 비교 / 작성 예시', '무엇이 달라졌는지, 같은 기준으로.',
      '같은 대상의 출발 상태와 바뀐 상태를 놓고, 변화 과정과 확인 조건을 설명합니다.',
      '', '실제 비교 화면과 기준이 준비되면 두 항목의 이미지를 교체합니다.',
      '두 항목은 같은 대상을 같은 기준으로 비교하는 작성 자리입니다. 실제 성과나 변화량은 입력한 자료로 확인합니다.', [
        item('before-state', '출발 상태', '변화 전의 상황과 확인 조건을 입력합니다.', '이전', '', '같은 기준 입력'),
        item('after-state', '바뀐 상태', '변화 뒤의 상황과 같은 확인 조건을 입력합니다.', '이후', '', '같은 기준 입력')
      ]
    )),
    entry('evidence-focus', '장면과 원자료', '큰 장면 이미지와 원래 설명을 가까이 두어 근거를 확인합니다.', '15', 'story', props(
      chosen[0].label + ' · 장면의 출처', chosen[0].title, chosen[0].body,
      chosen[0].image, chosen[0].title + ' · 제공된 Elio 장면 자료',
      '제공된 장면 이름·설명·사진을 함께 읽습니다. 이 장면의 앞뒤 맥락은 원래 이야기에서 확인합니다.', [
        item('evidence-scene', '원래 장면 이름', chosen[0].title, '장면 식별'),
        item('evidence-scope', '자료의 범위', '명조 제2장 6막에서 고른 장면입니다.', '선택 범위')
      ]
    )),
    entry('story-montage', '연속 장면 갤러리', '한 장면을 크게 보고 나머지 장면을 이어지는 패널로 읽습니다.', '14', 'story', props(
      'ELIO / 선택한 장면', '장면마다 남은 변화와 흔적.',
      '제공된 세 장면의 사진과 원래 설명을 한 페이지에서 이어 읽습니다.',
      '', '장면 사진과 설명은 제공된 Elio 자료에서 선택했습니다.',
      '패널 순서는 작품이 보여 준 순서입니다. 일부 장면을 고른 구성으로 전체 사건을 대체하지 않습니다.', clone(chosen)
    )),
    entry('world-atlas', '영역과 장소 목록', '전체 영역을 보면서 각 장소의 설명으로 이동합니다.', '11', 'items', props(
      '영역 안내 / 작성 예시', '전체 안에서, 필요한 장소를 찾습니다.',
      '각 구역의 이름과 역할을 입력하고, 전체 지도와 실제 위치 자료를 연결합니다.',
      'product-coast', 'Forma의 기존 생성 참고 이미지 · 실제 게임 지도는 원자료로 교체합니다.',
      '아래는 영역을 나누어 읽는 작성 예시입니다. 그림이나 항목 배치에서 실제 좌표·거리·면적을 추정하지 않습니다.', [
        item('atlas-north', '첫 번째 구역', '이 구역의 장소와 확인할 내용을 입력합니다.', '구역 01'),
        item('atlas-east', '두 번째 구역', '다른 구역의 장소와 역할을 입력합니다.', '구역 02'),
        item('atlas-south', '세 번째 구역', '해당 구역에서 찾을 자료를 입력합니다.', '구역 03'),
        item('atlas-west', '네 번째 구역', '전체와 연결되는 의미를 입력합니다.', '구역 04')
      ]
    )),
    entry('spotlight-index', '대표 장면과 목차', '한 장면을 크게 읽고 다른 장면으로 이동하는 목차를 둡니다.', '17', 'story', props(
      'ELIO / 장면 탐색', '궁금한 장면에서, 이야기를 다시 읽습니다.',
      '장면 이름을 먼저 살펴보고 필요한 사진과 원래 설명을 선택해 읽습니다.',
      'scene-hub-role', '제공된 Elio 자료의 중추 장면',
      '목차와 상세는 같은 장면에 대응합니다. 선택이 바뀌어도 원래 장면 이름·사진·설명은 함께 유지합니다.', clone(chosen)
    )),
    entry('editorial-intro', '이미지와 핵심 문장', '브랜드 이미지와 한 문장, 도구의 역할을 편집 글처럼 소개합니다.', '16', 'intro', props(
      'CVA / 치즈 직조기', '찾던 순간을, 다시 만나세요.',
      '방송의 흐름을 읽고, 같은 순간을 맞춰 보고, 작품의 이야기를 따라갑니다. 지금 필요한 일을 먼저 골라 보세요.',
      'brand-welcome', 'CVA의 기존 환영 그림',
      '각 항목은 CVA 가족의 도구가 맡는 역할입니다. 지금 필요한 일을 기준으로 이어 읽습니다.', [
        item('intro-loki', 'Loki', '긴 방송의 흐름과 다시 볼 장면을 읽습니다.', '읽다'),
        item('intro-pad', 'TTaempad', '같은 순간의 시점을 비교하고 필요한 컷을 담습니다.', '담다'),
        item('intro-elio', 'Elio', '작품의 장면과 인물의 이야기를 따라갑니다.', '따라가다')
      ]
    ))
  ];

  // A supplied scene serves as visual evidence; no invented item stats or isolated artwork.
  const mirror = sourceScenes.get('copper-mirror');
  const dossier = entries.find(value => value.variant === 'item-dossier');
  if (mirror) {
  if (mirror.image !== 'assets/copper-mirror.jpg') throw new Error('청동거울의 기존 장면 자료가 필요합니다.');
  dossier.props.image = 'scene-copper-mirror';
  dossier.props.title = '청동거울을, 등장 장면과 함께.';
  dossier.props.body = '아이템의 모습과 쓰임은 확인한 장면에서 읽습니다. 능력치·등급·획득 조건은 아래 작성 항목에 근거를 확인한 뒤 적습니다.';
  dossier.props.caption = mirror.title + ' · 제공된 Elio 장면 이미지';
  dossier.props.items.unshift({ id:'mirror-source', title:mirror.title, body:mirror.body, label:mirror.eyebrow, image:'' });
  }

  const templates = [
    { id: 'scene-story', name: 'Elio 장면 이야기', description: '큰 표지와 장면 축에서 시작해 갤러리와 원자료로 이어지는 읽기 페이지입니다.', category: '이야기 · Elio', preferredProfile: 'elio', purpose: 'story', compositions: ['scene-chapter-cover', 'scene-scene-rail', 'scene-story-montage', 'scene-evidence-focus'] },
    { id: 'scene-characters', name: '인물과 사건의 갈래', description: '중심 인물, 관계의 방향, 선택과 합류를 작성하는 페이지입니다.', category: '인물 · 관계', preferredProfile: 'elio', purpose: 'relations', compositions: ['scene-character-orbit', 'scene-relationship-ledger', 'scene-branch-stage', 'scene-merge-stage'] },
    { id: 'scene-items', name: '아이템과 장비 도감', description: '아이템 상세, 장비의 자리, 제작 재료와 전체 영역을 나누어 읽습니다.', category: '아이템 · 도감', preferredProfile: 'forma', purpose: 'items', compositions: ['scene-item-dossier', 'scene-loadout-slots', 'scene-crafting-recipe', 'scene-world-atlas'] },
    { id: 'scene-broadcast', name: '방송 장면과 검토 흐름', description: '서로 다른 방송의 레인, 검토 단계와 조정 과정을 작성합니다.', category: '방송 · 편집', preferredProfile: 'editor', purpose: 'broadcast', compositions: ['scene-parallel-lanes', 'scene-phase-ladder', 'scene-before-after', 'scene-feedback-ring'] },
    { id: 'scene-intro', name: 'CVA 도구와 사용 과정', description: '브랜드 이미지와 도구 역할을 소개하고 구성·비교·검토로 이어집니다.', category: '소개 · 안내', preferredProfile: 'ttaem', purpose: 'intro', compositions: ['scene-editorial-intro', 'scene-phase-ladder', 'scene-before-after', 'scene-feedback-ring'] }
  ];

  function deepFreeze(value) {
    if (value && typeof value === 'object' && !Object.isFrozen(value)) {
      Object.values(value).forEach(deepFreeze);
      Object.freeze(value);
    }
    return value;
  }
  global.CVA_SCENES = deepFreeze({
    version: 'cva.scenes.v1', entries,
    variants: entries.map(value => ({ id: value.variant, label: value.name })),
    defaultProps: clone(entries[0].props), templates
  });
})(window);
