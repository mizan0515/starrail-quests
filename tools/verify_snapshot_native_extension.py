"""Validate an append-only extension of the immutable snapshot caller overlay.

Default: closed portable37-reference/7-source joins and preserved old1410+34.
--audit: actual seven cached whole entries,37 independent native terminals,
current DLL/metadata raw bindings and archive owner edges. No game code runs.
--dist: raw/optimized exact source markers and110 remaining uncertain readers.
"""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
from html import escape
import json
import mmap
from pathlib import Path
import tarfile

import verify_snapshot_native_corroboration as old

SITE = Path(__file__).resolve().parents[1]
PAYLOAD_SHA = '6247033ea1add050633c28020305f0c9d76c90ea77b6ca62aeac5194f1267899'
PREVIOUS_PAYLOAD_SHA = '1e07f66cb2ddef04c081f5e216338b8aa07bff1fceadc6327ae10807fac30b67'
CANONICAL = '78a2168a3307c5eecb8054b88dd1fd61682bb37b29a0dce5dff7a6b12b7ae883'
PREVIOUS_CANONICAL = 'f1b3cf9b2272625c7626a0515adc287dcd046705e090a557ef0a7c26726b53de'
OLD_VERIFIER_SHA = '5df319bdf06c974a7ea301f2ffbe7c48a334b118ccfd47b711caeae998d96cd9'
AUDIT_MANIFEST_SHA = '52c7fdb2c2f71396652bdba9a24251918b2e333361cfd224b686bb133d245aee'
STAGE13_MANIFEST_SHA = 'bb82e7d1a807e2a43d6f8e334b93622d12d369292af8eb2ee8357ad95fd40d11'
require, sha, file_sha, canonical = old.require, old.sha, old.file_sha, old.canonical
UNKNOWN = old.UNKNOWN


