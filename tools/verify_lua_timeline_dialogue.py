"""Independent Lua screen projection, source, owner and static HTML checks.

No producer imports, game bytecode execution, site builds or installation writes.
"""
import argparse, copy, hashlib, json, math, re, struct, sys, tarfile
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit
from verify_site import Page

SITE = Path(__file__).resolve().parents[1]
FIELDS = ('text_sub_title', 'text_main_title', 'text_bottom_title', 'text_bottom_content')
LABELS = ('부제', '제목', '하단 제목', '하단 본문')
AUDIT_SHA = '07a5b65ca270d8d54edddac9a26047aebab7f97e2d1174b59f63bb21686bb9d4'
ARCHIVE_SHA = 'e1eee10139b338e271467e1823cedb0ceba0c5c1c608771f2386639db308f02a'
SNAPSHOT_KIND = 'CALLER_SOURCE_PUBLIC_JSON_SNAPSHOT_NATIVE_EOF_BLOCKED'

def read(p): return json.loads(Path(p).read_text('utf8'))
def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)
def pointer(obj, path):
    require(path.startswith('/'), 'Invalid JSON pointer')
    for key in path.split('/')[1:]:
        key = key.replace('~1', '/').replace('~0', '~')
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj
def safe_precision(obj):
    if type(obj) is int: require(abs(obj) < 2**53, 'Unsafe public integer precision')
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key in ('pathID', 'm_PathID', 'entryHash', 'nameHash', 'textHash', 'speakerHash'):
                require(isinstance(value, str) and re.fullmatch(r'-?[0-9]+', value), 'ID/hash must be a decimal string: '+key)
            safe_precision(value)
    elif isinstance(obj, list):
        for value in obj: safe_precision(value)

@lru_cache(maxsize=None)
def source_file(name):
    p = (SITE / name).resolve()
    require(p.is_relative_to(SITE), 'Source outside site')
    raw = p.read_bytes()
    return sha(raw), json.loads(raw)

