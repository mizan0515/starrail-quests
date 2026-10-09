"""Read-only native ownership, typed dialogue, actual choices and reader gate.

The independently replayed cohort has frozen identities. The original eighty-
two-source gate retains its original counts, seeds and mutation tests.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
from verify_timeline_mission_dialogue import artifact_check, html_check, iter_scenes, at, read, sha, same, require, Tree
from verify_official_mission_talks import row_check
from verify_official_universe_texts import safe

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'quest-4010146'
DS = 'Story/Discussion/Mission/4010146/DS401014600.json'
NPC = 'Config/Level/NPCDialogue/P10551/F10551001_G442/DialogueMain_F10551001_G442_N400001.json'
GROUP = 'Config/LevelOutput/SharedRuntimeGroup/Groups_P10551_F10551001/LevelGroup_P10551_F10551001_G442.json'
BASE = 'https://autopatchos.starrails.com/design_data/V4.6Live/output_16707949_49849fe93fe6_7e5dfd5e6cd1a8/client/Windows'
OPTIONS = [411460002, 411460004, 411460006, 411460011, 411460013, 411460022, 411460024, 411460026]
IDS = {411460000 + n for n in range(1, 29)}
POINTERS = ['/OnStartSequece/0/TaskList/2'] * 3 + ['/OnStartSequece/4/TaskList/2'] * 2 + ['/OnStartSequece/7/TaskList/2'] * 3
EVENTS = ['TalkSentence_' + str(n) for n in (411460003, 411460005, 411460007, 411460012, 411460014, 411460023, 411460025, 411460027)]
COHORT = {'missions': 1, 'scenes': 15, 'rows': 28, 'uniqueTalkIds': 28, 'spokenScenes': 12, 'spokenRows': 20, 'choiceScenes': 3, 'choiceRows': 8}
NATIVE_FACTS_SHA = 'e255a93f36d3a8668972f93e41b9d735cfd732a17cb31d64517d2e525f5c29f3'
MESSAGE_LINK_SHA = 'b7afc84ba9b50920dc84966fb85b24cd1bf67cb95d174ff7440da1b159dc2a66'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def spoken_projection(data):
    value = {**data, 'missions': {OWNER: [s for s in data['missions'][OWNER] if s['recordType'] == 'TIMELINE_DIALOGUE']}}
    value['counts'] = {'missions': 1, 'scenes': 12, 'rows': 20, 'uniqueTalkIds': 20}
    return value


def validate(data):
    safe(data)
    same(data['counts'], COHORT, 'native cohort')
    same(set(data['missions']), {OWNER}, 'native owner set')
    scenes = data['missions'][OWNER]
    same(len(scenes), 15, 'native scene coverage')
    rows = [r for s in scenes for r in s['rows']]
    same(len(rows), 28, 'native original occurrences')
    same({r['talk_id'] for r in rows}, IDS, 'native original ID coverage')
    official = data['evidence']['officialKorean']
    for scene in scenes:
        edges = scene['nativeOwnership']['edges']
        same(scene['ownership'], edges, 'native ownership binding')
        same(len(edges), 5, 'native ownership chain length')
        seed, graph, trigger, table, ds = edges
        same((seed['kind'], seed['source'], seed['pointer'], seed['value'], seed['missionId'], seed['canonicalMissionId']),
             ('EXPLICIT_NATIVE_MAIN_MISSION_ID', GROUP, '/OwnerMainMissionID', 4010146, 4010146, 4010146), 'explicit group owner')
        same((seed['sourceSha256'], seed['packOffset'], seed['packLength'], seed['fullFieldEOF'], seed['fieldSpan']),
             ('2ac90c1afc25d1428d4c0f34d6ba48e3afdad9f80d9fde3078f32bb95e9c96ce', 93002489, 237, 237,
              {'start': 64, 'end': 68, 'pointer': '/OwnerMainMissionID'}), 'actual native group span')
        same((graph['kind'], graph['source'], graph['pointer'], graph['target']),
             ('EXPLICIT_OWNED_NPC_DIALOG_GRAPH', GROUP, '/NPCList/0/Dialog/LevelGraph', NPC), 'owned NPC literal')
        same(graph['fieldSpan'], {'start': 135, 'end': 223, 'pointer': '/NPCList/0/Dialog/LevelGraph'}, 'actual NPC path span')
        same((trigger['kind'], trigger['source'], trigger['pointer'], trigger['PerformanceType'], trigger['PerformanceTypeLabel'], trigger['PerformanceID']),
             ('EXACT_NATIVE_TRIGGER_PERFORMANCE', NPC, '/OnStartSequece/0/TaskList/0', 3, 'D', 401014600), 'actual typed NPC trigger')
        same((trigger['sourceSha256'], trigger['packOffset'], trigger['packLength'], trigger['fullFieldEOF']),
             ('d7d939ae7f94ba23bec80cb57af1ac5ce478e4ef81f28941ed63083157087a8e', 77273735, 25, 25), 'actual NPC source')
        same((table['kind'], table['tableSource'], table['tableSha256'], table['rowPointer'], table['row']['PerformanceID'], table['row']['PerformancePath'], table['target']),
             ('EXPLICIT_PERFORMANCE_LOOKUP', 'ExcelOutput/PerformanceDS.json', '7866e4681ae08ef7d59c3412d4e040a381c220173d54115b3580a0c7517f6362', '/3230', 401014600, DS, DS), 'exact registered D table lookup')
        same(table['registeredShards'], ['PerformanceD', 'PerformanceDLD', 'PerformanceDS', 'PerformanceDSLD', 'PerformanceCG'], 'actual D table registration')
        same(table['sourceUrl'], 'https://github.com/DimbreathBot/TurnBasedGameData/blob/8b178dd48698e5e7b12f0cc319ddab149f2ffc5c/ExcelOutput/PerformanceDS.json', 'existing public table link')
        same((ds['kind'], ds['source'], ds['nameHash'], ds['sourceSha256'], ds['packOffset'], ds['packLength'], ds['fullFieldEOF']),
             ('EXACT_NATIVE_FULL_FIELD_SOURCE', DS, '14020069737093567675', '682331a95e9010ad0174ccc856280fabcc64925b26615eb0287fe4b03b8e32ac', 2703410, 1824, 1824), 'actual full-field DS source')
        for edge in (seed, trigger, ds):
            file = '4ce18f6be0e2b9093fb7832de6ddf6ef.bytes' if edge is ds else '904d542abb3940ea5972a4ad151697a8.bytes'
            digest = 'ff5136ecc6dc552e2f6b94e830e49322bc70f795dccbc0e1ad113e50cfd2a5dd' if edge is ds else 'fa5fe2f887c83f370945981cc4e5c38a8e263be1ab5fa0dadbaf037c99a8dcb6'
            same((edge['packFile'], edge['packSha256'], edge['sourceUrl']), (file, digest, BASE + '/' + file), 'actual official pack URL/hash')
        for row in scene['rows']:
            row_check(row, official)
            original = row['preservedSource']; path = ROOT / original['file']
            same(sha(path), original['sha256'], 'native preserved file hash')
            source = at(read(path), original['pointer'])
            for key in ('talk_id', 'text', 'hash', 'voice'):
                same(str(row[key]), str(source[key]), 'native preserved original ' + key)
            same(row['url'], '대사/' + path.stem + '.html#talk-' + str(row['talk_id']), 'native exact original CTA')
    spoken = spoken_projection(data)
    # Frozen from a separate raw-object/receipt comparison, including actual
    # TalkID bytes. A plausible-looking decimal PPtr or SHA is not sufficient.
    facts = [{'source': s['source'], 'timelineSource': s['timelineSource'], 'ownership': s['ownership'],
              'clips': [{'talk_id': r['talk_id'], 'timelineClip': r['timelineClip']} for r in s['rows']]}
             for s in spoken['missions'][OWNER]]
    same(fingerprint(facts), NATIVE_FACTS_SHA, 'independently replayed native source identities')
    artifact_check(spoken, ROOT, row_check, safe, expected_counts=spoken['counts'],
                   expected_conditions=0, expected_options=8, expected_repeats={}, owner_kind='EXPLICIT_NATIVE_MAIN_MISSION_ID')
    same({s['source'] for s in spoken['missions'][OWNER]},
         {'Story/Discussion/Mission/4010146/DS401014600' + str(n).zfill(2) + '.playable' for n in range(1, 13)}, 'exact native Timeline set')
    for scene in spoken['missions'][OWNER]:
        same((scene['timelineSource']['logicalJsonPath'], scene['timelineSource']['entrySha256'], scene['timelineSource']['entryBytes']),
             (DS, '682331a95e9010ad0174ccc856280fabcc64925b26615eb0287fe4b03b8e32ac', 1824), 'Timeline literal DS source')
        same((scene['triggerContext']['source'], scene['triggerContext']['sourceSha256'], scene['triggerContext']['performanceId']),
             (NPC, 'd7d939ae7f94ba23bec80cb57af1ac5ce478e4ef81f28941ed63083157087a8e', 401014600), 'Timeline native trigger')
    choices = [r for s in scenes if s['recordType'] == 'NATIVE_TIMELINE_CHOICES' for r in s['rows']]
    same([r['talk_id'] for r in choices], OPTIONS, 'actual typed option order')
    for index, row in enumerate(choices):
        require(row['label'] == '선택지', 'Typed option became speech')
        same(row['choiceSource'], {'taskPointer': POINTERS[index], 'optionIndex': [0,1,2,0,1,0,1,2][index], 'triggerCustomString': EVENTS[index]}, 'actual PlayOptionTalk field')
    for scene in scenes:
        if scene['recordType'] == 'NATIVE_TIMELINE_CHOICES':
            same((scene['source'], scene['sourceSha256'], scene['sourceUrl'], scene['optionTaskPointer']),
                 (DS, '682331a95e9010ad0174ccc856280fabcc64925b26615eb0287fe4b03b8e32ac', BASE + '/4ce18f6be0e2b9093fb7832de6ddf6ef.bytes', scene['rows'][0]['choiceSource']['taskPointer']), 'option source binding')
    same(set(data['relatedDocuments']), {OWNER}, 'native related-message owner')
    require(len(data['relatedDocuments'][OWNER]) == 1, 'Native message association count')
    link = data['relatedDocuments'][OWNER][0]
    same(fingerprint(link), MESSAGE_LINK_SHA, 'replayed seven-edge message association')
    same(sha(ROOT / 'data/documents/message-1508501.json'), link['documentSha256'], 'preserved message source hash')
    return spoken


def reader_check(data, dist):
    count, trees = html_check(spoken_projection(data), dist)
    tree = trees[OWNER]; nodes = list(tree.root.descendants())
    for scene in data['missions'][OWNER]:
        section = next(n for n in nodes if n.attrs.get('id') == scene['anchor'])
        contents = list(section.descendants())
        proof = [n for n in contents if n.attrs.get('data-native-timeline-owner') == scene['anchor']]
        require(len(proof) == 1, 'Native owner HTML proof missing/duplicate')
        links = {n.attrs.get('href') for n in proof[0].descendants() if n.tag == 'a'}
        same(links, {e['sourceUrl'] for e in scene['nativeOwnership']['edges'] if 'sourceUrl' in e}, 'Actual native proof links')
        all_links = [n.attrs.get('href', '') for n in contents if n.tag == 'a']
        require(not any('github.com' in link and any(source in unquote(link) for source in (GROUP, NPC, DS)) for link in all_links), 'Absent archive body linked as public original')
        if scene['recordType'] == 'NATIVE_TIMELINE_CHOICES':
            require(section.ancestor(lambda n: 'data-mission-reader' in n.attrs) and not section.ancestor(lambda n: 'data-reference-scenes' in n.attrs), 'Native choice demoted from primary reader')
            actual = [n for n in contents if n.attrs.get('data-passage') == 'choice']
            same(len(actual), len(scene['rows']), 'Actual native HTML choices')
            for node, row in zip(actual, scene['rows']):
                parts = list(node.descendants())
                bodies = [n for n in parts if 'original-body' in n.attrs.get('class', '').split()]
                require(len(bodies) == 1 and bodies[0].text() == row['text'], 'Native choice original changed')
                target = [n for n in parts if n.tag == 'a' and unquote(urlsplit(n.attrs.get('href', '')).path).endswith('/' + row['url'].split('#')[0]) and urlsplit(n.attrs.get('href', '')).fragment == row['url'].split('#')[1]]
                require(len(target) == 1 and 'data-reading-link' in target[0].attrs, 'Native option source/return CTA missing')
                original = Tree((dist / row['url'].split('#')[0]).read_text('utf8'))
                require(sum(n.attrs.get('id') == row['url'].split('#')[1] for n in original.root.descendants()) == 1, 'Native option source target missing')
    item = next(r for r in read(dist / 'reading-catalog.json') if r['id'] == OWNER)
    same((item['state'], item['dialogueCount'], item['choiceCount'], item['sceneCount']), ('dialogue-linked',20,8,15), 'Native reader catalogue')
    cards = [n for n in nodes if n.attrs.get('data-native-mission-message') == 'message-1508501']
    require(len(cards) == 1, 'Native related message card coverage')
    link = data['relatedDocuments'][OWNER][0]; card = cards[0]
    require(link['excerpt'] in card.text() and '메시지의 실제 재생 시점은 확인 중입니다.' in card.text(), 'Native message quote/runtime boundary')
    targets = [n for n in card.descendants() if n.tag == 'a' and unquote(urlsplit(n.attrs.get('href', '')).path).endswith('/문서/message-1508501.html') and urlsplit(n.attrs.get('href', '')).fragment == 'original']
    require(len(targets) == 1 and targets[0].attrs.get('id') == 'native-related-message-1508501' and 'data-reading-link' in targets[0].attrs, 'Native message original/return CTA')
    original = Tree((dist / '문서/message-1508501.html').read_text('utf8'))
    require(sum(n.attrs.get('id') == 'original' for n in original.root.descendants()) == 1, 'Native related message original anchor')
    links = {n.attrs.get('href') for n in card.descendants() if n.tag == 'a' and n not in targets}
    same(links, {e['sourceUrl'] for e in link['sourceEdges'] if 'sourceUrl' in e}, 'Native message actual source links')
    return count


def main(args):
    data = read(ROOT / 'data/native-timeline-mission-dialogue.json'); validate(data); rejected = 0
    if args.self_test:
        def first(d): return d['missions'][OWNER][0]
        def choice(d): return next(s for s in d['missions'][OWNER] if s['recordType'] == 'NATIVE_TIMELINE_CHOICES')['rows'][0]
        mutations = [lambda d: first(d)['ownership'][0].update(value=1), lambda d:first(d)['ownership'][0].update(sourceSha256='0'*64),
            lambda d:first(d)['ownership'][1].update(target=DS), lambda d:first(d)['ownership'][2].update(PerformanceID=401014603),
            lambda d:first(d)['ownership'][3].update(registeredShards=['PerformanceD']), lambda d:first(d)['ownership'][4].update(fullFieldEOF=1823),
            lambda d:first(d)['ownership'][4].update(sourceUrl='https://example.org/missing.json'), lambda d:first(d)['rows'][0].update(raw='changed'),
            lambda d:first(d)['rows'][0].update(url='대사/missing.html#talk-1'), lambda d:first(d)['rows'][0]['timelineClip'].update(talkIDSpan=[0,999999]),
            lambda d:choice(d).update(label='대사'), lambda d:choice(d)['choiceSource'].update(taskPointer='/wrong'),
            lambda d:choice(d)['choiceSource'].update(triggerCustomString='wrong'), lambda d:choice(d).update(text='changed'),
            lambda d:d['evidence'].update(privatePath='D:/game/.codex-work/private.json'), lambda d:d['counts'].update(rows=29),
            lambda d:first(d)['rows'][0]['timelineClip'].update(objectSha256='0'*64),
            lambda d:first(d)['timelineSource'].update(rootPathID='123456'),
            lambda d:(first(d)['ownership'][1].update(sourceSha256='0'*64),first(d)['nativeOwnership']['edges'][1].update(sourceSha256='0'*64)),
            lambda d:d['relatedDocuments'][OWNER][0].update(runtimePlayback='PASS'),
            lambda d:d['relatedDocuments'][OWNER][0]['sourceEdges'][5]['task'].update(MessageSectionID=1)]
        for mutate in mutations:
            changed = deepcopy(data); mutate(changed)
            try: validate(changed)
            except (AssertionError, ValueError, KeyError, IndexError): rejected += 1
            else: raise ValueError('Native meaningful mutation accepted')
    scenes = reader_check(data, args.dist) if args.dist else 0
    print({'status':'PASS', **COHORT, 'mutationRejections':rejected, 'builtSpokenScenes':scenes})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--dist',type=Path); p.add_argument('--self-test',action='store_true')
    main(p.parse_args())
