"""Independent public snapshot callers plus exact installed Timeline/Ko replay.

The archived JSON caller domain is kept separate from compiled native caller
proof: no synthetic native field spans, native whole EOF, or installed caller
edition claims. Native object primitives come from the frozen independent reader.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import math
import struct
import sys
import tarfile
import verify_fresh_native_timeline as fv
from verify_fresh_native_timeline import (require, sha, load, pointer, relative, public_safe, sequence_hash,
    scene_rows, readable, HASH, DOMAINS, TRACK_CLASSES, same_object, raw_object, decode_root, decode_track,
    decode_asset, normalize_fields, audit_records, file_sha, TimelineHTML, official_replay)

PROJECTION_SHA = '94bc9b8177a03aa4cc617b026de7e2474217a3b435fe2a55865ba35e66ac0ccc'
PRIMITIVES_SHA = '306124fe1969f13cdcfc18a0c8dba2a060acb89084755dedf55286632af07915'
SCENE_SET_SHA = '33b944092ccc8e1aac19d46fe6a2561e84dc959284063441a3700fd00f1df6db'
ID_SET_SHA = 'b26d39abe8f024edb74a9935084ebb0df17d08ea290e1974f7a7c7e1a11ff803'
ARCHIVE_COMMIT = '8b178dd48698e5e7b12f0cc319ddab149f2ffc5c'
KIND = 'CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED'


def snapshot_boundary(value):
    require(value['callerSourceKind'] == KIND and value['nativeCallerWholeEOF'] is False
            and value['nativeInstalledCallerClaim'] is False, 'Snapshot native caller domain/boolean claim altered')
    if 'nativeCallerFieldSpan' in value:
        require(value['nativeCallerFieldSpan'] is None, 'Invented snapshot caller byte span')
    if 'rawConsumerByteFrontier' in value:
        frontier = value['rawConsumerByteFrontier']
        require(frontier['wholeNativeEOF'] is False and type(frontier['byteOffset']) is int
                and 0 <= frontier['byteOffset'] < frontier['nativeBytes'] and frontier['firstFailure'],
                'Snapshot actual native first-failure boundary altered')
        require(HASH.fullmatch(frontier['entrySha256']), 'Snapshot native STOP source SHA differs')


class TimelineHTML(fv.TimelineHTML):
    def __init__(self):
        super().__init__()
        self.caller_domains = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'details' and attributes.get('id') == 'verified-sources':
            self.caller_domains.append(attributes.get('data-caller-source-kind'))
        super().handle_starttag(tag, attrs)


def owner_notice(scene, text):
    if len(scene['owners']) < 2:
        require('여러 임무 기록이 이 연출을 호출합니다' not in text, 'Single snapshot owner incorrectly described as multiple owners')


def source_validate(repo, data, inverse=None):
    public_safe(data)
    snapshot_boundary(data['evidence'])
    require(data['counts']['nativeCallerWholeEOF'] is False, 'Snapshot whole EOF count boundary altered')
    require(set(data['sourceProofs']) and all(s['callerSourceKind'] == KIND for s in data['scenes']), 'Snapshot scene source kind differs')
    require(data['schema'] == 'starrail-public-snapshot-timeline-dialogue.v1', 'Fresh public Timeline schema')
    require(data['evidence']['officialKorean']['kind'] == 'OFFICIAL_GAME_KOREAN_TEXTMAP', 'Fresh Korean edition domain')
    files, memberships = {}, {}
    roles, ids, used_sources = Counter(), set(), set()
    scene_ids, occurrences = set(), set()
    for scene in data['scenes']:
        require(re.fullmatch(r'snapshot-timeline-[0-9a-f]{20}', scene['id']) and scene['id'] not in scene_ids,
                'Fresh scene kind/duplicate identity')
        scene_ids.add(scene['id'])
        relative(scene['source'])
        require(scene_rows(scene), 'Fresh source has no readable rows')
        require(scene['source'] == scene['proof']['container']['key'], 'Exact canonical native source key differs')
        expected_status = 'UNOWNED_NATIVE_TIMELINE' if not scene['owners'] else 'ONE_EXPLICIT_SNAPSHOT_OWNER' if len(scene['owners']) == 1 else 'MULTIPLE_EXPLICIT_SNAPSHOT_OWNERS'
        require(scene['ownerStatus'] == expected_status, 'Fresh explicit owner status differs')
        proof = scene['proof']
        receipt, root, container = proof['receipt'], proof['root'], proof['container']
        require(root['class'] == 'TimelineAsset' and str(container['pathID']) == root['pathID'] and container['fileID'] == 0,
                'Fresh direct container/TimelineAsset root domain')
        require(HASH.fullmatch(root['sha256']) and HASH.fullmatch(receipt['cabSha256'])
                and HASH.fullmatch(receipt['sourceBlockSha256']), 'Fresh native root/source SHA domain')
        require(type(receipt['bundleOffset']) is int and receipt['bundleOffset'] >= 0
                and type(receipt['bundleBytes']) is int and receipt['bundleBytes'] > 0,
                'Fresh bundle byte bounds')
        owner_keys = {owner['mission'] for owner in scene['owners']}
        require(len(owner_keys) == len(scene['owners']), 'Duplicate explicit fresh owners')
        for owner in scene['owners']:
            require(set(owner) <= {'mission', 'canonicalMission', 'title'}, 'Unexpected inferred fresh owner/region field')
            name = 'data/documents/' + owner['canonicalMission'] + '.json'
            relative(name)
            if name not in memberships:
                memberships[name] = load(repo / name)
            doc = memberships[name]
            require(doc['id'] == owner['canonicalMission'] and owner['mission'] in doc.get('missionParts', [doc['id']]),
                    'Fresh mission actual membership differs')
        source_owners = set()
        for ref in proof['references']:
            key = str(ref['sourceIndex'])
            source = data['sourceProofs'][key]
            require(set(source) == {'mission', 'logicalJsonPath', 'sourceSha256', 'ownerChain', 'archiveCommit',
                    'archiveSha256', 'callerSourceKind', 'nativeCallerWholeEOF', 'nativeInstalledCallerClaim',
                    'nativeCallerFieldSpan', 'rawConsumerByteFrontier'}, 'Unexpected snapshot caller byte proof fields')
            used_sources.add(key)
            relative(source['logicalJsonPath'])
            snapshot_boundary(source)
            require(HASH.fullmatch(source['sourceSha256']) and source['archiveSha256'] == data['evidence']['archiveSha256']
                    and source['archiveCommit'] == ARCHIVE_COMMIT, 'Snapshot caller original SHA/edition differs')
            require(ref['fieldSpan'] is None and ref['pointer'].endswith('/TimelineName'), 'Invented snapshot caller native field span')
            snapshot_boundary(ref)
            chain = source['ownerChain']
            require(chain and chain[0]['kind'] == 'EXPLICIT_MAIN_MISSION_ID', 'Fresh owner chain seed domain')
            seed = chain[0]
            require(source['mission'] == 'quest-' + str(seed['canonicalMissionId']) and source['mission'] in owner_keys,
                    'Fresh source owner/mission explicit ID differs')
            name = seed['membershipSource']
            relative(name)
            require(name == 'data/documents/quest-' + str(seed['canonicalMissionId']) + '.json', 'Fresh canonical membership source domain')
            raw = (repo / name).read_bytes()
            require(sha(raw) == seed['membershipSha256'] and pointer(json.loads(raw), seed['membershipPointer']) == 'quest-' + str(seed['missionId']),
                    'Fresh membership pointer/source SHA differs')
            require(chain[-1].get('target') == source['logicalJsonPath'], 'Fresh owner path does not reach caller source')
            for edge in chain:
                require(edge['kind'] in ('EXPLICIT_MAIN_MISSION_ID', 'EXPLICIT_JSON_PATH', 'EXPLICIT_PERFORMANCE_LOOKUP'),
                        'Unsupported fresh owner edge domain')
                relative(edge['source'])
                require(HASH.fullmatch(edge['sourceSha256']), 'Fresh owner source SHA domain')
                if edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                    require(edge['lookupScope'] == 'TYPED_PRIMARY_TABLE'
                            and edge['performanceType'] in ('A', 'C', 'D', 'E'), 'Fresh performance caller/table domain')
                    require(edge['tableSource'] == 'ExcelOutput/Performance' + ('DS' if edge['performanceType'] == 'D' else edge['performanceType']) + '.json',
                            'Fresh performance type/table identity differs')
            context = ref['context']
            parent_pointer = ref['pointer'].rsplit('/', 1)[0]
            require(context['typedContainer'] == {'type': 'RPG.GameCore.PlayTimeline', 'pointer': parent_pointer}
                    and context['typedAncestors'][-1]['pointer'] == parent_pointer
                    and context['typedAncestors'][-1]['type'] == 'RPG.GameCore.PlayTimeline'
                    and context['typedAncestors'][-1]['branchOrChildKey'] == 'TimelineName',
                    'Fresh declared native TimelineName caller domain differs')
            relative(context['typedAncestors'][-1]['contextFields']['TimelineName'])
            source_owners.add(source['mission'])
        require(source_owners == owner_keys, 'Fresh owner has no exact native caller source')
        for match in scene.get('existingRootMatches', []):
            require(match['sceneId'] in scene['existingSceneIds'], 'Existing native root identity absent')
        anchors = set()
        previous_time = -1
        for row in scene_rows(scene):
            require(set(row['sourceIndices']) == {r['sourceIndex'] for r in proof['references']}, 'Snapshot row exact caller partition differs')
            tid = row['talkId']
            obj, field, track = row['object'], row['idField'], row['track']
            require(type(tid) is int and 0 < tid < 2 ** 32 and DOMAINS.get(obj['class']) == (row['role'], field['field'])
                    and field['value'] == tid, 'Fresh clip class/literal UInt32/role domain')
            require(row['anchor'] not in anchors and re.fullmatch(('reference-' if row['role'] == 'NON_SPOKEN_OPTION_REFERENCE' else 'talk-') + str(tid) + r'-[1-9]\d*', row['anchor']),
                    'Fresh original occurrence anchor domain')
            anchors.add(row['anchor'])
            require(all(type(row[key]) in (int, float) and math.isfinite(row[key]) for key in ('start', 'duration'))
                    and row['start'] >= previous_time and row['duration'] > 0, 'Fresh static source clip time/order differs')
            previous_time = row['start']
            start, end = field['span']
            require(type(start) is int and type(end) is int and 0 <= start < end <= obj['byteSize'] and end - start == 4,
                    'Fresh literal ID width/span differs')
            require(HASH.fullmatch(obj['sha256']) and HASH.fullmatch(track['sha256'])
                    and track['class'] in TRACK_CLASSES and type(row['trackClipIndex']) is int and row['trackClipIndex'] >= 0,
                    'Fresh object/track source domain')
            route = row['parentRoute']
            require(route and route[0] == track['pathID'] and route[-1] == root['pathID'] and len(route) == len(set(route)),
                    'Fresh native PPtr route endpoints/cycle')
            occurrence = (receipt['cabSha256'], root['pathID'], obj['pathID'], track['pathID'], row['trackClipIndex'])
            require(occurrence not in occurrences, 'Duplicate adopted exact fresh native occurrence')
            occurrences.add(occurrence)
            join = data['joins'][str(tid)]
            src = join['preservedSource']
            relative(src['file'])
            require(src['file'].startswith('data/dialogues/'), 'Fresh preserved Korean source domain')
            if src['file'] not in files:
                raw = (repo / src['file']).read_bytes()
                files[src['file']] = (sha(raw), json.loads(raw))
            h, corpus = files[src['file']]
            original = pointer(corpus, src['pointer'])
            require(h == src['sha256'] and original['talk_id'] == tid and isinstance(join['raw'], str),
                    'Fresh original Korean source/hash/ID differs')
            normalized = readable(join['raw'])
            require(normalized == original['text'] and (readable(join['speakerRaw']) or '화자 미지정') == original['speaker'], 'Fresh raw Korean projection differs')
            if inverse is not None:
                target = '대화/연출-' + scene['id'] + '.html#' + row['anchor']
                require(any(link['url'] == target and link['source'] == scene['source'] and link['role'] == row['role']
                            for link in inverse['readerLinks'].get(str(tid), [])), 'Fresh exact inverse original anchor absent')
            roles[row['role']] += 1
            ids.add(tid)
    require(set(data['joins']) == {str(tid) for tid in ids} and set(data['sourceProofs']) == used_sources,
            'Fresh adopted join/source proof partition differs')
    require(data['counts']['sceneCount'] == len(scene_ids) and data['counts']['includedUniqueIDs'] == len(ids)
            and all(data['counts']['occurrences']['included_' + role] == count for role, count in roles.items()),
            'Fresh declared adopted counts differ')
    require(sequence_hash(sorted(scene_ids)) == SCENE_SET_SHA and sequence_hash(sorted(ids)) == ID_SET_SHA,
            'Frozen fresh scene/ID cohort differs')
    return {'adoptedScenes': len(scene_ids), 'adoptedOriginals': sum(roles.values()), 'adoptedTalkIds': len(ids),
            'roles': dict(roles), 'preservedKoreanFiles': len(files), 'exactCallerSources': len(used_sources)}


def native_replay(data, directory):
    # Read a closed scope's JSONL once, index only exact native root identities.
    paths = []
    for receipt in [{'file': 'public-snapshot-cab-decoded.jsonl', 'sha256': data['evidence']['rawAuditSha256']}] :
        relative(receipt['file'])
        path = directory / receipt['file']
        require(sha(path.read_bytes()) == receipt['sha256'], 'Immutable CAB route audit SHA differs')
        paths.append(path)
    wanted = {}
    def target_key(receipt, container, root):
        return receipt.get('cabSha256'), container['key'], str(root['pathID']), root['sha256']
    for scene in data['scenes']:
        proof = scene['proof']
        key = target_key(proof['receipt'], proof['container'], proof['root'])
        require(key not in wanted, 'Duplicate exact adopted Timeline root')
        wanted[key] = scene
    inventories, inventory_names, found, decoded_counts, native_rows = {}, set(), set(), Counter(), 0
    raw_record_counts = Counter()
    for record in audit_records(paths):
        raw_record_counts['records'] += 1
        receipt = record['sourceReceipt']
        for target in record['targets']:
            if target.get('status') != 'SUPPORTED_TYPED_ROOT_ROUTE_PASS':
                raw_record_counts['nonTimelineTargets'] += 1
                continue
            raw_record_counts['supportedRoots'] += 1
            key = target_key(receipt, target['rootContainer'], target['rootObject'])
            if key not in wanted:
                continue
            require(key not in found, 'Duplicate raw exact adopted root identity')
            found.add(key)
            scene = wanted[key]
            public = scene['proof']['receipt']
            for old, new in [('blockFile', 'blockFile'), ('blockSha256', 'sourceBlockSha256'), ('bundleOffset', 'bundleOffset'),
                             ('bundleBytes', 'bundleBytes'), ('cabName', 'cabName'), ('cabSha256', 'cabSha256')]:
                require(receipt[old] == public[new], 'Actual CAB/container receipt identity differs')
            inv_path = Path(receipt['inventory'])
            inventory_names.add(str(inv_path))
            if str(inv_path) not in inventories:
                if len(inventories) >= 8:
                    inventories.clear()
                raw = inv_path.read_bytes()
                require(sha(raw) == receipt['inventorySha256'], 'Actual CAB inventory SHA differs')
                inv = json.loads(raw)
                require(inv['sourceSha256'] == receipt['blockSha256'], 'Actual inventory source block receipt differs')
                inventories[str(inv_path)] = inv
            inv = inventories[str(inv_path)]
            cab, = [cab for cab in inv['cabs'] if cab['name'] == receipt['cabName']]
            require(cab['sha256'] == receipt['cabSha256'] and cab['bytes'] == receipt['cabBytes']
                    and cab['bundleOffset'] == receipt['bundleOffset'], 'Actual inventory CAB receipt differs')
            folder = Path(receipt['objectFolder'])
            same_object(scene['proof']['root'], target['rootObject'])
            require(normalize_fields(target['rootContainer']) == scene['proof']['container'], 'Actual canonical container export differs')
            raw, obj = raw_object(folder, receipt['cabName'], cab, target['rootObject'])
            root = decode_root(raw, obj)
            require(root['fields'] == normalize_fields(target['rootFields']) and root['eof'] == target['rootEOF'], 'Independent native root fields/EOF differ')
            decoded_counts['TimelineAsset'] += 1
            tracks, assets = {}, {}
            def track(pathid):
                pathid = str(pathid)
                if pathid not in tracks:
                    proof = target['trackProofs'].get(pathid)
                    if proof is None:
                        inventory_object, = [o for o in cab['objects'] if str(o['pathID']) == pathid]
                        script, = [o for o in cab['objects'] if o['pathID'] == inventory_object['scriptPointer']['m_PathID']]
                        require(script['script']['m_ClassName'] == 'GroupTrack', 'Unsupported native parent track schema')
                        proof = {'object': dict(inventory_object, **{'class': 'GroupTrack'})}
                    raw, obj = raw_object(folder, receipt['cabName'], cab, proof['object'])
                    actual = decode_track(raw, obj, proof['object']['class'])
                    require(('fields' not in proof or actual['fields'] == normalize_fields(proof['fields']))
                            and ('eof' not in proof or actual['eof'] == proof['eof']),
                            'Independent native track fields/whole EOF differ')
                    tracks[pathid] = actual
                    decoded_counts[proof['object']['class']] += 1
                return tracks[pathid]
            candidates = {}
            for candidate in target['rows'] + target.get('options', []):
                ckey = (str(candidate['object']['pathID']), str(candidate['track']['pathID']), candidate['trackClipIndex'])
                require(ckey not in candidates, 'Duplicate raw native clip occurrence')
                candidates[ckey] = candidate
            refs = target['publicSnapshotReferences']
            for reference in scene['proof']['references']:
                source = data['sourceProofs'][reference['sourceIndex']]
                literal = reference['context']['typedAncestors'][-1]['contextFields']['TimelineName']
                matching = [r for r in refs if r['source'] == source['logicalJsonPath'] and r['pointer'] == reference['pointer']
                            and r['sourceSha256'] == source['sourceSha256'] and r['timelineName'] == literal]
                require(matching, 'Exact snapshot/native container lookup proof absent')
                for raw_ref in matching:
                    require(raw_ref['kind'] == KIND and raw_ref['archiveSha256'] == source['archiveSha256']
                            and raw_ref['archiveCommit'] == source['archiveCommit'] and raw_ref['nativeCallerWholeEOF'] is False
                            and raw_ref['nativeInstalledCallerClaim'] is False and raw_ref['nativeCallerFieldSpan'] is None,
                            'Raw snapshot falsely claims native caller proof')
                    require(raw_ref['snapshotTask'] == dict(reference['context']['typedAncestors'][-1]['contextFields'], **{'$type': 'RPG.GameCore.PlayTimeline'}),
                            'Raw exact snapshot task differs')
                    require(any(o['ownerChain'] == source['ownerChain'] and o['rawConsumerByteFrontier'] == source['rawConsumerByteFrontier'] for o in raw_ref['owners']),
                            'Raw snapshot owner/native failure frontier differs')
            for row in scene_rows(scene):
                ckey = (row['object']['pathID'], row['track']['pathID'], row['trackClipIndex'])
                candidate = candidates[ckey]
                same_object(row['object'], candidate['object'])
                same_object(row['track'], candidate['track'])
                require(candidate['role'] == row['role'] and str(row['talkId']) == str(candidate.get('talkID', candidate.get('referenceOptionTalkID')))
                        and candidate['parentRoute'] == row['parentRoute'], 'Exact raw native role/ID/parent route differs')
                asset_key = row['object']['pathID']
                if asset_key not in assets:
                    raw, obj = raw_object(folder, receipt['cabName'], cab, candidate['object'])
                    actual = decode_asset(raw, obj, row['object']['class'])
                    require(actual['fields'] == normalize_fields(candidate['assetFields']) and actual['eof'] == candidate['assetEOF'],
                            'Independent native clip fields/whole EOF differ')
                    assets[asset_key] = actual
                    decoded_counts[row['object']['class']] += 1
                field, = [f for f in assets[asset_key]['fields'] if f['field'] == row['idField']['field']]
                require(field == row['idField'], 'Independent typed literal UInt32 span/value differs')
                route = row['parentRoute']
                for child, parent in zip(route, route[1:]):
                    require(track(child)['parent'] == {'fileID': 0, 'pathID': parent}, 'Independent native parent PPtr differs')
                    parents_children = root['tracks'] if parent == route[-1] else track(parent)['children']
                    require({'fileID': 0, 'pathID': child} in parents_children, 'Independent reciprocal root/track PPtr absent')
                clip = track(row['track']['pathID'])['clips'][row['trackClipIndex']]
                require(clip == normalize_fields(candidate['timelineClip']) and clip['m_Asset'] == {'fileID': 0, 'pathID': asset_key}
                        and clip['m_Start'] == row['start'] and clip['m_Duration'] == row['duration'],
                        'Independent native clip asset PPtr/time/order differs')
                require(set(row['sourceIndices']) == {r['sourceIndex'] for r in scene['proof']['references']}, 'Native row caller usage partition differs')
                native_rows += 1
    require(found == set(wanted), 'Adopted exact native root absent in closed route census')
    require(raw_record_counts == {'records': 1573, 'supportedRoots': 1573, 'nonTimelineTargets': 1543}, 'Whole closed native input scope differs')
    return {'rawScope': dict(raw_record_counts), 'actualAdoptedNativeRoots': len(found), 'actualNativeOriginalOccurrences': native_rows,
            'actualFullEOFObjects': dict(decoded_counts), 'inventoryFiles': len(inventory_names),
            'scriptClassBoundary': 'MonoScript 115 class/namespace is inventory-SHA/block-SHA/CAB-SHA bound; only MonoBehaviour 114 has raw export bytes',
            'installedVersion': 'UNVERIFIED', 'unadoptedRoots': 26}


def archive_replay(data, archive):
    require(file_sha(archive) == data['evidence']['archiveSha256'], 'Exact owner archive SHA differs')
    needed, terminals = {}, set()
    def need(name, expected):
        relative(name)
        require(name not in needed or needed[name] == expected, 'Conflicting archive source SHA')
        needed[name] = expected
    for source in data['sourceProofs'].values():
        for edge in source['ownerChain']:
            need(edge['source'], edge['sourceSha256'])
            if 'tableSource' in edge:
                need(edge['tableSource'], edge['tableSha256'])
    for source in data['sourceProofs'].values():
        need(source['logicalJsonPath'], source['sourceSha256'])
        terminals.add(source['logicalJsonPath'])
    documents = {}
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name.split('/', 1)[-1]
            if name in needed or name in terminals:
                raw = tar.extractfile(member).read()
                require(name not in documents, 'Duplicate actual archived source')
                if name in needed:
                    require(sha(raw) == needed[name], 'Actual archive owner/table source SHA differs')
                documents[name] = json.loads(raw)
    require(set(documents) == set(needed) | terminals, 'Exact archived owner/table/available terminal absent')
    for source in data['sourceProofs'].values():
        seed, path, edge = source['ownerChain']
        require(pointer(documents[seed['source']], seed['pointer']) == seed['missionId'], 'Actual archived explicit main mission ID differs')
        require(path['source'] == seed['source'] and pointer(documents[path['source']], path['pointer']) == path['target']
                and edge['source'] == path['target'], 'Actual archive owner source path continuity differs')
        parent = pointer(documents[edge['source']], edge['pointer'].rsplit('/', 1)[0])
        performance_id = pointer(documents[edge['source']], edge['pointer'])
        table = documents[edge['tableSource']]
        require(parent['$type'] == 'RPG.GameCore.TriggerPerformance' and parent['PerformanceType'] == edge['performanceType']
                and performance_id == edge['performanceId'] and pointer(table, edge['idPointer']) == performance_id
                and pointer(table, edge['pathPointer']) == source['logicalJsonPath'], 'Actual typed performance source/table target differs')
        require({r['PerformancePath'] for r in table if r.get('PerformanceID') == performance_id} == {source['logicalJsonPath']},
                'Actual typed performance lookup ambiguous')
    checked = set()
    for scene in data['scenes']:
        for ref in scene['proof']['references']:
            source = data['sourceProofs'][ref['sourceIndex']]
            name = source['logicalJsonPath']
            parent = pointer(documents[name], ref['pointer'].rsplit('/', 1)[0])
            context = ref['context']['typedAncestors'][-1]['contextFields']
            require(parent == dict(context, **{'$type': 'RPG.GameCore.PlayTimeline'}),
                    'Actual whole archived snapshot typed TimelineName caller differs')
            checked.add((name, ref['pointer']))
    return {'actualArchiveFiles': len(needed), 'actualArchiveCallerFiles': len(terminals),
            'actualArchiveOwnerChains': len(data['sourceProofs']), 'actualArchivedSnapshotTerminalCalls': len(checked),
            'nativeCallerWholeEOF': False, 'nativeInstalledCallerClaim': False}


def rendered_scene(scene, data, corpus, static, expanded):
    page = TimelineHTML()
    page.feed(static)
    page.close()
    owner_notice(scene, ''.join(page.text))
    rows = scene_rows(scene)
    require(all(n == 1 for n in page.ids.values()), 'Duplicate static original anchors')
    require([r['talkId'] for r in page.rows] == [r['talkId'] for r in rows], 'Static native originals ID/order differs')
    for row, actual in zip(rows, page.rows):
        source = data['joins'][str(row['talkId'])]['preservedSource']
        original = pointer(corpus[source['file']], source['pointer'])
        is_reference = row['role'] == 'NON_SPOKEN_OPTION_REFERENCE'
        require(actual['role'] == row['role'] and actual['speaker'] == original['speaker']
                and actual['passage'] == ('choice' if is_reference else 'dialogue') and actual['choice'] == is_reference,
                'Static native role/speaker/choice display differs')
        require(actual['paragraphs'] == [{'anchor': row['anchor'], 'text': original['text']}] and page.ids[row['anchor']] == 1,
                'Static Korean original body/anchor differs')
        href = '/starrail-quests/대사/' + Path(source['file']).stem + '.html#talk-' + str(row['talkId'])
        require(href in actual['links'], 'Native original return link absent')
    for owner in scene['owners']:
        require('/starrail-quests/문서/' + owner['canonicalMission'] + '.html#deep-timeline-originals' in page.links,
                'Native explicit owner reading return link absent')
    proof = TimelineHTML()
    proof.feed(expanded)
    proof.close()
    require(proof.proof_markers == [row['anchor'] for row in rows] and proof.ids['verified-sources'] == 1,
            'Rendered native technical markers/order absent')
    text = ''.join(proof.text)
    receipt = scene['proof']['receipt']
    require(all(value in text for value in (scene['source'], receipt['cabName'], receipt['cabSha256'],
                receipt['sourceBlockSha256'], scene['proof']['root']['sha256'], scene['proof']['root']['pathID'])),
            'Rendered exact native source/root identity absent')
    require(not re.search(r'(?i)[a-z]:[/\\]|file://|\.codex-work[/\\]', text), 'Private path in rendered native evidence')
    for ref in scene['proof']['references']:
        source = data['sourceProofs'][ref['sourceIndex']]
        require(source['logicalJsonPath'] in text and ref['pointer'] in text and source['sourceSha256'] in text
                and '호출자 바이너리의 전체 해석은 미지원 상태' in text,
                'Rendered exact native caller span/hash absent')
    require(proof.caller_domains == [KIND], 'Rendered caller source domain marker absent/altered')
    for row in rows:
        join = data['joins'][str(row['talkId'])]
        source = join['preservedSource']
        original = pointer(corpus[source['file']], source['pointer'])
        require(all(value in text for value in (row['object']['pathID'], row['object']['sha256'], row['track']['sha256'],
                    row['idField']['field'], '–'.join(map(str, row['idField']['span'])), original['hash'], join['raw'])),
                'Rendered native UInt64/literal ID/source raw proof absent')
    return len(rows)


def dist_replay(repo, data, directory, publication_report=None):
    corpus = {name: load(repo / name) for name in {j['preservedSource']['file'] for j in data['joins'].values()}}
    expansion, report, rows = None, None, 0
    for scene in data['scenes']:
        path = directory / '대화' / ('연출-' + scene['id'] + '.html')
        require(path.is_file(), 'Native fresh static reader absent: ' + scene['id'])
        static = path.read_text(encoding='utf8')
        expanded = static
        if re.search(r'__spr\(|__sp\(|__starrailPublicationWrite\(', static):
            if expansion is None:
                # Existing independent reader's shard hashes/bytes are validated;
                # its closure caches each decoded shard once for all 3,204 pages.
                from optimize_publication import expansion_function
                report = load(publication_report or repo / '.codex-work/publication-build-report.json')
                for shard in report.get('proofShards', {}).values():
                    url = unquote(shard['url'])
                    require(url.startswith('/starrail-quests/'), 'Technical shard URL base differs')
                    relative_name = url[len('/starrail-quests/'):]
                    relative(relative_name)
                    actual = (directory / relative_name).read_bytes()
                    require(sha(actual) == shard['assetSha256'], 'Actual technical shard source SHA differs')
                expansion = expansion_function(report)
            expanded = expansion(static)
        rows += rendered_scene(scene, data, corpus, static, expanded)
    return {'staticSnapshotReaders': len(data['scenes']), 'staticSnapshotOriginals': rows,
            'technicalProofExpansion': 'One cached expansion closure; originals validated before expansion',
            'proofShardReceipts': len(report.get('proofShards', {})) if report else 0}


def closed_receipt_replay(data, directory):
    raw = (directory / 'public-snapshot-source-owner-replay.json').read_bytes()
    require(sha(raw) == data['evidence']['sourceOwnerReplaySha256'], 'Closed snapshot caller/owner receipt SHA differs')
    receipt = json.loads(raw)
    require(receipt['nativeCallerWholeEOF'] is False and receipt['nativeInstalledCallerClaim'] is False
            and receipt['archiveSha256'] == data['evidence']['archiveSha256'] and receipt['failures'] == [],
            'Closed snapshot caller receipt source boundary altered')
    for key, source in data['sourceProofs'].items():
        require(source == receipt['sources'][key], 'Public snapshot caller/native STOP receipt differs')
        for edge, check in zip(source['ownerChain'], receipt['ownerChecks'][key]):
            require(check['status'] == 'PASS' and edge['source'] == check['source'] and edge['pointer'] == check['pointer']
                    and edge['sourceSha256'] == check['actualSourceSha256'], 'Snapshot closed exact owner edge receipt differs')
    return {'adoptedSnapshotSourceReceipts': len(data['sourceProofs']), 'wholeCandidateSnapshotSources': receipt['sourceCount'],
            'nativeCallerWholeEOF': False, 'nativeInstalledCallerClaim': False}


def self_tests(repo, data, inverse):
    tests = []
    def reject(name, fn):
        try:
            fn()
        except (ValueError, KeyError, IndexError, UnicodeError, struct.error):
            tests.append(name)
            return
        raise ValueError('Snapshot semantic mutation accepted: ' + name)
    def mutate(name, edit):
        bad = dict(data)
        bad['scenes'] = list(data['scenes'])
        bad['scenes'][0] = copy.deepcopy(data['scenes'][0])
        bad['evidence'] = dict(data['evidence'])
        bad['counts'] = dict(data['counts'])
        bad['joins'] = dict(data['joins'])
        bad['sourceProofs'] = dict(data['sourceProofs'])
        key = bad['scenes'][0]['proof']['references'][0]['sourceIndex']
        bad['sourceProofs'][key] = copy.deepcopy(data['sourceProofs'][key])
        edit(bad, bad['scenes'][0], bad['sourceProofs'][key])
        reject(name, lambda: source_validate(repo, bad, inverse))
    mutate('snapshot source mistaken for native', lambda d, s, p: p.__setitem__('callerSourceKind', 'NATIVE_CALLER'))
    mutate('invented native caller whole EOF', lambda d, s, p: p.__setitem__('nativeCallerWholeEOF', True))
    mutate('invented installed caller edition', lambda d, s, p: p.__setitem__('nativeInstalledCallerClaim', True))
    mutate('false boundary uses int0 instead of bool', lambda d, s, p: p.__setitem__('nativeCallerWholeEOF', 0))
    mutate('invented source native byte span', lambda d, s, p: p.__setitem__('nativeCallerFieldSpan', {'start': 1, 'end': 2}))
    mutate('invented reference native byte span', lambda d, s, p: s['proof']['references'][0].__setitem__('fieldSpan', {'start': 1, 'end': 2}))
    mutate('invented native pack proof', lambda d, s, p: p.__setitem__('callerPack', {'file': 'invented.bytes'}))
    mutate('native STOP marked EOF', lambda d, s, p: p['rawConsumerByteFrontier'].__setitem__('wholeNativeEOF', True))
    mutate('native STOP offset out of bounds', lambda d, s, p: p['rawConsumerByteFrontier'].__setitem__('byteOffset', 999999))
    mutate('snapshot reference source domain', lambda d, s, p: s['proof']['references'][0].__setitem__('nativeInstalledCallerClaim', True))
    mutate('literal ID domain', lambda d, s, p: s['rows'][0].__setitem__('talkId', 1))
    mutate('spoken role confusion', lambda d, s, p: s['rows'][0].__setitem__('role', 'NON_SPOKEN_OPTION_REFERENCE'))
    mutate('native UInt32 span', lambda d, s, p: s['rows'][0]['idField'].__setitem__('span', [1, 2]))
    mutate('native signed Int64 precision', lambda d, s, p: s['rows'][0]['track'].__setitem__('pathID', 123))
    mutate('native root route endpoint', lambda d, s, p: s['rows'][0]['parentRoute'].__setitem__(-1, '1'))
    mutate('native timing NaN', lambda d, s, p: s['rows'][0].__setitem__('start', float('nan')))
    mutate('invented region owner', lambda d, s, p: s['owners'][0].__setitem__('region', 'Unknown'))
    mutate('invented mission owner', lambda d, s, p: s['owners'][0].__setitem__('mission', 'quest-1'))
    mutate('archived commit mismatch', lambda d, s, p: p.__setitem__('archiveCommit', '0' * 40))
    mutate('archived SHA mismatch', lambda d, s, p: p.__setitem__('archiveSha256', '0' * 64))
    mutate('caller JSON pointer mismatch', lambda d, s, p: s['proof']['references'][0].__setitem__('pointer', '/Wrong/TimelineName'))
    mutate('caller typed class mismatch', lambda d, s, p: s['proof']['references'][0]['context']['typedContainer'].__setitem__('type', 'RPG.GameCore.PlayOptionTalk'))
    mutate('private path leak', lambda d, s, p: p.__setitem__('logicalJsonPath', 'X:/private/source.json'))
    def korean(d, s, p):
        key = str(s['rows'][0]['talkId'])
        d['joins'][key] = dict(d['joins'][key], raw=d['joins'][key]['raw'] + ' changed')
    mutate('Korean original raw mismatch', korean)
    def absence(d, s, p):
        d['scenes'] = d['scenes'][1:]
    mutate('frozen scene absence', absence)
    if inverse is not None:
        bad = dict(inverse, readerLinks=dict(inverse['readerLinks']))
        bad['readerLinks'][str(data['scenes'][0]['rows'][0]['talkId'])] = []
        reject('exact inverse original absence', lambda: source_validate(repo, data, bad))
    positive = '<details id="verified-sources" data-caller-source-kind="' + KIND + '"></details>'
    owner_notice(data['scenes'][0], '임무에서 함께 읽기')
    reject('single snapshot owner false multiowner notice', lambda: owner_notice(data['scenes'][0], '여러 임무 기록이 이 연출을 호출합니다'))
    parser = TimelineHTML()
    parser.feed(positive)
    require(parser.caller_domains == [KIND], 'Snapshot domain marker positive canary')
    for bad_html in (positive.replace(KIND, 'NATIVE'), positive.replace('data-caller-source-kind', 'data-other')):
        def marker_check(bad_html=bad_html):
            parser = TimelineHTML()
            parser.feed(bad_html)
            require(parser.caller_domains == [KIND], 'Snapshot domain marker altered')
        reject('rendered snapshot domain marker', marker_check)
    return tests + fv.guard_tests()['negativeGuardTests']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--projection', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--official-root', type=Path)
    parser.add_argument('--dist', type=Path)
    parser.add_argument('--publication-report', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    require(file_sha(Path(fv.__file__)) == PRIMITIVES_SHA, 'Frozen independent native primitive reader SHA differs')
    raw = (args.projection or repo / 'data/public-snapshot-timeline-dialogue.json').read_bytes()
    require(sha(raw) == PROJECTION_SHA, 'Closed public snapshot projection SHA differs')
    data = json.loads(raw)
    inverse = load(repo / 'data/deep-dialogue-attribution.json')
    require(inverse['evidence']['publicSnapshotTimelineSha256'] == sha(raw), 'Snapshot exact inverse source SHA differs')
    require(file_sha(repo / 'data/native-fresh-timeline-dialogue.json') == data['evidence']['closedNativeFreshProjectionSha256'],
            'Prior frozen native fresh source SHA differs')
    checks = {'source': source_validate(repo, data, inverse)}
    if args.audit:
        checks['closedSnapshotReceipt'] = closed_receipt_replay(data, args.audit.resolve())
        checks['native'] = native_replay(data, args.audit.resolve())
    if args.archive:
        checks['archive'] = archive_replay(data, args.archive.resolve())
    if args.official_root:
        checks['officialKorean'] = official_replay(repo, data, args.official_root.resolve())
    if args.dist:
        checks['dist'] = dist_replay(repo, data, args.dist.resolve(), args.publication_report)
    report = {'schema': 'starrail-public-snapshot-timeline-independent-verification.v1', 'status': 'PASS',
              'projectionSha256': sha(raw), 'verifierSha256': file_sha(Path(__file__)), 'checks': checks,
              'nativeCallerWholeEOF': False, 'nativeInstalledCallerClaim': False,
              'negativeCanaries': self_tests(repo, data, inverse) if args.self_test else [],
              'limits': ['Archived public JSON callers and owners are verified within their snapshot; compiled native caller full EOF remains blocked.',
                         'Installed Timeline clips/tracks/roots have independent native byte replay; installed release edition remains UNVERIFIED.',
                         'MonoScript115 metadata is inventory receipt bound; no independent raw115/CAB decompression claim.',
                         'No synthetic caller byte span or runtime branch execution is inferred.']}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, UnicodeError, struct.error) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