def public_checks(data, attr, deep, raw_sha=None, snapshot_bridge=None):
    require(data['schema'] == 'starrail-lua-timeline-dialogue.v1', 'Lua projection schema')
    require(data['evidence']['auditSha256'] == AUDIT_SHA, 'Unclosed source audit')
    require(data['evidence']['installedVersion'] == 'UNVERIFIED', 'Unproved installed release claim')
    if raw_sha: require(attr['evidence']['luaTimelineSha256'] == raw_sha, 'Attribution source SHA drift')
    require(not re.search(r'(?:[A-Za-z]:[/\\]|\.codex-work|inventory\.json|source_objects_folder)', json.dumps(data, ensure_ascii=False)), 'Private path in public projection')
    safe_precision(data)
    bridge = None
    if 'snapshotAuxiliaryOwnerBridgeSha256' in data['evidence']:
        if snapshot_bridge is None:
            bridge_raw = (SITE/'data/lua-snapshot-owner-bridges.json').read_bytes(); bridge = json.loads(bridge_raw)
        else:
            bridge = snapshot_bridge; bridge_raw = (json.dumps(bridge, ensure_ascii=False, separators=(',',':'))+'\n').encode()
        require(sha(bridge_raw) == data['evidence']['snapshotAuxiliaryOwnerBridgeSha256'] == '4f0e94bb85a96f92618ffa51ef45dbc040819ee34a78bb8a7ce525db12b1c138', 'Snapshot owner bridge SHA drift')
        from verify_timeline_owner_bridges import bridge_public_checks
        bridge_public_checks(data, bridge, 'lua')
    aliases = read(SITE/'data/aliases.json')
    corpus = {}
    for tid, join in data['joins'].items():
        require(re.fullmatch(r'[1-9][0-9]*', tid) and 0 < int(tid) < 2**32, 'Talk lookup ID domain')
        src = join['preservedSource']
        require(src['file'].startswith('data/dialogues/') and '..' not in src['file'].split('/'), 'Unsafe Korean source')
        digest, obj = source_file(src['file']); row = pointer(obj, src['pointer'])
        require(digest == src['sha256'] and row['talk_id'] == int(tid), 'Preserved original SHA/ID drift')
        require(row['text'] == join['text'] and str(row['hash']) == join['textHash'] and str(row['speaker_hash']) == join['speakerHash'] and row['voice'] == join['voice'], 'Preserved Korean fields drift')
        table, text = join['tableRecord'], join['textRecord']
        require(table['TalkSentenceID'] == int(tid) and str(table['TalkSentenceText']['Hash']) == join['textHash'] == str(text['hash']), 'Talk table/TextMap join drift')
        require(text['raw'] == join['raw'] and table.get('VoiceID', 0) == join['voice'] and str(table.get('TextmapTalkSentenceName', {}).get('Hash', 0)) == join['speakerHash'], 'Raw/hash/voice domain drift')
        if join['speakerHash'] != '0': require(join['speakerRecord'] and str(join['speakerRecord']['hash']) == join['speakerHash'], 'Missing speaker original')
        corpus[int(tid)] = row
    asset_key = lambda s: s.casefold().removeprefix('assets/asbres/')
    deep_by_source = {asset_key(s['source']): s for s in deep['scenes'] if s.get('kind') != 'NATIVE_CHOICES'}
    expected_urls = {}; scene_ids = set(); used_ids = set(); references = set(); rows = 0
    for scene in data['scenes']:
        require(scene['id'] == 'lua-timeline-'+sha(scene['source'].encode())[:16] and scene['id'] not in scene_ids, 'Scene identity/collision')
        scene_ids.add(scene['id']); require(scene['kind'] == 'LUA_ARGUMENT_SCREEN_TEXT', 'Scene screen kind')
        proof = scene['proof']; require(proof['container']['key'] == scene['source'] and str(proof['container']['pathID']) == proof['root']['pathID'] and proof['container']['fileID'] == 0, 'Actual root/container identity')
        require(scene['title'] == data['joins'][str(scene['rows'][0]['talkId'])]['text'], 'Screen title original drift')
        require(proof['root']['class'] == 'TimelineAsset', 'Typed Timeline root')
        require([r['slot'] for r in scene['rows']] == [1, 2, 3, 4], 'Four slots/source order changed')
        canonical = {o['canonicalMission'] for o in scene['owners']}
        snapshot = proof.get('ownerBridge') == 'EXACT_PUBLIC_SNAPSHOT_AUXILIARY_ROOT_AND_CALLER'
        if snapshot:
            require(bridge is not None and scene['id'] in bridge['scenes'], 'Missing exact snapshot owner bridge')
            expected_owner = 'ONE_EXPLICIT_SNAPSHOT_OWNER' if len(canonical) == 1 else 'MULTIPLE_EXPLICIT_SNAPSHOT_OWNERS'
        else:
            expected_owner = 'ONE_EXPLICIT_OWNER' if len(canonical) == 1 else 'MULTIPLE_EXPLICIT_OWNERS' if canonical else 'UNOWNED_NATIVE_TIMELINE'
        require(scene['ownerStatus'] == expected_owner and bool(proof['references']) == bool(canonical), 'Owner status/reference mismatch')
        for owner in scene['owners']:
            require(owner['canonicalMission'] == aliases.get(owner['mission'], owner['mission']), 'Canonical owner alias drift')
            _, doc = source_file('data/documents/'+owner['canonicalMission']+'.json')
            require(owner['mission'] in doc.get('missionParts', [doc['id']]) and owner['title'] == doc['title'], 'Mission membership/title drift')
        if canonical and not snapshot:
            ds = deep_by_source.get(asset_key(scene['source'])); require(ds is not None, 'Owned scene lacks independent deep root')
            require(ds['proof']['root'] == proof['root'] and ds['proof']['receipt']['cabSha256'] == proof['receipt']['cabSha256'] and ds['owners'] == scene['owners'], 'Owner copied from a different actual root/CAB')
        for ref in proof['references']:
            index = ref['sourceIndex']; references.add(index); source = data['sourceProofs'][index]
            require(source == (bridge['sourceProofs'][index] if snapshot else deep['sourceProofs'][index]), 'Independent owner source proof drift')
            require(source['mission'] in {o['mission'] for o in scene['owners']}, 'Reference belongs to another owner')
            span = ref['fieldSpan']
            if snapshot:
                require(span is None and ref['callerSourceKind'] == SNAPSHOT_KIND and source['callerSourceKind'] == SNAPSHOT_KIND and ref['nativeCallerWholeEOF'] is False and source['nativeCallerWholeEOF'] is False and ref['nativeInstalledCallerClaim'] is False and source['nativeInstalledCallerClaim'] is False and source['nativeCallerFieldSpan'] is None, 'Snapshot/native caller proof boundary')
            else:
                require(span['pointer'] == ref['pointer'] and 0 <= span['start'] < span['end'] <= source['consumedBytes'], 'Timeline field byte bounds')
            require(ref['context']['typedContainer']['type'] == 'RPG.GameCore.PlayTimeline' and ref['pointer'] == ref['context']['typedContainer']['pointer']+'/TimelineName', 'Typed terminal caller domain')
        clip_identity = None
        for row in scene['rows']:
            tid, slot, arg = row['talkId'], row['slot'], row['argument']; rows += 1; used_ids.add(tid)
            require(type(tid) is int and tid in corpus and row['role'] == 'SCREEN_TEXT' and row['uiField'] == FIELDS[slot-1], 'Screen slot/role/domain')
            require(row['anchor'] == f'lua-screen-{tid}-{slot}', 'Screen anchor identity')
            require(row['object']['class'] == 'ShowFateShowCaptionDialogClip' and row['track']['class'] == 'ShowDialogTrack', 'Typed clip/track class')
            identity = (row['object']['pathID'], row['track']['pathID'], row['trackClipIndex'], row['start'], row['duration'])
            if clip_identity is None: clip_identity = identity
            require(identity == clip_identity and row['parentRoute'][0] == row['track']['pathID'] and row['parentRoute'][-1] == proof['root']['pathID'], 'Clip/track/root route differs')
            require(all(type(row[k]) in (int, float) and math.isfinite(row[k]) for k in ('start', 'duration')) and row['start'] >= 0 and row['duration'] > 0, 'Invalid clip timing')
            tokens = arg['raw'].split('|'); require(len(tokens) == 4 and arg['tokenIndex'] == slot-1 and arg['token'] == str(tid) == tokens[slot-1], 'UIParam token/slot/ID drift')
            require(all(t.isascii() and t.isdigit() and 0 < int(t) < 2**32 for t in tokens), 'UInt32 token domain')
            start = sum(len(t.encode())+1 for t in tokens[:slot-1]); end = start+len(tokens[slot-1].encode()); field = arg['serializedField']; a, z = field['span']
            require(field['field'] == 'ShowFateShowCaptionDialogClip.UIParam' and field['value'] == arg['raw'] and 0 <= a < z == row['object']['byteSize'] and z-a == (4+len(arg['raw'].encode())+3)//4*4, 'Whole UTF8 string field/EOF drift')
            require(arg['tokenUtf8SpanRelativeToString'] == [start, end] and arg['tokenByteSpanRelativeToObject'] == [a+4+start, a+4+end], 'UTF8 token byte span drift')
            call = row['luaConsumer']['call']; receiver = ['member', ['member', ['parameter', 0], '_binder'], row['uiField']]
            require(call['function'] == ['method', receiver, 'SafeSetTextID'] and call['arguments'] == [receiver, ['index', ['member', ['parameter', 0], '_text_id_list'], ['number', str(slot), None]]] and call['resultCount'] == 0, 'Actual Lua argument expression drift')
            require(row['luaConsumer']['prototype'] == 4 and row['luaConsumer']['methodRole'] == '_setup_view' and call['end']-call['start'] == 4 and 0 <= call['start'] < call['end'] <= row['luaConsumer']['module']['entryLength'], 'Lua CALL byte/prototype bounds')
            native = row['nativeConsumer']; require(native['lookupClass'] == 'RPG.GameCore.TalkSentenceConfigExcelTable' and native['lookupMethod'] == 'GetData' and native['textFieldClass'] == 'RPG.GameCore.TalkSentenceConfigRow' and native['textField'] == 'TalkSentenceText' and native['runtimeOffset'] == 40 and native['copyBytes'] == 16 and native['outputElement'] == 'RPG.Client.TextID' and native['screenCall'] == 'SafeSetTextID', 'Native consumer domain drift')
            url = '대화/연출-'+scene['id']+'.html#'+row['anchor']; require(url not in expected_urls, 'Duplicate inverse URL'); expected_urls[url] = (str(tid), scene['source'], row['role'])
    require(references == set(data['sourceProofs']), 'Unused/missing owner proof')
    require(used_ids == set(corpus) and data['counts']['scenes'] == len(scene_ids) and data['counts']['rows'] == rows and data['counts']['distinctTalkIds'] == len(used_ids) and data['counts']['roles'] == {'SCREEN_TEXT': rows}, 'Projected count drift')
    require(data['counts']['frozenIds'] == attr['counts']['luaFrozenAttributedIds'] and attr['counts']['luaScreenReaderIds'] == len(used_ids), 'Lua attribution count mismatch')
    observed = {}
    for tid, links in attr['readerLinks'].items():
        for link in links:
            if link['url'].startswith('대화/연출-lua-timeline-'):
                require(link['url'] not in observed, 'Duplicate attribution URL'); observed[link['url']] = (tid, link['source'], link['role'])
    require(observed == expected_urls, 'Exact inverse attribution/source/role drift')
    return corpus

def archive_checks(data, archive):
    h = hashlib.sha256()
    with archive.open('rb') as f:
        for block in iter(lambda: f.read(16*1024*1024), b''): h.update(block)
    require(h.hexdigest() == ARCHIVE_SHA, 'Structure archive snapshot SHA drift')
    needed = {p['logicalJsonPath'] for p in data['sourceProofs'].values()}
    for proof in data['sourceProofs'].values():
        needed.update(e[k] for e in proof['ownerChain'] for k in ('source', 'tableSource') if k in e)
    loaded = {}
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            name = member.name.split('/', 1)[-1]
            if name not in needed: continue
            require(member.isfile() and 0 < member.size < 64*1024*1024, 'Owner archive member boundary')
            blob = tar.extractfile(member).read(); loaded[name] = (sha(blob), json.loads(blob)); needed.remove(name)
            if not needed: break
    require(not needed, 'Missing archived owner/terminal source: '+str(needed))
    checked = 0; terminals = 0; missions = set()
    for scene in data['scenes']:
        for ref in scene['proof']['references']:
            proof = data['sourceProofs'][ref['sourceIndex']]; prior_target = None; owner = None
            for edge in proof['ownerChain']:
                if 'source' not in edge: continue
                digest, obj = loaded[edge['source']]; require(digest == edge['sourceSha256'], 'Owner source archive hash drift'); value = pointer(obj, edge['pointer']); checked += 1
                if prior_target: require(edge['source'] == prior_target, 'Disconnected owner chain')
                if edge['kind'] == 'EXPLICIT_MAIN_MISSION_ID':
                    require(value == edge['missionId'] and edge['canonicalMissionId'] == int(proof['mission'].split('-')[1]), 'Actual owner/canonical ID mismatch'); owner = 'quest-'+str(value); missions.add(owner)
                elif edge['kind'] == 'EXPLICIT_JSON_PATH': require(value == edge['target'], 'Owner graph path mismatch'); prior_target = edge['target']
                elif edge['kind'] == 'EXPLICIT_PERFORMANCE_LOOKUP':
                    table_hash, table = loaded[edge['tableSource']]; require(table_hash == edge['tableSha256'] and value == edge['performanceId'] == pointer(table, edge['idPointer']) and pointer(table, edge['pathPointer']) == edge['target'], 'Typed performance table lookup mismatch')
                    task = pointer(obj, edge['pointer'].rsplit('/', 1)[0]); require(task['$type'] == 'RPG.GameCore.TriggerPerformance' and task['PerformanceType'] == edge['performanceType'], 'Performance task domain mismatch'); prior_target = edge['target']
                else: raise ValueError('Unsupported owner edge: '+edge['kind'])
            require(owner == proof['mission'] and prior_target == proof['logicalJsonPath'], 'Owner chain terminal mismatch')
            terminal_hash, terminal = loaded[proof['logicalJsonPath']]; task = pointer(terminal, ref['context']['typedContainer']['pointer']); name = pointer(terminal, ref['pointer'])
            if proof.get('callerSourceKind') == SNAPSHOT_KIND:
                require(terminal_hash == proof['sourceSha256'] and task == ref['snapshotTask'], 'Snapshot caller source SHA/task differs')
                require(ref['fieldSpan'] is None and proof['nativeCallerFieldSpan'] is None and proof['nativeCallerWholeEOF'] is False and proof['nativeInstalledCallerClaim'] is False and ref['nativeCallerWholeEOF'] is False and ref['nativeInstalledCallerClaim'] is False, 'Snapshot falsely asserts native caller/span')
            require(task['$type'] == 'RPG.GameCore.PlayTimeline' and isinstance(name, str) and ('assets/asbres/'+name).casefold() == scene['source'].casefold(), 'Terminal actual TimelineName/typed caller mismatch'); terminals += 1
    return {'ownerEdges': checked, 'terminalTimelineCalls': terminals, 'missionParts': sorted(missions), 'archiveFiles': len(loaded), 'archiveSha256': h.hexdigest()}

class LuaPage(Page):
    def __init__(self): super().__init__(); self.rows = []; self.order = []; self.slot_labels = []; self.label_active = False; self.proofs = []; self.owner_proofs = []
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs); a = dict(attrs)
        if 'data-lua-talk' in a: self.rows.append((a['data-lua-talk'], a.get('data-caption-slot'), a.get('data-lua-role')))
        if tag == 'p' and 'original-body' in a.get('class', '').split(): self.order.append(a.get('id'))
        if tag == 'span' and 'rw-source-speaker' in a.get('class', '').split(): self.slot_labels.append(''); self.label_active = True
        if 'data-lua-clip-proof' in a: self.proofs.append(a['data-lua-clip-proof'])
        if 'data-lua-owner-proof' in a: self.owner_proofs.append(a['data-lua-owner-proof'])
    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == 'span': self.label_active = False
    def handle_data(self, text):
        super().handle_data(text)
        if self.label_active: self.slot_labels[-1] += text