def source_check(repo, data):
    """Return37 validated references; old1410 and the entire old34 extension stay pinned."""
    repo = Path(repo)
    require(file_sha(repo/'tools/verify_snapshot_native_corroboration.py') == OLD_VERIFIER_SHA, 'Pinned old verifier changed')
    previous_raw = (repo/'data/public-snapshot-native-corroboration.json').read_bytes()
    require(sha(previous_raw) == old.OVERLAY_SHA, 'Preserved old overlay changed')
    previous = json.loads(previous_raw)
    old_refs = old.source_check(repo, previous)
    old.public_safe(data)
    require(data['schema'] == 'starrail-snapshot-native-corroboration-extension.v1', 'Extension schema differs')
    require(data['baseProjectionSha256'] == old.PUBLIC_SHA and data['nativeFreshProjectionSha256'] == old.FRESH_SHA
            and data['oldOverlaySha256'] == old.OVERLAY_SHA and data['oldVerifierSha256'] == OLD_VERIFIER_SHA, 'Extension base boundary differs')
    public, _ = old.baseline(repo)
    scenes = {s['id']:s for s in public['scenes']}
    covered = {(r['sceneId'],r['referenceIndex']) for r in old_refs}
    evidence = data['evidence']
    require(evidence['typedConsumer'] == 'RPG.GameCore.PlayTimeline' and evidence['wholeEOFStatus'] == 'WHOLE_NATIVE_FIELDS_EOF_PASS'
            and evidence['trailingByteRejected'] is True, 'Typed whole cached source EOF claim differs')
    require(evidence['callerEditionStatus'] == UNKNOWN and evidence['runtimePlaybackStatus'] == 'UNVERIFIED', 'Edition/runtime boundary weakened')
    require(evidence['nativeInputReceipts'] == previous['evidence']['nativeInputReceipts'], 'Current native input profile differs')
    require(set(evidence['profiles']) == {'12','13'}, 'Unapproved source profile')
    previous_extension = deepcopy(data)
    stage13_sources = {key for key,source in data['sourceProofs'].items() if source['sourceCodeStage'] == 13}
    require(len(stage13_sources) == 1, 'Int16 continuation source count differs')
    previous_extension['sourceProofs'] = {key:source for key,source in data['sourceProofs'].items() if key not in stage13_sources}
    previous_extension['references'] = [ref for ref in data['references'] if ref['nativeSourceIndex'] not in stage13_sources]
    del previous_extension['evidence']['profiles']['13']
    previous_extension['evidence']['counts'] = {'extensionReferences':34,'extensionScenes':34,'extensionSources':6,'oldReferences':1410,'oldScenes':1400,
            'oldSources':239,'combinedReferences':1444,'combinedScenes':1434,'combinedSources':245,'remainingUnmatchedSnapshotScenes':113,'newBodies':0,'newFrozenIds':0}
    require(canonical(previous_extension) == PREVIOUS_CANONICAL, 'Preserved entire34-reference extension changed')
    profile = evidence['profiles']['12']
    for key,pin in profile['retainedCodePins'].items():
        old.relative(key);require(pin['bytes'] > 0 and len(pin['sha256']) == 64, 'Invalid retained reader pin')
    for key,pin in profile['retainedSchemaPins'].items():
        old.relative(key);require(pin['bytes'] > 0 and len(pin['sha256']) == 64, 'Invalid retained schema pin')
    require(profile['sourceCodeReceipt']['file'] == 'phase12-strict-decoder.py'
            and profile['sourceCodeReceipt']['sha256'] == profile['retainedCodePins']['phase12-strict-decoder.py']['sha256']
            and profile['schemaContractsSha256'] == profile['retainedSchemaPins']['phase12-field-contracts.json']['sha256'], 'Reader/schema provenance differs')
    continuation = evidence['profiles']['13']
    require(continuation['baseProfile'] == '12' and continuation['sourceCodeReceipt']['file'] == 'candidate-int16-wire-code.py'
            and continuation['sourceCodeReceipt'] == {'file':'candidate-int16-wire-code.py',**continuation['retainedCodePins']['candidate-int16-wire-code.py']}
            and continuation['schemaContractsSha256'] == continuation['retainedSchemaPins']['stage13-field-contract.json']['sha256']
            and continuation['counts'] == {'wholeSourcesIndependentlyParsed':1,'nativeTerminals':3,'newBodies':0,'newFrozenIds':0}, 'Int16 source profile differs')
    for pins in (continuation['retainedCodePins'],continuation['retainedSchemaPins']):
        for name,pin in pins.items():old.relative(name);require(pin['bytes'] > 0 and len(pin['sha256']) == 64, 'Invalid Int16 retained pin')
    seen,used,scene_ids = set(),set(),set()
    for ref in data['references']:
        pair = (ref['sceneId'],ref['referenceIndex'])
        require(type(ref['referenceIndex']) is int and ref['referenceIndex'] >= 0 and pair not in seen and pair not in covered, 'Duplicate/old/invalid reference pair')
        seen.add(pair)
        scene = scenes[ref['sceneId']]
        original, snapshot, name = old.original_pair(public, scene, ref['referenceIndex'])
        src = data['sourceProofs'][ref['nativeSourceIndex']]
        require(src['snapshotSourceIndex'] == original['sourceIndex'] and src['logicalJsonPath'] == snapshot['logicalJsonPath'], 'Wrong source or public index')
        require(ref['containerKey'] == scene['source'] and ref['rootSha256'] == scene['proof']['root']['sha256'], 'Wrong exact root/container')
        require(ref['ownerChainSha256'] == canonical(snapshot['ownerChain']), 'Wrong owner chain')
        require(ref['sceneRowsSha256'] == canonical(scene['rows']), 'Preserved row/ID projection differs')
        require(original['nativeCallerWholeEOF'] is False and original['nativeInstalledCallerClaim'] is False
                and original['callerSourceKind'] == 'CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED', 'Original source boundary changed')
        require(src['entrySha256'] == snapshot['rawConsumerByteFrontier']['entrySha256']
                and src['consumedBytes'] == snapshot['rawConsumerByteFrontier']['nativeBytes'], 'Wrong original cached source byte identity')
        require(original['context']['typedContainer'] == {'type':'RPG.GameCore.PlayTimeline','pointer':original['pointer'].rsplit('/',1)[0]}, 'Wrong typed source pointer/domain')
        pack = evidence['callerPacks'][src['callerPackIndex']];cat = src['catalogMatch']
        require(cat['length'] == src['consumedBytes'] and cat['packExpectedBytes'] == pack['bytes']
                and 0 <= cat['offset'] < cat['offset'] + cat['length'] <= pack['bytes'], 'Cached source span/EOF escapes pack')
        f,t = ref['fieldSpan'],ref['terminalSpan']
        require(len(f) == len(t) == 2 and all(type(x) is int for x in f+t)
                and 0 <= t[0] < f[0] < f[1] < t[1] <= src['consumedBytes'], 'Native field/terminal span escapes whole source')
        require(ref['mask'] in(6,14) and ref['nativeType'] in(4,8)
                and t[0] == f[0]-3 and t[1] == f[1]+(2 if ref['mask'] == 14 else 1), 'Wrong typed terminal grammar')
        n = len(name.encode('utf8'));require(f[1]-f[0] == n+max(1,(n.bit_length()+6)//7), 'Wrong exact TimelineName UTF8 span')
        require(src['sourceCodeStage'] in (12,13), 'Wrong source profile stage')
        used.add(ref['nativeSourceIndex']);scene_ids.add(scene['id'])
    require(len(seen) == len(scene_ids) == 37 and len(used) == 7 and used == set(data['sourceProofs']), 'Extension coverage differs')
    require(all((sid,i) in seen for sid in scene_ids for i in range(len(scenes[sid]['proof']['references']))), 'Partial scene claimed complete')
    remaining = {s['id'] for s in public['scenes'] if any((s['id'],i) not in covered|seen for i in range(len(s['proof']['references'])))}
    require(len(remaining) == 110, 'Remaining uncertain snapshot scene count differs')
    require(evidence['counts'] == {'extensionReferences':37,'extensionScenes':37,'extensionSources':7,'oldReferences':1410,'oldScenes':1400,
            'oldSources':239,'combinedReferences':1447,'combinedScenes':1437,'combinedSources':246,'remainingUnmatchedSnapshotScenes':110,
            'newBodies':0,'newFrozenIds':0}, 'Extension/combined counts or ID boundary differs')
    require(canonical(data) == CANONICAL, 'Closed extension provenance changed')
    return data['references']


def native_int16(raw):
    """Exact bounded unsigned wire value followed by the native16-bit zigzag."""
    require(0 < len(raw) <= 3, 'Int16 wire length')
    value = 0
    for index,byte in enumerate(raw):
        value |= (byte & 127) << (7*index)
        if not byte & 128:
            require(index == len(raw)-1 and value <= 65535 and (index == 0 or byte != 0), 'Int16 wire bound/canonical form')
            return (value >> 1) ^ -(value & 1)
    raise AssertionError('Int16 wire truncated')


def audit_check(repo, data, directory, installed_root=None, stage13_directory=None, retained_code_root=None):
    directory = Path(directory)
    manifest_raw = (directory/'phase12-extension-audit-manifest.json').read_bytes()
    require(sha(manifest_raw) == AUDIT_MANIFEST_SHA, 'Private audit manifest changed')
    manifest = json.loads(manifest_raw);require(manifest['extensionSha256'] == PREVIOUS_PAYLOAD_SHA, 'Preserved private/public extension boundary differs')
    files = {}
    for name,pin in manifest['inputPins'].items():
        old.relative(name);raw = (directory/name).read_bytes()
        require(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'Frozen private receipt changed: '+name)
        if name.endswith('.json'):files[name] = json.loads(raw)
    profile = data['evidence']['profiles']['12']
    for category in ('retainedCodePins','retainedSchemaPins'):
        paths = manifest['codePaths' if category == 'retainedCodePins' else 'schemaPaths']
        for name,pin in profile[category].items():
            path = Path(paths[name])
            if not path.exists() and name == 'phase5-strict-native-expanded.py' and retained_code_root:
                path = Path(retained_code_root)/name
            require(path.stat().st_size == pin['bytes'] and file_sha(path) == pin['sha256'], 'Actual retained code/schema differs: '+name)
    require(stage13_directory is not None, 'Int16 continuation requires --stage13-audit')
    stage13_directory = Path(stage13_directory)
    continuation_raw = (stage13_directory/'stage13-audit-manifest.json').read_bytes()
    require(sha(continuation_raw) == STAGE13_MANIFEST_SHA, 'Int16 audit manifest changed')
    continuation_manifest = json.loads(continuation_raw)
    continuation_files = {}
    continuation_profile = data['evidence']['profiles']['13']
    require(continuation_manifest['baseAuditManifestSha256'] == AUDIT_MANIFEST_SHA, 'Int16 base audit changed')
    for name,pin in continuation_manifest['inputPins'].items():
        old.relative(name);body = (stage13_directory/name).read_bytes()
        require(len(body) == pin['bytes'] and sha(body) == pin['sha256'], 'Int16 frozen receipt changed: '+name)
        if name.endswith('.json'):continuation_files[name] = json.loads(body)
    for category in ('retainedCodePins','retainedSchemaPins'):
        for name,pin in continuation_profile[category].items():
            old.relative(name);path = stage13_directory/name
            require(path.stat().st_size == pin['bytes'] and file_sha(path) == pin['sha256'], 'Int16 retained reader/schema changed')
    continuation_replay = continuation_files[continuation_manifest['replay']]
    continuation_independent = continuation_files[continuation_manifest['independent']]
    contract = continuation_files[continuation_manifest['contract']]
    require(file_sha(stage13_directory/continuation_manifest['replay']) == continuation_profile['wholeSourceReplaySha256']
            and file_sha(stage13_directory/continuation_manifest['independent']) == continuation_profile['independentReplaySha256'], 'Int16 whole/independent replay changed')
    require(continuation_independent['status'] == 'PASS_RESEARCH_CANDIDATE_INDEPENDENTLY_REPLAYED'
            and continuation_independent['wholeNativeEOF'] is True and continuation_independent['independentFieldsAndSpansIdentical'] is True
            and continuation_independent['allNonenumNonfixedPublicFixtureFieldsMatch'] is True
            and len(continuation_independent['negativeCases']) == 6, 'Int16 independent whole replay absent')
    require(contract['fieldSchema'] == 'predicate163' and contract['fieldSlot'] == 5 and contract['fieldName'] == 'CompareValue'
            and contract['fieldKind'] == 'nativeInt16ZigZag' and contract['wireUnsignedMax'] == 65535
            and contract['expectedSignedValue'] == 1, 'Int16 declared field grammar differs')
    replay = files['phase12-new-field-replay.json'];independent = files['phase12-independent-replay.json']
    require(sha((directory/'phase12-new-field-replay.json').read_bytes()) == profile['wholeSourceReplaySha256']
            and sha((directory/'phase12-independent-replay.json').read_bytes()) == profile['independentReplaySha256'], 'Whole replay/independent pin differs')
    require(independent['status'] == 'PASS' and independent['counts']['newWholeSourcesIndependentlyParsed'] == 16, 'Independent whole source EOF absent')
    current = files['phase12-current-native-profile-raw-replay.json']
    require(sha((directory/profile['currentProfile']['file']).read_bytes()) == profile['currentProfile']['sha256']
            and current['status'] == 'PASS_CURRENT_INPUTS_AND_RECORDED_BYTES'
            and current['currentInputReceipts'] == data['evidence']['nativeInputReceipts'], 'Current native profile differs')
    public,_ = old.baseline(repo);scenes = {s['id']:s for s in public['scenes']};packs,bodies,records = {},{},{}
    needed = {}
    for key,source in data['sourceProofs'].items():
        snapshot = public['sourceProofs'][source['snapshotSourceIndex']]
        source_replay = continuation_replay if source['sourceCodeStage'] == 13 else replay
        candidates = [r for r in source_replay['results'] if r['source'] == source['logicalJsonPath'] and r['sha256'] == source['entrySha256']
                      and r['descriptor']['mission'] == snapshot['mission'] and r['descriptor']['ownerChain'] == snapshot['ownerChain']]
        require(candidates, 'Whole cached source/owner receipt absent')
        rec = candidates[0];require(rec['status'] == 'WHOLE_NATIVE_FIELDS_EOF_PASS' and rec['trailingByteRejected'] is True
                and rec['bytes'] == source['consumedBytes'], 'Actual whole source EOF receipt differs')
        actual_pack = rec['pack'];expected = data['evidence']['callerPacks'][source['callerPackIndex']]
        require(actual_pack['sha256'] == expected['sha256'] and actual_pack['bytes'] == expected['bytes'], 'Actual pack receipt differs')
        if actual_pack['path'] not in packs:
            raw = Path(actual_pack['path']).read_bytes();require(len(raw) == expected['bytes'] and sha(raw) == expected['sha256'], 'Actual cached pack differs')
            packs[actual_pack['path']] = raw
        cat = source['catalogMatch'];body = packs[actual_pack['path']][cat['offset']:cat['offset']+cat['length']]
        require(len(body) == source['consumedBytes'] and sha(body) == source['entrySha256'], 'Actual source entry EOF/SHA differs')
        spans = {s['pointer']:s for s in rec['fieldSpans']};require(spans[''] == {'pointer':'','start':0,'end':len(body)}, 'Whole raw source partition absent')
        for span in spans.values():require(0 <= span['start'] <= span['end'] <= len(body), 'Field escapes source')
        bodies[key],records[key] = body,rec
        if source['sourceCodeStage'] == 13:
            require(source['logicalJsonPath'] == contract['source'] and source['entrySha256'] == contract['sourceSha256'], 'Int16 exact source differs')
            scalar = spans[contract['fieldPointer']]
            require([scalar['start'],scalar['end']] == contract['fieldSpan']
                    and native_int16(body[scalar['start']:scalar['end']]) == old.at(rec['fields'],contract['fieldPointer']) == 1, 'Int16 actual scalar/span differs')
        needed[source['logicalJsonPath']] = snapshot['sourceSha256']
        for edge in snapshot['ownerChain']:
            needed[edge['source']] = edge['sourceSha256']
            if 'tableSource' in edge:needed[edge['tableSource']] = edge['tableSha256']
    documents = {}
    with tarfile.open(manifest['archive'],'r|gz') as archive:
        for member in archive:
            name = member.name.split('/',1)[-1]
            if name not in needed:continue
            raw = archive.extractfile(member).read();require(sha(raw) == needed[name], 'Actual archive source/owner SHA differs')
            documents[name] = json.loads(raw)
    require(set(documents) == set(needed), 'Actual archive owner/source absent')
    edges = 0
    for key,source in data['sourceProofs'].items():
        snapshot = public['sourceProofs'][source['snapshotSourceIndex']]
        for edge in snapshot['ownerChain']:
            parent = documents[edge['source']]
            if edge['kind'] == 'EXPLICIT_MAIN_MISSION_ID':
                require(old.at(parent,edge['pointer']) == edge['missionId'], 'Wrong actual mission seed')
                path = Path(repo)/old.relative(edge['membershipSource']);membership = old.load(path)
                require(file_sha(path) == edge['membershipSha256']
                        and old.at(membership,edge['membershipPointer']) == 'quest-'+str(edge['missionId'])
                        and membership['id'] == snapshot['mission'] == 'quest-'+str(edge['canonicalMissionId']), 'Wrong actual corpus owner membership')
            elif edge['kind'] == 'EXPLICIT_JSON_PATH':require(old.at(parent,edge['pointer']) == edge['target'], 'Wrong actual owner path')
            elif edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                require(old.at(parent,edge['pointer']) == edge['performanceId']
                        and old.at(documents[edge['tableSource']],edge['idPointer']) == edge['performanceId']
                        and old.at(documents[edge['tableSource']],edge['pathPointer']) == edge['target'], 'Wrong actual performance owner bridge')
            else:raise AssertionError('Unsupported actual owner edge')
            edges += 1
    for ref in data['references']:
        scene = scenes[ref['sceneId']];original,_,name = old.original_pair(public,scene,ref['referenceIndex']);rec = records[ref['nativeSourceIndex']]
        spans = {s['pointer']:s for s in rec['fieldSpans']};parent = original['pointer'].rsplit('/',1)[0]
        require([spans[original['pointer']]['start'],spans[original['pointer']]['end']] == ref['fieldSpan']
                and [spans[parent]['start'],spans[parent]['end']] == ref['terminalSpan'], 'Actual source pointer/terminal span differs')
        node = old.at(rec['fields'],parent);require(node['$type'] == 'RPG.GameCore.PlayTimeline' and node['TimelineName'] == name
                and node['Type']['observedSerializedEnum'] == ref['nativeType'], 'Actual typed native source graph differs')
        src = data['sourceProofs'][ref['nativeSourceIndex']];json_node = old.at(documents[src['logicalJsonPath']],parent)
        require(json_node['$type'] == 'RPG.GameCore.PlayTimeline' and json_node['TimelineName'] == name, 'Actual archive typed terminal differs')
        old.terminal_check(bodies[ref['nativeSourceIndex']],ref,name)
    game = Path(installed_root or manifest['installedRoot']);handles={};maps={};raw_checks=field_checks=0
    try:
        for name,relative in [('GameAssembly.dll','GameAssembly.dll'),('global-metadata.dat','StarRail_Data/il2cpp_data/Metadata/global-metadata.dat')]:
            path = game/relative;proof = current['currentInputReceipts'][name]
            require(path.stat().st_size == proof['bytes'] and file_sha(path) == proof['sha256'], 'Actual current DLL/metadata changed')
            handles[name] = path.open('rb');maps[name] = mmap.mmap(handles[name].fileno(),0,access=mmap.ACCESS_READ)
        a,m = maps['GameAssembly.dll'],maps['global-metadata.dat'];receipts={}
        for check in current['functionChecks']:
            name = old.relative(check['receipt'])
            if name not in receipts:receipts[name] = old.load(directory/name)
            f = next(f for f in receipts[name]['functions'] if f['requestedVA'] == check['nativeVA'] and f['sha256'] == check['sha256'])
            raw = a[f['fileOffset']:f['fileOffset']+f['bytes']]
            require(raw.hex() == f['raw'] and sha(raw) == check['sha256'], 'Actual full native function bytes differ');raw_checks += 1
        for c in files['phase12-predicate-fields.json']['classes']:
            raw = bytes.fromhex(c['typeDefinitionRaw']);require(m[c['metadataFileOffset']:c['metadataFileOffset']+len(raw)] == raw, 'Actual predicate class metadata differs')
            for f in c['fields']:
                for mm,offset,encoded in((m,f['metadataFileOffset'],f['metadataRaw']),(a,f['typeRecordFileOffset'],f['typeRecordRaw']),(m,f['runtimeFieldOffsetFile'],f['runtimeFieldOffsetRaw'])):
                    raw = bytes.fromhex(encoded);require(mm[offset:offset+len(raw)] == raw, 'Actual declared field binding differs')
                field_checks += 1
        native = contract['nativeEvidence'];field = native['nativeDeclaredField']
        require(field['name'] == 'CompareValue' and field['candidateTypeCode'] == 6 and field['runtimeFieldOffset'] == 52,
                'Int16 current declared type/offset differs')
        for mm,offset,encoded in ((m,field['metadataFileOffset'],field['metadataRaw']),
                (a,field['typeRecordFileOffset'],field['typeRecordRaw']),(m,field['runtimeFieldOffsetFile'],field['runtimeFieldOffsetRaw'])):
            raw = bytes.fromhex(encoded);require(mm[offset:offset+len(raw)] == raw, 'Int16 actual declared field binding differs')
        function = native['currentNativeFunction'];method = a[function['fileOffset']:function['fileOffset']+function['bytes']]
        require(function['requestedVA'] == '0x19d4aeff0' and function['bytes'] == 570 and sha(method) == function['sha256'], 'Int16 actual native reader differs')
        instructions = native['currentNativeZigzagInstructions']
        require({'f6c320','e857d9d2ff','0fb7c8','d1e9','83e001','f7d8','31c8','66894634'} <= {i['bytes'] for i in instructions}, 'Int16 presence/read/zigzag/word-store proof absent')
        for instruction in instructions:
            start = int(instruction['va'],16)-int(function['requestedVA'],16);raw = bytes.fromhex(instruction['bytes'])
            require(0 <= start < start+len(raw) <= len(method) and method[start:start+len(raw)] == raw, 'Int16 actual native instruction span differs')
    finally:
        for mm in maps.values():mm.close()
        for handle in handles.values():handle.close()
    return {'wholeCachedSourceEntries':len(bodies),'wholeCachedSourceBytes':sum(map(len,bodies.values())),
            'independentTypedTerminalChecks':37,'archiveDocuments':len(documents),'actualOwnerEdges':edges,'actualCurrentNativeInputs':2,
            'fullNativeFunctionSpansRebound':raw_checks,'predicateDeclaredFieldsRebound':field_checks,
            'int16WholeSourceEntries':1,'int16NativeTerminalChecks':3,'int16DeclaredFieldBindings':3,'int16NativeFunctionBytes':570,
            'callerEditionStatus':UNKNOWN,'runtimePlaybackStatus':'UNVERIFIED','newBodies':0,'newFrozenIds':0}


def dist_check(repo, data, directory, publication_report=None):
    public,_ = old.baseline(repo);scenes = {s['id']:s for s in public['scenes']};by_scene = defaultdict(list)
    for ref in data['references']:by_scene[ref['sceneId']].append(ref)
    report = None;decoded={};markers=0
    def text_for(scene_id):
        nonlocal report
        text = (Path(directory)/'대화'/('연출-'+scene_id+'.html')).read_text('utf8')
        if '__spr(' in text or '__starrailPublicationWrite(' in text:
            if report is None:
                report = old.load(publication_report or Path(repo)/'.codex-work/publication-build-report.json')
                for shard in report.get('proofShards',{}).values():
                    url = old.unquote(shard['url']);require(url.startswith('/starrail-quests/'), 'Publication proof shard base differs')
                    require(file_sha(Path(directory)/old.relative(url[len('/starrail-quests/'):])) == shard['assetSha256'], 'Actual optimized proof shard asset differs')
            text = old.expand_proof_slots(text,report,decoded)
        return text
    for sid,refs in by_scene.items():markers += old.rendered_check(data,public,scenes[sid],refs,text_for(sid))
    previous = old.load(Path(repo)/'data/public-snapshot-native-corroboration.json');covered = {(r['sceneId'],r['referenceIndex']) for r in previous['references']+data['references']}
    remaining = [s for s in public['scenes'] if any((s['id'],i) not in covered for i in range(len(s['proof']['references'])))]
    for scene in remaining:
        parsed = old.ReaderHTML();parsed.feed(text_for(scene['id']));parsed.close()
        require(not parsed.markers and old.STALE in ''.join(parsed.text), 'Remaining unmatched source promoted or disclaimer removed')
    require(markers == 37 and len(by_scene) == 37 and len(remaining) == 110, 'Rendered extension/uncertain counts differ')
    return {'extensionReaders':37,'exactMarkers':37,'remainingUnmatchedSnapshotReaders':110,'newBodies':0}


def self_tests(repo, data):
    cases=[]
    def reject(name,fn):
        try:fn()
        except(AssertionError,KeyError,IndexError,TypeError,ValueError):cases.append(name);return
        raise AssertionError('Negative accepted: '+name)
    def mutate(name,edit):
        d=deepcopy(data);r=d['references'][0];s=d['sourceProofs'][r['nativeSourceIndex']];edit(d,r,s);reject(name,lambda:source_check(repo,d))
    for name,edit in[
        ('wrong owner',lambda d,r,s:r.__setitem__('ownerChainSha256','0'*64)),('wrong ID/rows',lambda d,r,s:r.__setitem__('sceneRowsSha256','0'*64)),
        ('wrong source',lambda d,r,s:s.__setitem__('logicalJsonPath','wrong.json')),('wrong public source index',lambda d,r,s:s.__setitem__('snapshotSourceIndex','wrong')),
        ('wrong public pointer/reference',lambda d,r,s:r.__setitem__('referenceIndex',99999)),('wrong field span',lambda d,r,s:r['fieldSpan'].__setitem__(0,r['fieldSpan'][0]+1)),
        ('wrong EOF',lambda d,r,s:s.__setitem__('consumedBytes',s['consumedBytes']-1)),('wrong root',lambda d,r,s:r.__setitem__('rootSha256','0'*64)),
        ('old pair repeated',lambda d,r,s:r.__setitem__('sceneId','snapshot-timeline-2b89de8cf37d2f31e94d')),('private path',lambda d,r,s:s.__setitem__('logicalJsonPath','D:/private')),
        ('runtime promoted',lambda d,r,s:d['evidence'].__setitem__('runtimePlaybackStatus','PASS')),('edition promoted',lambda d,r,s:d['evidence'].__setitem__('callerEditionStatus','CURRENT')),
        ('wrong domain',lambda d,r,s:d['evidence'].__setitem__('typedConsumer','RPG.GameCore.PlayVoice')),('wrong source SHA',lambda d,r,s:s.__setitem__('entrySha256','0'*64)),
        ('wrong profile',lambda d,r,s:d['evidence']['profiles']['12']['currentProfile'].__setitem__('sha256','0'*64)),('missing reference',lambda d,r,s:d['references'].pop()),
        ('new ID claimed',lambda d,r,s:d['evidence']['counts'].__setitem__('newFrozenIds',1)),('wrong old overlay pin',lambda d,r,s:d.__setitem__('oldOverlaySha256','0'*64))]:mutate(name,edit)
    public,_ = old.baseline(repo);r=data['references'][0];scene=next(s for s in public['scenes'] if s['id']==r['sceneId']);s=data['sourceProofs'][r['nativeSourceIndex']];original,_,_=old.original_pair(public,scene,r['referenceIndex'])
    text='<details id="verified-sources">'+old.CORROBORATED+' 판본 일치는 미확인 실제 재생 여부는 미확인<div data-native-corroboration="'+scene['id']+':'+str(r['referenceIndex'])+'">'+escape(' '.join([s['logicalJsonPath'],original['pointer'],s['entrySha256'],str(s['consumedBytes']),str(r['fieldSpan'][0])+'–'+str(r['fieldSpan'][1])]))+'</div></details>'
    old.rendered_check(data,public,scene,[r],text)
    reject('missing rendered marker',lambda:old.rendered_check(data,public,scene,[r],text.replace('data-native-corroboration','data-other')))
    reject('wrong rendered bytes',lambda:old.rendered_check(data,public,scene,[r],text.replace(s['entrySha256'],'wrong')))
    reject('rendered stale disclaimer',lambda:old.rendered_check(data,public,scene,[r],text+old.STALE))
    reject('rendered runtime uncertainty removed',lambda:old.rendered_check(data,public,scene,[r],text.replace('실제 재생 여부는 미확인','')))
    def uint(value):
        out=bytearray()
        while value>=128:out.append((value&127)|128);value>>=7
        out.append(value);return bytes(out)
    name='test.playable';encoded=name.encode();raw=uint(1976)+uint(6)+uint(len(encoded))+encoded+uint(8)
    ref={'terminalSpan':[0,len(raw)],'fieldSpan':[3,len(raw)-1],'mask':6,'nativeType':8};old.terminal_check(raw,ref,name)
    extra=deepcopy(ref);extra['terminalSpan'][1]+=1
    reject('native terminal trailing byte',lambda:old.terminal_check(raw+b'\0',extra,name))
    short=deepcopy(ref);short['terminalSpan'][1]-=1
    reject('native terminal truncated',lambda:old.terminal_check(raw[:-1],short,name))
    reject('native terminal wrong literal',lambda:old.terminal_check(raw,ref,'wrong.playable'))
    reject('native terminal wrong task ID',lambda:old.terminal_check(b'\0'+raw[1:],ref,name))
    changed=deepcopy(ref);changed['mask']=63
    reject('native terminal unknown mask',lambda:old.terminal_check(raw,changed,name))
    for encoded,expected in [(b'\0',0),(b'\1',-1),(b'\2',1),(b'\xfe\xff\3',32767),(b'\xff\xff\3',-32768)]:
        require(native_int16(encoded) == expected, 'Native Int16 positive boundary differs')
    for label,encoded in [('empty',b''),('truncated',b'\x80'),('trailing',b'\2\0'),('overflow',b'\x80\x80\4'),('overlong',b'\x80\0')]:
        reject('Int16 '+label,lambda encoded=encoded:native_int16(encoded))
    for label,edit in [
        ('stage promoted',lambda d,r,s:s.__setitem__('sourceCodeStage',12)),
        ('source replay changed',lambda d,r,s:d['evidence']['profiles']['13'].__setitem__('wholeSourceReplaySha256','0'*64)),
        ('Int16 code pin changed',lambda d,r,s:d['evidence']['profiles']['13']['sourceCodeReceipt'].__setitem__('sha256','0'*64)),
        ('Int16 source hash changed',lambda d,r,s:s.__setitem__('entrySha256','0'*64)),
        ('Int16 source field moved',lambda d,r,s:r['fieldSpan'].__setitem__(0,r['fieldSpan'][0]+1)),
        ('Int16 whole EOF changed',lambda d,r,s:s.__setitem__('consumedBytes',368))]:
        d=deepcopy(data);r=next(r for r in d['references'] if d['sourceProofs'][r['nativeSourceIndex']]['sourceCodeStage']==13);s=d['sourceProofs'][r['nativeSourceIndex']]
        edit(d,r,s);reject(label,lambda d=d:source_check(repo,d))
    return {'negativeCases':len(cases),'rejected':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repo',type=Path,default=SITE);parser.add_argument('--data',type=Path)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--audit',type=Path);parser.add_argument('--installed-root',type=Path)
    parser.add_argument('--stage13-audit',type=Path);parser.add_argument('--retained-code-root',type=Path)
    parser.add_argument('--dist',type=Path);parser.add_argument('--publication-report',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    repo=args.repo.resolve();path=args.data or repo/'data/snapshot-native-corroboration-extension.json';raw=path.read_bytes()
    require(sha(raw)==PAYLOAD_SHA and b'\r'not in raw,'Closed compact UTF8 LF extension bytes changed');data=json.loads(raw);refs=source_check(repo,data)
    checks={'source':{'references':len(refs),'scenes':37,'sources':7,'combinedReferences':1447,'combinedScenes':1437,'combinedSources':246,'remainingUnmatched':110,'newBodies':0,'newFrozenIds':0}}
    if args.self_test:checks['selfTests']=self_tests(repo,data)
    if args.audit:checks['actual']=audit_check(repo,data,args.audit,args.installed_root,args.stage13_audit,args.retained_code_root)
    require(not args.installed_root or args.audit,'Current native input verification requires --audit')
    require(not (args.stage13_audit or args.retained_code_root) or args.audit,'Private continuation paths require --audit')
    if args.dist:checks['dist']=dist_check(repo,data,args.dist,args.publication_report)
    out={'status':'PASS','verifierSha256':file_sha(Path(__file__)),'extensionSha256':sha(raw),'checks':checks}
    if args.report:args.report.write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps(out,ensure_ascii=False))


if __name__ == '__main__':main()
