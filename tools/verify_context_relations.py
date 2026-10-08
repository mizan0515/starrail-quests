"""Check reviewed relation direction and exact original citations.

Natural-language review is recorded separately; this gate preserves its
explicit decisions and verifies the generated endpoints against those inputs.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
# Frozen decisions from the full original-context review; generated graph is not a semantic oracle.
REVIEWED = {'belobog/0': ['preservation',
               'outgoing',
               '원문 서술',
               '보존의 비호로 한파를 견뎠다고 기록된다',
               '공식 연대기는 벨로보그가 보존의 비호 덕분에 한파의 영향을 받지 않았다고 기록한다.'],
 'belobog/1': ['bronya',
               'outgoing',
               '편집자의 연결',
               '브로냐의 하층 방문과 훈련에 관한 의문',
               '브로냐는 하층의 열악한 환경을 본 뒤 자신의 훈련이 시민들을 원하는 삶으로 이끌 수 있는지 의문을 품는다.'],
 'belobog/2': ['natasha', 'outgoing', '편집자의 연결', '나타샤의 하층 의료 활동', '나타샤는 의료 물자가 부족한 하층에서 주민들을 돌보는 의사다.'],
 'bronya/0': ['belobog', 'outgoing', '원문 서술', '수호자의 계승자이자 철위대 지휘관', '브로냐는 벨로보그 수호자의 계승자이자 실버메인 철위대 지휘관으로 소개된다.'],
 'bronya/1': ['preservation',
              'outgoing',
              '편집자의 연결',
              '전우의 희생과 보호에 관한 발언',
              '브로냐의 이야기는 전우의 희생을 마주한 경험과 자신이 대신 희생하고 싶다는 발언을 기록한다.'],
 'bronya/2': ['seele', 'outgoing', '원문 서술', '축제에서 미소를 나눈다', '제레가 소매치기범을 철위대에 인계한 뒤, 무대 위 수호자와 제레는 서로 미소를 나눈다.'],
 'preservation/0': ['belobog',
                    'outgoing',
                    '원문 서술',
                    '벨로보그의 생존을 지킨 비호로 기록된다',
                    '벨로보그의 공식 연대기는 도시가 보존의 비호로 한파를 견뎠다고 기록한다.'],
 'preservation/1': ['xianzhou',
                    'outgoing',
                    '원문 서술',
                    '보천파가 따른 옛 주류 신앙으로 기록된다',
                    '선주 역사 글은 보천파가 클리포트의 운명의 길을 따랐으며 보천 신앙이 600여 년간 주류였다고 기록한다.'],
 'preservation/2': ['paths',
                    'outgoing',
                    '편집자의 연결',
                    '클리포트의 장벽과 축성가에 관한 기록',
                    '파벌 아카이브는 클리포트가 장벽을 짓는 동기에 관한 여러 소문과 사람들이 축성가에 합류한 기록을 소개한다.'],
 'xianzhou/0': ['immortality',
                'outgoing',
                '편집자의 연결',
                '영생 이후 선주의 인구·권력 변화',
                '단정사 논문은 영생 이후 인구가 늘고 일부 계층에 권력과 부가 집중되었다고 설명한다.'],
 'xianzhou/1': ['jingliu',
                'outgoing',
                '편집자의 연결',
                '경류의 전란 생존과 검술 수련 기록',
                '경류의 개인 이야기는 전란에서 살아남은 기억과 검을 통해 살고자 하는 의지를 깨달은 경험을 기록한다.'],
 'xianzhou/2': ['borisin',
                'outgoing',
                '편집자의 연결',
                '군 교재의 보리인 사냥단 기록',
                '군 교재는 보리인 사냥단별 특성과 단륜사 승려를 보호하는 군무부의 지침을 소개한다.'],
 'immortality/0': ['xianzhou',
                   'outgoing',
                   '편집자의 연결',
                   '영생 이후 선주의 인구·권력 변화',
                   '단정사 논문은 선주 사람들이 무한한 수명을 얻은 뒤의 인구·권력 변화를 기록한다.'],
 'immortality/1': ['jingliu',
                   'outgoing',
                   '편집자의 연결',
                   '경류의 마각의 몸과 역적 신분',
                   '경류의 인물 소개는 나부 검술의 일인자였던 그녀가 마각의 몸의 경계를 걷는 역적이 되었다고 설명한다.'],
 'jingliu/0': ['xianzhou',
               'outgoing',
               '원문 서술',
               '나부 검술의 일인자에서 역적으로',
               '인물 소개는 경류가 나부 검술의 일인자로 운기군을 이끌었으며 이후 이름이 지워졌다고 기록한다.'],
 'jingliu/1': ['immortality',
               'outgoing',
               '편집자의 연결',
               '악몽의 재현과 신체 붕괴 기록',
               '경류의 개인 이야기는 과거의 공포가 되돌아오는 악몽과 몸의 붕괴를 기록한다.'],
 'borisin/0': ['xianzhou',
               'outgoing',
               '편집자의 연결',
               '사냥단별 특성과 단륜사 보호 지침',
               '군 교재는 사냥단의 특성을 설명하며 군무부가 단륜사 승려를 고의로 해치는 일을 금지한다고 기록한다.'],
 'borisin/1': ['paths',
               'outgoing',
               '편집자의 연결',
               '단륜사의 비살생 신조와 파벌의 신앙',
               '군 교재는 단륜사의 구원 신앙과 비살생 신조를 소개한다. 운명의 길과 파벌의 자료에는 다른 집단의 신앙·활동이 수록되어 있다.'],
 'penacony/0': ['memory',
                'outgoing',
                '편집자의 연결',
                '기억 물질·기억 영역·기억 밈의 정의',
                '용어 기록은 기억 물질을 기억과 의식의 재료로, 기억 영역을 그 물질이 응집한 공간으로 설명한다.'],
 'penacony/1': ['watchmaker',
                'outgoing',
                '편집자의 연결',
                '가족이 남긴 시계공 조사 기록',
                '가족의 조사자는 시계공 목격담의 체형·외모·성별이 일치하지 않았다고 적었다.'],
 'memory/0': ['penacony',
              'outgoing',
              '편집자의 연결',
              '박물관 기록의 변조와 복구 사건',
              '가족의 사건 보고는 클락 스튜디오 전시실의 기록이 변조되었으며 밤꾀꼬리 가문과 기억의 정원 주재원이 복구했다고 기록한다.'],
 'memory/1': ['paths',
              'outgoing',
              '편집자의 연결',
              '기억의 정원과 소각공의 보존 방식',
              '파벌 아카이브는 소각공이 가치 없다고 판단한 기억을 태우며 기억의 정원이 그 판단 권한을 비웃는다고 설명한다.'],
 'watchmaker/0': ['penacony',
                  'outgoing',
                  '편집자의 연결',
                  '페나코니 발전과 이익 침해에 관한 가족의 평가',
                  '가족의 조사자는 시계공의 페나코니 발전 공헌을 인정하면서 가족의 이익을 침해했다고 평가한다.'],
 'watchmaker/1': ['paths', 'outgoing', '편집자의 연결', '시계공의 무명객 신분 기록', '시계공의 용어 기록은 레그워크·샤르·미하일을 과거의 무명객으로 소개한다.'],
 'herta/0': ['ruan-mei',
             'outgoing',
             '편집자의 연결',
             '완·매의 시뮬레이션 우주 공동 개발 기록',
             '완·매의 인물 소개는 헤르타의 초청으로 스크루룸·스티븐과 시뮬레이션 우주를 개발했다고 기록한다.'],
 'herta/1': ['life', 'outgoing', '편집자의 연결', '창조물의 소멸과 감정 연구 기록', '실험 일지는 성공으로 판정된 창조물이 56초 후 소멸했다고 기록한다.'],
 'ruan-mei/0': ['person-1013',
                'incoming',
                '원문 서술',
                '시뮬레이션 우주 공동 개발에 초청했다',
                '완·매의 인물 소개는 헤르타의 초청을 받아 스크루룸·스티븐과 시뮬레이션 우주를 개발했다고 기록한다.'],
 'ruan-mei/1': ['life',
                'outgoing',
                '원문 서술',
                '감정 논문에 이해의 어려움을 메모한다',
                '완·매는 감정 논문 말미에 공감하기도 이해하기도 어렵다며 저자를 직접 만나 묻고 싶다고 메모했다.'],
 'life/0': ['ruan-mei', 'outgoing', '편집자의 연결', '완·매의 부모에 관한 기억과 연구 기록', '완·매의 개인 이야기는 부모를 잃은 뒤 과학에 기댄 기억을 기록한다.'],
 'life/1': ['amphoreus',
            'outgoing',
            '편집자의 비교',
            '생명 실험과 나무 정원의 연구 안전 심사',
            '나무 정원 역사 문헌은 누스페르마타 학파의 현인이 실험·연구의 안전 심사를 맡는다고 설명한다.'],
 'life/2': ['natasha',
            'outgoing',
            '편집자의 비교',
            '생명 실험과 나타샤의 하층 의료 활동',
            '나타샤는 편지에서 봉쇄 소식을 전하면서 하층 주민들을 포기할 수 없다고 썼다.'],
 'amphoreus/0': ['titans',
                 'outgoing',
                 '원문 서술',
                 '대표 티탄의 달에 계약과 농사를 배치한다',
                 '역법은 균형의 달을 판결·계약에 적합한 시기로, 경작의 달을 농사에 적합한 시기로 기록한다.'],
 'amphoreus/1': ['life',
                 'outgoing',
                 '편집자의 연결',
                 '나무 정원의 실험·연구 안전 심사',
                 '나무 정원 역사 문헌은 누스페르마타 학파의 현인이 탐구가 정원의 안전을 위협하지 않도록 연구를 심사한다고 설명한다.'],
 'titans/0': ['amphoreus',
              'outgoing',
              '원문 서술',
              '대표 티탄의 달이 계약과 농사의 기준이 된다',
              '앰포리어스의 역법은 달마다 대표 티탄과 생산·의례 활동을 정한다.'],
 'titans/1': ['paths',
              'outgoing',
              '편집자의 비교',
              '티탄 신앙의 학파 논쟁과 파벌의 신앙',
              '나무 정원 역사 문헌은 티탄에 대한 경외와 지식 추구를 둘러싼 학파들의 논쟁을 기록한다.'],
 'paths/0': ['preservation',
             'outgoing',
             '편집자의 연결',
             '클리포트가 관장하는 보존의 정의',
             '클리포트의 기록은 광년 단위로 장벽을 세워 생기가 남은 세계를 보호했다고 설명한다.'],
 'paths/1': ['memory',
             'outgoing',
             '편집자의 연결',
             '기억의 정원과 소각공의 보존 방식',
             '파벌 아카이브는 소각공의 기억 소각과 이를 비판하는 기억의 정원의 평가를 함께 소개한다.'],
 'seele/0': ['belobog', 'outgoing', '원문 서술', '와일드 파이어 멤버로 하층에서 자랐다', '제레는 지하의 위험하고 혼란스러운 환경에서 자란 와일드 파이어 멤버다.'],
 'seele/1': ['bronya', 'outgoing', '원문 서술', '축제에서 미소를 나눈다', '제레는 소매치기범을 철위대에 인계한 뒤 무대 위 수호자와 미소를 나눈다.'],
 'natasha/0': ['belobog',
               'outgoing',
               '원문 서술',
               '봉쇄 앞에서 하층에 남겠다고 쓴다',
               '나타샤는 편지에서 상층과 하층의 봉쇄 소식을 전하고 하층 주민들을 포기할 수 없다고 썼다.'],
 'natasha/1': ['life',
               'outgoing',
               '편집자의 비교',
               '하층 주민의 돌봄과 완·매의 생명 실험',
               '나타샤의 편지는 하층 주민을 위한 의료 활동을 이어가겠다는 뜻을 담고 있다.'],
 'antimatter-legion/0': ['aeon-aeon-6', 'outgoing', '원문 서술', '나누크의 군대', '도움말은 반물질군단을 나누크의 군대로 정의한다.'],
 'antimatter-legion/1': ['lore-10003',
                         'outgoing',
                         '편집자의 연결',
                         '나누크가 관장하는 파멸의 정의',
                         '파멸의 도움말은 나누크가 그 운명의 길을 관장한다고 설명한다. 군단의 도움말도 나누크를 군대의 주체로 명시한다.'],
 'sanctus-medicus/0': ['xianzhou',
                       'outgoing',
                       '원문 서술',
                       '나부 전복을 도모한다',
                       '도움말은 약왕의 비전이 옛 선인의 기적으로 추종자를 모아 나부 선주를 전복시키려 한다고 설명한다.'],
 'sanctus-medicus/1': ['lore-10054',
                       'outgoing',
                       '편집자의 연결',
                       '풍요의 백성의 축복·육체 설명',
                       '풍요의 백성 도움말은 풍요의 축복을 받은 사람들이 죽지 않는 육체를 누리며 약사의 인자함을 칭송한다고 설명한다.'],
 'stellaron-hunters/0': ['person-1005',
                         'incoming',
                         '원문 서술',
                         '멤버로 소개된다',
                         '카프카의 인물 소개는 그녀를 스텔라론 헌터이자 엘리오가 가장 신뢰하는 멤버 중 하나로 설명한다.'],
 'stellaron-hunters/1': ['xianzhou',
                         'outgoing',
                         '카프카의 발언',
                         '열차를 나부로 인도했다고 말한다',
                         '카프카는 스텔라론 헌터의 나부 방문과 자신의 궁관진 출석이 은하열차를 선주로 인도하기 위한 것이라고 말한다.'],
 'stellaron-hunters/2': ['antimatter-legion',
                         'outgoing',
                         '편집자의 연결',
                         '카프카의 나누크 예고와 군단의 정의',
                         '카프카는 미래의 열차가 나누크와 직면할 것이라고 예고한다. 반물질군단은 별도의 용어 기록에서 나누크의 군대로 정의된다.'],
 'stellaron/0': ['lore-10071',
                 'outgoing',
                 '원문 서술',
                 '열계가 함께 나타난다',
                 '열계의 도움말은 스텔라론과 함께 나타나는 공간 왜곡이 현실을 갉아먹는다고 설명한다.'],
 'stellaron/1': ['stellaron-hunters',
                 'outgoing',
                 '편집자의 연결',
                 '은랑의 봉인 해제와 스텔라론 수용체 계획',
                 '우주정거장 퀘스트는 은랑이 봉인을 해제하면 스텔라론을 준비된 수용체에 넣어야 한다고 서술한다.'],
 'ipc/0': ['aeon-aeon-1', 'outgoing', '원문 서술', '지원하기 위해 설립된다', '스타피스 컴퍼니의 설립 목적은 클리포트 지원으로 소개된다.'],
 'masked-fools/0': ['aeon-aeon-7', 'outgoing', '원문 서술', '숭배한다', '가면의 우인은 아하의 숭배자로 소개된다.'],
 'galaxy-rangers/0': ['lore-10222',
                      'outgoing',
                      '원문 서술',
                      '원한을 맺는다',
                      '원시 박사의 용어 기록은 회귀 실험의 악행으로 갤럭시 레인저와 악연을 맺었다고 설명한다.'],
 'swarm/0': ['aeon-aeon-8', 'outgoing', '원문 서술', '복제 군단', '곤충떼는 타이츠론스의 복제 군단으로 기록된다.'],
 'genius-society/0': ['lore-10222', 'incoming', '원문 서술', '64번 회원이다', '원시 박사는 지니어스 클럽 64번 회원으로 소개된다.'],
 'genius-society/1': ['aeon-aeon-9', 'outgoing', '원문 서술', '주목을 받는다', '지니어스 클럽의 도움말은 구성원을 누스의 주목을 받은 사람들로 설명한다.'],
 'swarm-research/0': ['swarm',
                      'outgoing',
                      '편집자의 연결',
                      '타이츠론스 몰락 전 시대의 연산과 곤충떼의 정의',
                      '헤르타는 완·매가 타이츠론스의 몰락 전 시대로 연산을 고정하려 한다고 말한다.'],
 'swarm-research/1': ['ruan-mei',
                      'incoming',
                      '헤르타의 발언',
                      '타이츠론스 몰락 전 시대를 선택했다',
                      '헤르타는 완·매가 타이츠론스의 몰락 전 시대를 선택했다고 설명한다.'],
 'swarm-research/2': ['person-1013',
                      'incoming',
                      '헤르타의 발언',
                      '연산의 누락 가능성을 지적한다',
                      '헤르타는 시뮬레이션 우주의 연산에 무언가 빠져 있을 가능성을 제기한다.'],
 'rupert-research/0': ['genius-society',
                       'outgoing',
                       '편집자의 연결',
                       '클럽 회원 #27 루버트와 제1차 제왕 전쟁',
                       '헤르타는 클럽 회원 #27 루버트를 제1차 제왕 전쟁을 일으킨 인물로 소개한다.'],
 'rupert-research/1': ['ipc',
                       'outgoing',
                       '편집자의 연결',
                       '루버트 사망설에 등장하는 컴퍼니',
                       '헤르타는 루버트가 컴퍼니의 자객에게 죽었다는 이야기와 적막의 영주에게 파괴됐다는 이야기를 제시한다.'],
 'rupert-research/2': ['life',
                       'outgoing',
                       '편집자의 연결',
                       '컴퍼니의 기계 생명체 멸종 계획 기록',
                       '기계식 뻐꾸기 시계의 배경은 컴퍼니가 기계 생명체의 멸종 계획을 세웠으며 그 계획이 통과되기 전에 스크루룸의 클럽 가입 소식을 들었다고 기록한다.'],
 'unknowable-research/0': ['rupert-research',
                           'outgoing',
                           '편집자의 연결',
                           '제왕 전쟁 이후 학파 전쟁과 앞선 제왕 전쟁 연구',
                           '스크루룸은 캔들 학파 자료에 따라 공동의 역사를 제2차 제왕 전쟁 이후 학파 전쟁에 연결한다.'],
 'unknowable-research/1': ['person-1013',
                           'incoming',
                           '헤르타의 발언',
                           '셉터 재현을 연구 목적으로 설명한다',
                           '헤르타는 학파 전쟁의 데이터를 모아 시뮬레이션 우주에서 셉터 시스템을 모조하려 한다고 설명한다.'],
 'unknowable-research/2': ['life',
                           'outgoing',
                           '편집자의 연결',
                           '루버트 2세의 무덤과 반유기 방정식 기록',
                           '스크루룸은 루버트 2세의 무덤과 꽃다발이 반유기 방정식과 제왕에 관한 기존 인식을 깨뜨렸다고 말한다.']}
# Original-context review fixtures: interpretation is checked independently from generated HTML.
REVIEWED_TIMING = {'belobog': {'timeNote': '「벨로보그 주요 사건 일대기·한파 직전」에 기록된 근사 연대다. 철위대 보고서와 하층 전단지의 작성일은 미상이다.',
             'timeline': [{'when': '축성 기원 전 30년 전후',
                           'title': '스텔라론 추락과 피난소 건설',
                           'text': '공식 연대기는 스텔라론의 추락과 종말론의 확산, 알리사·랜드가 지휘한 피난소 건설을 기록한다.'},
                          {'when': '축성 기원 전 20년 전후',
                           'title': '군단 침공과 벨로보그 수호 전쟁',
                           'text': '공식 연대기는 반물질군단이 야릴로-VI을 침공했으며 준공 전의 벨로보그에서 수호 전쟁이 시작되었다고 기록한다.'},
                          {'when': '축성 기원 원년 전후',
                           'title': '도시 준공과 빙하기, 수호자 칭호',
                           'text': '공식 연대기는 벨로보그의 준공과 야릴로-VI의 빙하기 진입을 기록한다. 백성들은 알리사·랜드에게 수호자 칭호를 부여했다.'}]},
 'bronya': {'timeNote': '인물 이야기의 어린 시절·장례식과 인물 소개의 하층 방문 기록이다. 장례식과 하층 방문의 정확한 선후·시간 간격은 미상이다.',
            'timeline': [{'when': '어린 시절의 기억',
                          'title': '더 아름다운 세상을 만들겠다는 약속',
                          'text': '브로냐는 돌담길을 걸으며 노동자들의 삶을 보고 더 아름다운 세상을 만들겠다고 말한다.'},
                         {'when': '첫 출전 뒤 장례식',
                          'title': '첫 출전에서 희생한 전우의 장례식',
                          'text': '브로냐는 자신을 보호하다 희생된 전우의 장례식에서 대신 그 공격을 맞고 싶었다고 말한다.'},
                         {'when': '하층을 본 뒤의 의문',
                          'title': '하층 방문 뒤 훈련의 목적에 관한 의문',
                          'text': '인물 소개는 하층의 열악한 환경을 본 브로냐가 자신의 훈련이 시민들을 원하는 삶으로 이끌 수 있는지 의문을 품었다고 기록한다.'}]},
 'preservation': {'timeNote': '', 'timeline': []},
 'xianzhou': {'timeNote': '단정사 논문과 선주 신앙사에 기록된 시대다. 신앙사의 신앙 위기는 성력 3400~4000년으로 명시되어 있다.',
              'timeline': [{'when': '불멸의 거목 이후',
                            'title': '불멸의 거목 이후 무한한 수명',
                            'text': '단정사 논문은 불멸의 거목이 나타난 뒤 선주 사람들이 무한한 수명을 얻었다고 기록한다.'},
                           {'when': '공겁의 난 이후',
                            'title': '마각의 몸과 약사 신앙의 위기',
                            'text': '신앙사의 저자는 마각의 몸이 선주 사람들의 약사에 대한 믿음을 흔들었다고 설명한다.'},
                           {'when': '성력 3400~4000년의 신앙 위기',
                            'title': '성력 3400~4000년의 여러 신앙',
                            'text': '신앙사는 이 시기의 보천파·구 약왕의 비전·변지파를 소개한다.'}]},
 'immortality': {'timeNote': '', 'timeline': []},
 'jingliu': {'timeNote': '인물 이야기 2~5에 기록된 사건이다. 장인·용존·제자는 이 인용 구간에서 직함으로 등장한다.',
             'timeline': [{'when': '구출된 아이',
                           'title': '구출 뒤 첫 검술 수업',
                           'text': '구출된 소녀는 병실을 나온 날 처음 검을 만지고 혈안의 애자 10마리를 처치하라는 수업을 받는다.'},
                          {'when': '검술을 익히는 전장',
                           'title': '전장에서 부러진 검과 스승의 가르침',
                           'text': '경류는 용백과 싸우다 검이 부러지고 죽음의 위기에 놓인다. 무장한 여자는 운기군이 직접 검을 들고 싸워야 한다고 말한다.'},
                          {'when': '검술의 일인자와 친구들',
                           'title': '검을 자신의 표현 방식으로 설명한다',
                           'text': '경류는 제자에게 자신을 표현하는 방식이 많지만 자신에게는 검뿐이라고 말한다.'},
                          {'when': '지기에게 향한 검',
                           'title': '악룡과의 싸움에서 되돌아온 악몽',
                           'text': '경류는 악룡에게 맞서며 어린 시절의 악몽을 다시 경험하고 몸이 극한을 넘어 붕괴되는 감각을 느낀다.'}]},
 'borisin': {'timeNote': '', 'timeline': []},
 'penacony': {'timeNote': '「기밀: 꿈세계 대형 사건 기록」이 전한 박물관 습격·복구·재개관 과정이다. 복구에는 10 시스템 시간 이내가 소요되었다.',
              'timeline': [{'when': '박물관 습격',
                            'title': '박물관 전시 기록의 변조',
                            'text': '가족의 사건 보고는 허구 역사학자의 습격 뒤 꿈 건축·가문 인물·역사 설명을 포함한 전시 기록이 변조되었다고 기록한다.'},
                           {'when': '수정과 복구',
                            'title': '밤꾀꼬리 가문과 기억의 정원 주재원의 복구',
                            'text': '가족의 사건 보고는 밤꾀꼬리 가문이 기억의 정원의 페나코니 주재원과 박물관 내용을 수정했다고 기록한다.'},
                           {'when': '10 시스템 시간 내',
                            'title': '10 시스템 시간 이내의 재개관',
                            'text': '가족의 사건 보고는 10 시스템 시간 내에 복구가 완료되어 박물관을 다시 개관했다고 기록한다.'}]},
 'memory': {'timeNote': '', 'timeline': []},
 'watchmaker': {'timeNote': '', 'timeline': []},
 'herta': {'timeNote': '', 'timeline': []},
 'ruan-mei': {'timeNote': '인물 이야기 2~5에 수록된 생애 사건이다. 실험 일지는 별도의 실험 번호를 사용하며 각 실험의 날짜는 미상이다.',
              'timeline': [{'when': '어린 시절',
                            'title': '어머니와 함께한 생명 연구',
                            'text': '어머니와 생명을 관찰한 뒤 디저트를 보상으로 받았으며 연구 비행선으로 여러 세계를 방문했다.'},
                           {'when': '부모의 장례 뒤',
                            'title': '부모의 장례와 데이터로 만든 부모의 모습',
                            'text': '완·매는 부모의 장례 뒤 과학만이 기대를 저버리지 않는다고 말한다. 실험실에는 데이터 집합으로 만든 부모의 얼굴이 나타난다.'},
                           {'when': '누스의 눈길을 받은 뒤',
                            'title': '은둔 생활과 생명의 모조',
                            'text': '누스의 눈길을 받은 뒤 고향을 떠났다. 모조한 생명들은 사고·의식·감정을 키우려 했으나 그녀는 그들을 느낄 수 없었다고 기록된다.'},
                           {'when': '공동 연구의 자리',
                            'title': '동료들과의 공동 연구와 에이언즈 연구',
                            'text': '동료들과 애프터눈 티와 연구를 나누며 시뮬레이션 에이언즈에 관심을 가진다. 이야기는 그녀가 이 자리를 즐기고 있다고 기록한다.'}]},
 'life': {'timeNote': '', 'timeline': []},
 'amphoreus': {'timeNote': '', 'timeline': []},
 'titans': {'timeNote': '', 'timeline': []},
 'paths': {'timeNote': '', 'timeline': []},
 'seele': {'timeNote': '인물 이야기 2에 수록된 배급소와 진료소의 사건이다. 두 사건 사이의 간격은 3일로 명시되어 있다.',
           'timeline': [{'when': '물을 독차지한 밤',
                         'title': '배급소에서 물을 독차지한다',
                         'text': '제레는 물을 두고 노숙자와 싸웠으며 상대가 도망간 뒤 물을 독차지했다.'},
                        {'when': '3일 뒤',
                         'title': '3일 뒤 진료소에서 상대를 다시 만난다',
                         'text': '제레는 진료소에서 병상에 누운 상대를 보았다. 이후에는 다음 사람을 위해 물을 남겨두었다.'}]},
 'natasha': {'timeNote': '인물 이야기 3의 진로 선택과 이야기 4의 편지다. 편지는 봉쇄 계획을 소문으로 전하며 작성일은 미상이다.',
             'timeline': [{'when': '의대를 졸업할 무렵',
                           'title': '교수에게 하층으로 향할 뜻을 밝힌다',
                           'text': '나타샤는 도움이 더 필요한 사람들이 있는 하층 구역으로 가고 싶다고 교수에게 말한다.'},
                          {'when': '상·하층 봉쇄를 앞둔 편지',
                           'title': '봉쇄 소식을 전하며 하층에 남을 뜻을 밝힌다',
                           'text': '나타샤는 부모에게 봉쇄 계획의 소문을 전하면서 하층 주민들을 포기할 수 없다고 썼다.'}]},
 'antimatter-legion': {'timeNote': '', 'timeline': []},
 'sanctus-medicus': {'timeNote': '', 'timeline': []},
 'stellaron-hunters': {'timeNote': '', 'timeline': []},
 'stellaron': {'timeNote': '', 'timeline': []},
 'ipc': {'timeNote': '', 'timeline': []},
 'masked-fools': {'timeNote': '', 'timeline': []},
 'galaxy-rangers': {'timeNote': '', 'timeline': []},
 'swarm': {'timeNote': '', 'timeline': []},
 'genius-society': {'timeNote': '', 'timeline': []},
 'swarm-research': {'timeNote': '', 'timeline': []},
 'rupert-research': {'timeNote': '', 'timeline': []},
 'unknowable-research': {'timeNote': '', 'timeline': []}}
REVIEWED_COMPARISONS = {'belobog-preservation': {'title': '벨로보그의 생존, 철위대 지휘, 하층의 의료',
                          'scope': '공식 연대기·철위대 보고서·하층 전단지',
                          'same': '세 자료는 벨로보그에서 도시·군대·주민을 보호하는 활동을 기록한다.',
                          'different': '연대기는 도시의 생존과 수호자 칭호를, 보고서는 병력과 지휘권을, 전단지는 하층의 질서와 의료를 다룬다.',
                          'reading': '브로냐의 인물 소개에는 하층의 환경을 본 뒤 자신의 훈련이 시민들을 원하는 삶으로 이끌 수 있는지 의문을 품었다고 기록되어 있다.',
                          'panels': ['공식 연대기는 한파 속에서 벨로보그를 지킨 알리사·랜드에게 백성들이 수호자 칭호를 부여했다고 기록한다.',
                                     '정보관은 병력 손실과 지휘 문제를 보고하며 실버메인 철위대의 지휘권을 되찾아 달라고 건의한다.',
                                     '와일드 파이어의 전단지는 주민들이 직접 질서를 지키고 의료 지원에 동참할 사람이 필요하다고 호소한다.']},
 'xianzhou-immortality': {'title': '구 약왕의 비전과 현대 약왕의 비전의 기록',
                          'scope': '선주 신앙사와 시왕사 판관의 반박문',
                          'same': '두 자료는 구 약왕의 비전과 현대의 조직을 구분해 설명한다.',
                          'different': '신앙사는 옛 집단의 의료 활동과 계승을, 시왕사 반박문은 현대 조직의 범죄와 행정 대응을 다룬다.',
                          'reading': '신앙사에는 가난한 사람들을 치료한 옛 집단의 기록이, 시왕사 문서에는 현대 조직을 범죄 조직으로 규정한 판관의 설명이 수록되어 있다.',
                          'panels': ['신앙사의 저자는 구 약왕의 비전이 의심을 받아들이고 의원을 열어 가난한 사람들을 도왔다고 설명한다.',
                                     '시왕사 판관은 현대 약왕의 비전을 옛 이름을 쓰는 설립 30년 미만의 범죄 조직으로 규정한다.']},
 'borisin-and-foxians': {'title': '보리인 사냥단의 전술과 단륜사 보호, 종광의 문화 고찰',
                         'scope': '신입 병사용 군 교재와 종광의 문화 고찰',
                         'same': '군 교재와 문화 고찰은 보리인 사회의 집단과 능력 평가에 관한 정보를 담고 있다.',
                         'different': '군 교재는 사냥단별 대응책과 단륜사 승려 보호를, 종광의 글은 보리인의 문화와 선주 학자 가문의 제도를 다룬다.',
                         'reading': '교재에는 여우족이 이끄는 백랑과 비살생 신조를 지키는 단륜사가 등장한다. 종광은 전투·기술·시 등 여러 능력을 평가하는 질서를 소개한다.',
                         'panels': ['군 교재는 백랑이 여우족이 이끄는 사냥단이며 선주 여우족으로 위장해 병사들을 속이는 전술을 쓴다고 설명한다.',
                                    '종광은 보리인의 능력 평가 문화를 선주 학자 가문의 제도와 비교하며 배울 기회가 있다고 주장한다.',
                                    '군 교재는 단륜사 승려를 고의로 해치면 민간인 살상으로 처벌받는다고 명시한다.']},
 'penacony-memory': {'title': '시계공 목격담과 레그워크·샤르·미하일의 이름',
                     'scope': '가족의 조사 기록과 시계공 용어 기록 · 작성 시점의 선후 미상 · 정체 스포일러',
                     'same': '두 자료는 페나코니의 시계공을 다룬다.',
                     'different': '가족의 문서는 조사자의 관측과 배후 세력에 관한 가설을, 용어 기록은 이름과 과거의 신분을 제시한다.',
                     'reading': '가족의 조사서는 시계공의 발전 공헌을 인정하면서 가족의 이익 침해를 평가한다. 용어 기록에는 시계공의 이름과 무명객 신분이 명시되어 있다.',
                     'panels': ['가족의 조사자는 목격담의 체형·외모·성별이 일치하지 않는다고 적고 신비 관련 세력의 지원 가능성을 추측한다.',
                                '용어 기록은 시계공을 레그워크·샤르·미하일이라는 과거의 무명객으로 소개한다.']},
 'herta-life-and-knowledge': {'title': '창조물의 소멸 기록과 감정 논문, 완·매의 메모',
                              'scope': '완·매의 실험 일지와 감정의 본질 논문',
                              'same': '실험 일지와 논문에는 생명체의 감정이 등장한다.',
                              'different': '일지는 실험 결과와 실패 원인을, 논문은 감정에 관한 저자의 결론을, 메모는 그 결론에 대한 완·매의 반응을 담는다.',
                              'reading': '일지는 큰 슬픔을 실험 실패의 원인으로 기록한다. 논문의 공통 언어라는 결론 뒤에는 완·매가 남긴 공감과 이해에 관한 메모가 '
                                         '있다.',
                              'panels': ['완·매의 일지는 분산형 생명체가 123초 후 소멸했으며 감정 탐측기로 큰 슬픔이 전해졌다고 기록한다.',
                                         '논문 저자는 기계 생명체의 경험을 서술하고 감정이 생명의 공통 언어라는 결론을 제시한다.',
                                         '완·매는 논문 말미에 공감하기도 이해하기도 어렵다며 저자를 직접 만나 묻고 싶다고 메모한다.']},
 'amphoreus-myth-and-life': {'title': '대표 티탄의 달과 나무 정원의 일곱 현인 제도',
                             'scope': '앰포리어스 역법과 나무 정원 역사 문헌',
                             'same': '두 자료에는 티탄 신앙과 관련된 생활·제도가 수록되어 있다.',
                             'different': '역법은 월별 생산과 의례를, 의정서는 일곱 학파의 관리 업무와 의사 결정 절차를 설명한다.',
                             'reading': '나무 정원의 현인들은 연구 심사·건강 관리·숲 관리·자료 보존·의식·단련·예술 교육을 나누어 맡는다.',
                             'panels': ['역법은 대표 티탄의 달에 농사·제물·계약·판결 등의 활동을 배치한다.',
                                        '역사 문헌은 티탄에 대한 경외와 지식 추구를 둘러싼 논쟁 뒤 일곱 학파의 독립과 상호 견제를 위한 현인 제도가 도입되었다고 '
                                        '기록한다.']},
 'paths-and-factions': {'title': '기억의 정원의 보존과 소각공의 소각',
                        'scope': '파벌 아카이브의 소각공 항목',
                        'same': '두 파벌은 후리와 기억을 중심으로 설명된다.',
                        'different': '기억의 정원은 모든 조각의 존재 이유를 말하고, 소각공은 가치 없다고 판단한 기억을 없앤다.',
                        'reading': '파벌 아카이브는 소각공의 선별·소각과 이를 비판하는 기억의 정원의 견해를 같은 항목에 기록한다.',
                        'panels': ['기억의 정원은 모든 우주의 조각에 존재 이유가 있다며 소각공에게 기억의 가치를 판단할 권리가 없다고 비판한다.',
                                   '소각공은 후리의 부담을 덜어준다는 이유로 쓸모없다고 판단한 기억을 소각한다고 소개된다.']}}
INCOMING = {('swarm-research', 1): ('ruan-mei', '완•매', '헤르타'),
            ('swarm-research', 2): ('person-1013', '아마도라고 정정해야겠어', '헤르타'),
            ('unknowable-research', 1): ('person-1013', '제왕의 외장 사고 유닛을 재현', '헤르타'),
            ('ruan-mei', 0): ('person-1013', '헤르타의 초청을 받아', None),
            ('stellaron-hunters', 0): ('person-1005', '이 스텔라론 헌터', None),
            ('genius-society', 0): ('lore-10222', '「지니어스 클럽」 #64', None)}


def require(value, label):
    if not value:
        raise ValueError(label)


def read(path):
    return json.loads(path.read_text('utf8'))


def verify(site=SITE, atlas=None, graph=None, sources_only=False):
    atlas = atlas or read(site / 'editorial/context-atlas.json')
    manifests = {}
    for name in ('dataset/manifest.json', 'dataset-extra/manifest.json'):
        for item in read(site / name)['files']:
            key = item['path']
            require(key not in manifests or manifests[key] == item['sha256'], 'Conflicting preserved source SHA')
            manifests[key] = item['sha256']
    docs, cited_rows = {}, []

    def evidence(e):
        ident = e.get('id', e.get('docId'))
        if ident not in docs:
            path = site / 'data/documents' / (ident + '.json')
            relative = path.relative_to(site).as_posix()
            require(relative in manifests and hashlib.sha256(path.read_bytes()).hexdigest() == manifests[relative],
                    'Original source SHA differs: ' + ident)
            docs[ident] = read(path)
        matches = [r for s in docs[ident]['sections'] if s['anchor'] == e['anchor'] for r in s['rows']
                   if ('hash' not in e or str(r.get('hash')) == str(e['hash']))
                   and (e.get('talkId') is None or r.get('talk_id') == e['talkId'])
                   and e['quote'] in r.get('text', '')]
        require(len(matches) == 1, 'Original quote/anchor/hash/TalkID differs: ' + ident)
        cited_rows.append((ident, e, matches[0]))
        return matches[0]

    if not sources_only:
        graph = graph or read(site / 'public/reading-data/graph.json')
        relations = {r['id']: r for r in graph['relations']}
        require(len(relations) == len(graph['relations']), 'Duplicate relation ID')
        claims = {c['id']: c for c in graph['claims']}
        proof = {e['id']: e for e in graph['evidence']}
    all_ids, count, topology_edges, events, comparisons = set(), 0, 0, 0, 0
    incoming = set()
    for node in atlas['nodes']:
        require(node['id'] not in all_ids, 'Duplicate context entity')
        all_ids.add(node['id'])
        timing = {'timeNote': node.get('timeNote', ''), 'timeline': [{k: e[k] for k in ('when', 'title', 'text')} for e in node.get('timeline', [])]}
        require(timing == REVIEWED_TIMING.get(node['id']), 'Original timing scope or event meaning differs: ' + node['id'])
        for e in node['evidence']:
            evidence(e)
        for index, relation in enumerate(node['links']):
            key = (node['id'], index)
            decision = REVIEWED.get(node['id'] + '/' + str(index))
            require(decision is not None and [relation.get(k) for k in ('target', 'direction', 'status', 'verb', 'why')] == decision,
                    'Actor/direction/setting-versus-editorial meaning differs from reviewed original context: ' + str(key))
            direction = relation.get('direction')
            require(direction in ('incoming', 'outgoing'), 'Explicit reviewed direction required')
            require((direction == 'incoming') == (key in INCOMING), 'Relation direction differs from semantic review: ' + str(key))
            require(relation['target'] != node['id'] and relation['verb'].strip(), 'Invalid relation endpoints/predicate')
            original = evidence(relation['evidence'])
            if key == ('sanctus-medicus', 1):
                require(relation['target'] == 'lore-10054' and relation['status'] == '편집자의 연결' and
                        relation['verb'] == '풍요의 백성의 축복·육체 설명', 'Related definition promoted to inferred membership')
            if key in INCOMING:
                target, original_needle, speaker = INCOMING[key]
                require(relation['target'] == target and (speaker is None or original.get('speaker') == speaker) and
                        original_needle in original['text'], 'Incoming actor proof differs')
                incoming.add(key)
            if not sources_only:
                ident = 'atlas/' + node['id'] + '/relation-' + str(index)
                require(ident in relations, 'Missing generated relation')
                r = relations[ident]
                left, right = (relation['target'], node['id']) if direction == 'incoming' else (node['id'], relation['target'])
                require((r['from'], r['to'], r['label']) == (left, right, relation['verb']), 'Generated actor/predicate/target differs: ' + ident)
                claim = claims[r['reasonClaimId']]
                require(claim['text'] == relation['why'], 'Relation reason changed')
                expected_kind = 'inference' if '편집' in relation.get('status', '') else ('attributed' if
                    relation['evidence'].get('speaker') or relation['evidence'].get('status') != '원문 서술' else 'explicit')
                require(claim['kind'] == expected_kind, 'Relation fact/claim/interpretation differs')
                evs = [proof[e] for e in claim['evidenceIds']]
                require(len(evs) == 1 and evs[0]['sourceId'] == relation['evidence']['id'] and
                        evs[0]['quote'] == relation['evidence']['quote'] and
                        evs[0]['sourceSha256'] == hashlib.sha256(original['text'].encode()).hexdigest(), 'Relation cited original differs')
            count += 1
        for event in node.get('timeline', []):
            evidence(event['evidence'])
            events += 1
        for edge in (node.get('topology') or {}).get('edges', []):
            for e in edge['evidence']:
                evidence(e)
            topology_edges += 1
    require(incoming == set(INCOMING), 'Reviewed incoming relation missing')
    require(count == len(REVIEWED), 'Full reviewed relation coverage differs')
    if not sources_only:
        require(count == len(graph['relations']), 'Unreviewed generated relation')
    require(set(atlas['comparisons']) == set(REVIEWED_COMPARISONS), 'Reviewed comparison coverage differs')
    for comparison_id, comparison in atlas['comparisons'].items():
        meaning = {**{k: comparison[k] for k in ('title', 'scope', 'same', 'different', 'reading')}, 'panels': [p['text'] for p in comparison['panels']]}
        require(meaning == REVIEWED_COMPARISONS[comparison_id], 'Comparison meaning differs from original-context review: ' + comparison_id)
        for panel in comparison['panels']:
            evidence(panel['evidence'])
            comparisons += 1
    universe = read(site / 'data/universe-reading-clusters.json')
    panels = 0
    for cluster in universe['clusters']:
        for panel in cluster['panels']:
            for e in panel['evidence']:
                evidence(e)
            panels += 1
    return {'nodes': len(all_ids), 'relations': count, 'incomingRelations': len(incoming), 'editorialConnections': sum('편집' in r['status'] for n in atlas['nodes'] for r in n['links']),
            'topologyEdges': topology_edges, 'timelineEvents': events, 'comparisonPanels': comparisons,
            'universeClusters': len(universe['clusters']), 'universePanels': panels,
            'originalReferences': len(cited_rows), 'originalDocuments': len(docs), 'generatedGraphChecked': not sources_only}


def self_test(site, sources_only):
    atlas = read(site / 'editorial/context-atlas.json')
    rejected = []
    for label, mutate in [
        ('INCOMING_REVERSED', lambda a: next(n for n in a['nodes'] if n['id'] == 'swarm-research')['links'][1].update(direction='outgoing')),
        ('OUTGOING_REVERSED', lambda a: a['nodes'][0]['links'][0].update(direction='incoming')),
        ('UNKNOWN_DIRECTION', lambda a: a['nodes'][0]['links'][0].update(direction='sideways')),
        ('WRONG_CITED_HASH', lambda a: a['nodes'][0]['links'][0]['evidence'].update(hash='1')),
        ('WRONG_QUOTE', lambda a: a['nodes'][0]['links'][0]['evidence'].update(quote='invented quotation')),
        ('WRONG_ACTOR', lambda a: next(n for n in a['nodes'] if n['id'] == 'swarm-research')['links'][1].update(target='bronya')),
        ('STATION_AS_PERSONAL_INVITER', lambda a: next(n for n in a['nodes'] if n['id'] == 'ruan-mei')['links'][0].update(target='herta')),
        ('READING_CONNECTION_AS_SETTING_FACT', lambda a: next(n for n in a['nodes'] if n['id'] == 'herta')['links'][0].update(status='원문 서술')),
        ('MEMBER_DIRECTION_REVERSED', lambda a: next(n for n in a['nodes'] if n['id'] == 'genius-society')['links'][0].update(direction='outgoing')),
        ('FORECAST_AS_ARMY_ACTION', lambda a: next(n for n in a['nodes'] if n['id'] == 'stellaron-hunters')['links'][2].update(status='카프카의 발언')),
        ('UNSUPPORTED_COMPARISON_HYPOTHESIS', lambda a: a['comparisons']['herta-life-and-knowledge'].update(reading='창조·측정·공감은 서로 다른 능력일 수 있다.')),
        ('TIMELINE_ARBITRARY_DATE', lambda a: next(n for n in a['nodes'] if n['id'] == 'ruan-mei')['timeline'][0].update(when='성력 4000년')),
        ('TIMELINE_ABSTRACT_EDITORIAL_META', lambda a: next(n for n in a['nodes'] if n['id'] == 'belobog')['timeline'][2].update(text='하나의 공식 서사 안에 겹친다.')),
        ('BLURRED_READING_PREDICATE', lambda a: next(n for n in a['nodes'] if n['id'] == 'herta')['links'][1].update(verb='실험 성과와 감정의 간격')),
        ('RELATED_DEFINITION_AS_MEMBERSHIP', lambda a: next(n for n in a['nodes'] if n['id'] == 'sanctus-medicus')['links'][1].update(status='원문 서술', verb='풍요의 축복을 받은 사람들'))]:
        edited = deepcopy(atlas)
        mutate(edited)
        try:
            verify(site, atlas=edited, sources_only=sources_only)
        except (ValueError, KeyError):
            rejected.append(label)
        else:
            raise ValueError('Accepted contaminated relation: ' + label)
    if not sources_only:
        graph = read(site / 'public/reading-data/graph.json')
        edited = deepcopy(graph)
        target = next(r for r in edited['relations'] if r['id'] == 'atlas/swarm-research/relation-1')
        target['from'], target['to'] = target['to'], target['from']
        try:
            verify(site, graph=edited)
        except ValueError:
            rejected.append('GENERATED_ACTOR_REVERSED')
        else:
            raise ValueError('Accepted reversed generated actor')
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=SITE)
    parser.add_argument('--sources-only', action='store_true', help='Do not check stale generated graph before regeneration')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    result = verify(args.site, sources_only=args.sources_only)
    result['mutationRejections'] = self_test(args.site, args.sources_only) if args.self_test else []
    print(json.dumps({'status': 'PASS', **result}, ensure_ascii=False))