def dist_checks(data, corpus, dist):
    report = dist.parent/'.codex-work/publication-build-report.json'; expand = None
    if report.exists():
        from optimize_publication import expansion_function
        expand = expansion_function(read(report))
    @lru_cache(maxsize=None)
    def page(relative):
        path = (dist/relative).resolve(); require(path.is_relative_to(dist.resolve()), 'HTML path boundary')
        text = path.read_text('utf8'); p = LuaPage(); p.feed(text); require(not p.duplicates, 'Duplicate static HTML anchors'); return text, p
    for scene in data['scenes']:
        raw, p = page('대화/연출-'+scene['id']+'.html'); require('original' in p.ids and 'verified-sources' in p.ids, 'Missing static reader/disclosure anchor')
        require(p.rows == [(str(r['talkId']), str(r['slot']), 'SCREEN_TEXT') for r in scene['rows']] and p.order == [r['anchor'] for r in scene['rows']], 'Static rows/slots/source order drift')
        require(p.slot_labels == ['화면 문구 · '+label for label in LABELS], 'Static screen position labels drift')
        for row in scene['rows']:
            tid = row['talkId']; require(p.original.get(row['anchor']) == corpus[tid]['text'], 'Static original Korean differs')
            source = data['joins'][str(tid)]['preservedSource']['file']; target = '대사/'+Path(source).stem+'.html'; url = '/starrail-quests/'+target+'#talk-'+str(tid)
            require(url in p.links and 'talk-'+str(tid) in page(target)[1].ids, 'Original return link/target missing')
        for owner in scene['owners']:
            target = '문서/'+owner['canonicalMission']+'.html'; require('/starrail-quests/'+target+'#deep-timeline-originals' in p.links, 'Static owner return link missing')
            _, owner_page = page(target); require('deep-timeline-originals' in owner_page.ids and '/starrail-quests/대화/연출-'+scene['id']+'.html' in owner_page.links, 'Owner inverse reader link missing')
        expanded = expand(raw) if expand else raw; proof = LuaPage(); proof.feed(expanded)
        require(proof.proofs == [r['anchor'] for r in scene['rows']] and set(proof.owner_proofs) == {r['sourceIndex'] for r in scene['proof']['references']}, 'Expanded technical proof references drift')
        needles = [scene['source'], scene['proof']['receipt']['blockSha256'], scene['proof']['receipt']['cabSha256']]
        for row in scene['rows']:
            needles += [row['argument']['raw'], row['uiField'], row['luaConsumer']['module']['entrySha256'], row['nativeConsumer']['lookupClass'], data['joins'][str(row['talkId'])]['textHash']]
        require(all(value in expanded for value in needles), 'Expanded technical provenance missing')
    return {'staticHtmlScenes': len(data['scenes']), 'staticOriginalRows': len(corpus), 'publicationExpanded': bool(expand)}

def audit_checks(data, path):
    raw = path.read_bytes(); require(sha(raw) == data['evidence']['auditSha256'] == AUDIT_SHA, 'Audit bytes SHA drift'); audit = json.loads(raw)
    require(data['evidence']['officialKorean'] == audit['officialKorean'] and data['evidence']['sourceGuards'] == audit['sourceGuards'], 'Projected source/version evidence differs')
    cohort_path = path.parent.parent/'frozen-cohorts.json'; cohort_raw = cohort_path.read_bytes(); cohort = json.loads(cohort_raw)
    require(sha(cohort_raw) == data['evidence']['frozenCohortSha256'] == audit['cohortFrozenSha256'] and data['counts']['frozenIds'] == len(set(map(int, data['joins'])) & set(cohort['starrail']['ids'])), 'Frozen cohort SHA/ID partition drift')
    for name, digest in data['evidence']['sourceGuards'].items(): require(sha((path.parent/name).read_bytes()) == digest, 'Private source guard drift: '+name)
    require(audit['ownerProofs'] == {k:v for k,v in data['sourceProofs'].items() if v.get('callerSourceKind') != SNAPSHOT_KIND}, 'Four original native owner source proofs differ')
    rows = {(r['route']['rootContainer']['key'], r['captionSlot']): r for r in audit['readableDelta']}
    game = Path('D:/game/starrail/HonkaiStarRail/games/Star Rail Games')
    blocks = set(); inventories = {}; scripts_checked = set()
    canaries = read(path.parent/'fate-current-cab-canaries.json')
    cab_guards = {c['candidate']['cab']: c for c in canaries['canaries']}
    fields = read(path.parent/'fate-exact-runtime-fields.json')
    assembly = (game/'GameAssembly.dll').read_bytes()
    metadata = (game/'StarRail_Data/il2cpp_data/Metadata/global-metadata.dat').read_bytes()
    for source in fields['files']:
        if source['path'].endswith('GameAssembly.dll'): require(sha(assembly) == source['sha256'], 'Current native assembly SHA drift')
        if source['path'].endswith('global-metadata.dat'): require(sha(metadata) == source['sha256'], 'Current native metadata SHA drift')
    for cls in fields['classes']:
        for field in cls['fields']:
            require(metadata[field['metadataFileOffset']:field['metadataFileOffset']+8].hex() == field['metadataRaw'], 'Current native field metadata bytes')
            offset = field['runtimeFieldOffsetFile']; require(metadata[offset:offset+4].hex() == field['runtimeFieldOffsetRaw'], 'Current runtime field offset bytes')
    native_functions = read(path.parent/'special-fate-native.json')['functions']
    for f in native_functions: require(sha(assembly[f['fileOffset']:f['fileOffset']+f['bytes']]) == f['sha256'], 'Current caption native function bytes')
    for scene in data['scenes']:
        for row in scene['rows']:
            source = rows[(scene['source'], row['slot'])]; route = source['route']
            require(str(row['talkId']) == source['joinedTalkID'] and row['argument'] == source['uiParamTokenProof'] and row['luaConsumer'] == source['luaConsumerProof'] and row['nativeConsumer'] == source['nativeConsumerProof'], 'Source argument/consumer projection differs')
            require(row['object'] == route['clipObject'] and row['track'] == route['trackObject'] and scene['proof']['root'] == route['rootObject'] and row['start'] == route['timelineClip']['m_Start'] and row['duration'] == route['timelineClip']['m_Duration'], 'Actual source object/timing differs')
            refs = []
            for ref in source.get('sourceReferences', []):
                projected = {'sourceIndex': str(ref['sourceIndex']), 'pointer': ref['pointer'], 'fieldSpan': ref['timelineFieldByteProof'], 'context': ref['context']}
                if projected not in refs: refs.append(projected)
            require([ref for ref in scene['proof']['references'] if ref.get('callerSourceKind') != SNAPSHOT_KIND] == refs, 'Actual original native pointer/byte-span/condition reference differs')
            receipt = scene['proof']['receipt']; require(receipt == {k: source['sourceReceipt'][k] for k in receipt}, 'Actual native pack/CAB receipt differs')
            if receipt['blockFile'] not in blocks:
                require(re.fullmatch(r'[0-9a-f]{32}\.block', receipt['blockFile']), 'Native block filename boundary')
                require(sha((game/'StarRail_Data/StreamingAssets/Asb/Windows'/receipt['blockFile']).read_bytes()) == receipt['blockSha256'], 'Current installed native pack SHA'); blocks.add(receipt['blockFile'])
            folder = path.parent/'cab-replay'/scene['proof']['receipt']['cab']
            if receipt['cab'] not in inventories:
                invraw = (folder/'inventory.json').read_bytes(); require(sha(invraw) == cab_guards[receipt['cab']]['inventorySha256'], 'Current CAB inventory identity')
                inv = json.loads(invraw); require(inv['sourceSha256'] == receipt['blockSha256'] and len(inv['cabs']) == 1 and inv['cabs'][0]['sha256'] == receipt['cabSha256'], 'Current extracted CAB/source identity')
                inventories[receipt['cab']] = {str(obj['pathID']): obj for obj in inv['cabs'][0]['objects']}
            for obj in (row['object'], row['track'], scene['proof']['root']):
                b = (folder/(scene['proof']['receipt']['cab']+'-'+obj['pathID']+'.bin')).read_bytes(); require(len(b) == obj['byteSize'] and sha(b) == obj['sha256'], 'Current object raw bytes drift')
                script_id = obj['scriptPointer']['m_PathID']; script_key = (receipt['cab'], script_id)
                if script_key not in scripts_checked:
                    script = inventories[receipt['cab']][script_id]
                    require(script['classID'] == 115 and script['script']['m_ClassName'] == obj['class'], 'Actual MonoScript class binding')
                    # Approved Probe writes 114 raw objects; 115 raw hashes and
                    # names reside in its pinned CAB inventory receipt.
                    require(re.fullmatch(r'[0-9a-f]{64}', script['sha256']) and script['byteSize'] > 0, 'MonoScript raw hash receipt')
                    scripts_checked.add(script_key)
            b = (folder/(scene['proof']['receipt']['cab']+'-'+row['object']['pathID']+'.bin')).read_bytes(); offset = 0
            def take(n):
                nonlocal offset
                require(0 <= n <= len(b)-offset, 'Clip EOF boundary'); value = b[offset:offset+n]; offset += n; return value
            def string():
                n = struct.unpack('<i', take(4))[0]; require(0 <= n <= len(b)-offset, 'Clip string size'); value = take(n).decode('utf8'); pad = (-offset)%4; require(take(pad) == bytes(pad), 'Clip string padding'); return value
            require(struct.unpack('<iq', take(12)) == (0, 0) and take(4) == bytes.fromhex('01000000'), 'Clip MonoBehaviour base')
            file_id, script = struct.unpack('<iq', take(12)); require(file_id == 0 and str(script) == row['object']['scriptPointer']['m_PathID'], 'Current clip MonoScript')
            object_name = next(f['value'] for f in route['clipFields'] if f['field'] == 'MonoBehaviour.m_Name')
            require(string() == object_name and string() == 'Ui.Fate.Performance.FateShowCaptionDialog', 'Whole typed caption clip')
            require(offset == row['argument']['serializedField']['span'][0] and string() == row['argument']['raw'] and offset == len(b), 'Actual UIParam full-field EOF')
            a, z = row['argument']['tokenByteSpanRelativeToObject']; require(b[a:z].decode() == str(row['talkId']), 'Actual token source byte value')
    # Independent closed source verifier: static decoders and original tables only.
    sys.dont_write_bytecode = True; sys.path.insert(0, str(path.parent))
    from luau4_reader import decode, VM_SHA, VM_PROOF_SHA
    from static_flow import analyze
    modules = {}; lua_root = Path('D:/game/starrail/HonkaiStarRail/games/Star Rail Games/StarRail_Data/StreamingAssets/Lua/Windows')
    for scene in data['scenes']:
        for row in scene['rows']:
            module = row['luaConsumer']['module']; key = module['entryHash']
            if key not in modules:
                pack = (lua_root/module['file']).read_bytes(); b = pack[module['entryOffset']:module['entryOffset']+module['entryLength']]; require(sha(b) == module['entrySha256'] and hashlib.md5(b).hexdigest() == module['entryMd5'], 'Current caller raw chunk SHA/MD5'); modules[key] = decode(b)
            d = modules[key]; flow = analyze(d['prototypes'][row['luaConsumer']['prototype']], d['prototypes']); require(row['luaConsumer']['call'] in flow['calls'], 'Current typed CALL argument drift')
    sys.path.insert(0, str(Path('D:/game/skills/starrail-korean-library/starrail-korean-library/scripts')))
    from binary import decode_table, decode_textmap
    official = data['evidence']['officialKorean']; root = Path('D:/game/.codex-work/starrail-source-resume/official-input-audit/official-4.6.0-design'); table = official['talkTable']; pack = (root/table['file']).read_bytes(); require(sha(pack) == table['sha256'], 'Official talk pack SHA'); entry = pack[table['offset']:table['offset']+table['length']]; require(sha(entry) == table['entrySha256'], 'Talk table entry SHA')
    schema = table['schema']
    records = decode_table(entry, schema); require(len(records) == table['rows'], 'Whole talk table count/EOF'); wanted = set(data['joins']); byid = {str(r['TalkSentenceID']): r for r in records if str(r.get('TalkSentenceID')) in wanted}
    kr = (root/'kr'/official['koreanPack']['file']).read_bytes(); require(sha(kr) == official['koreanPack']['sha256'], 'Official Korean pack SHA'); text_entry = official['entry']; entry = kr[text_entry['offset']:text_entry['offset']+text_entry['length']]; require(sha(entry) == text_entry['sha256'], 'Official Korean entry SHA'); texts = decode_textmap(entry); require(len(texts) == text_entry['rows'], 'Whole Korean TextMap count/EOF'); byhash = {str(t['hash']): t for t in texts if str(t['hash']) in {j['textHash'] for j in data['joins'].values()}}
    def hashes_as_strings(obj):
        if isinstance(obj, dict): return {k: str(v) if k.lower() in ('hash', 'legacy') else hashes_as_strings(v) for k,v in obj.items()}
        if isinstance(obj, list): return [hashes_as_strings(v) for v in obj]
        return obj
    for tid, join in data['joins'].items(): require(hashes_as_strings(byid[tid]) == join['tableRecord'] and hashes_as_strings(byhash[join['textHash']]) == join['textRecord'], 'Current official row/raw Korean record drift')
    return {'auditSourceRows': sum(len(s['rows']) for s in data['scenes']), 'currentNativePacks': len(blocks), 'currentCABs': len(inventories), 'pinnedMonoScriptRawHashReceipts': len(scripts_checked), 'nativeFunctionByteRanges': len(native_functions), 'luaModules': len(modules), 'installedVmSha256': VM_SHA, 'installedVmMapSha256': VM_PROOF_SHA, 'officialKoreanRows': len(wanted)}

def self_tests(data, attr, deep):
    mutations = []
    def changed(name, change):
        d, a = copy.deepcopy(data), copy.deepcopy(attr); change(d, a)
        try: public_checks(d, a, deep)
        except (ValueError, KeyError, IndexError, TypeError): mutations.append(name)
        else: raise ValueError('Semantic mutation accepted: '+name)
    changes = [('slot', lambda d,a:d['scenes'][0]['rows'][0].update(slot=2)), ('token', lambda d,a:d['scenes'][0]['rows'][0]['argument'].update(token='1')), ('ID', lambda d,a:d['scenes'][0]['rows'][0].update(talkId=1)), ('raw', lambda d,a:d['joins'][next(iter(d['joins']))].update(raw='changed')), ('hash', lambda d,a:d['joins'][next(iter(d['joins']))].update(textHash='1')), ('owner', lambda d,a:d['scenes'][0]['owners'][0].update(mission='quest-1')), ('private path', lambda d,a:d['evidence'].update(private='D:/private/input')), ('64-bit precision', lambda d,a:d['scenes'][0]['rows'][0]['object'].update(pathID=9223372036854775807)), ('source ordering', lambda d,a:d['scenes'][0]['rows'].reverse()), ('wrong native field', lambda d,a:d['scenes'][0]['rows'][0]['nativeConsumer'].update(runtimeOffset=24)), ('wrong byte span', lambda d,a:d['scenes'][0]['rows'][0]['argument'].update(tokenByteSpanRelativeToObject=[117,125])), ('Lua arg slot', lambda d,a:d['scenes'][0]['rows'][0]['luaConsumer']['call']['arguments'][1][2].__setitem__(1,'4'))]
    for name, change in changes: changed(name, change)
    def duplicate(d, a):
        key = str(d['scenes'][0]['rows'][0]['talkId']); link = next(x for x in a['readerLinks'][key] if x['url'].startswith('대화/연출-lua-timeline-')); a['readerLinks'][key].append(copy.deepcopy(link))
    changed('duplicate inverse link', duplicate)
    return mutations

def verify(args):
    raw = (SITE/'data/lua-timeline-dialogue.json').read_bytes(); data = json.loads(raw); attr = read(SITE/'data/deep-dialogue-attribution.json'); deep = read(SITE/'data/deep-timeline-dialogue.json')
    corpus = public_checks(data, attr, deep, sha(raw)); result = {'status': 'PASS', 'schema': data['schema'], 'projectionSha256': sha(raw), 'scenes': len(data['scenes']), 'rows': len(corpus), 'owners': sorted({o['mission'] for s in data['scenes'] for o in s['owners']})}
    if args.self_test: result['semanticMutationRejections'] = self_tests(data, attr, deep)
    if args.audit: result['audit'] = audit_checks(data, args.audit)
    if args.archive: result['archive'] = archive_checks(data, args.archive)
    if args.dist: result['dist'] = dist_checks(data, corpus, args.dist)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--audit', type=Path); parser.add_argument('--archive', type=Path); parser.add_argument('--dist', type=Path); parser.add_argument('--self-test', '--selftest', action='store_true', dest='self_test'); verify(parser.parse_args())
