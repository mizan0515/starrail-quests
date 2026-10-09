"""Add the independently audited native-owner Timeline cohort to the reader.

Private raw inputs remain outside the repository. The existing public-JSON
cohort is preserved; its typed clip projector is reused with an explicit native
ownership seed and contexts decoded from the official binary source.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from build_timeline_mission_dialogue import project, read, sha, SITE

OWNER = 'quest-4010146'
BASE = 'https://autopatchos.starrails.com/design_data/V4.6Live/output_16707949_49849fe93fe6_7e5dfd5e6cd1a8/client/Windows'


def public_edges(manifest):
    edges = []
    for raw in manifest['edges']:
        edge = {k: deepcopy(raw[k]) for k in ('kind', 'source', 'sourceSha256', 'pointer', 'value',
                    'target', 'tableSource', 'tableSha256', 'rowPointer', 'row', 'nameHash',
                    'packSha256', 'packOffset', 'packLength', 'fullFieldEOF',
                    'PerformanceType', 'PerformanceTypeLabel', 'PerformanceID') if k in raw}
        if 'pack' in raw:
            edge['packFile'] = Path(raw['pack']).name
            edge['sourceUrl'] = BASE + '/' + edge['packFile']
        if 'fieldSpan' in raw:
            edge['fieldSpan'] = {k: raw['fieldSpan'][k] for k in ('start', 'end', 'pointer')}
        if 'publicBlob' in raw:
            edge['sourceUrl'] = raw['publicBlob']
            edge['registeredShards'] = raw['nativeShardContract']['actualShardNames']
        edges.append(edge)
    seed = edges[0]
    assert seed['kind'] == 'EXPLICIT_NATIVE_MAIN_MISSION_ID' and seed['value'] == 4010146
    doc = SITE / 'data/documents/quest-4010146.json'
    assert read(doc)['id'] == OWNER
    seed.update(missionId=4010146, canonicalMissionId=4010146,
                membershipSource='data/documents/quest-4010146.json',
                membershipSha256=sha(doc), membershipPointer='/id')
    return edges


def message_link(receipt):
    assert receipt['status'] == 'EXACT_NATIVE_OWNER_CONFIG_MESSAGE_ASSOCIATION_PASS'
    assert receipt['owner'] == OWNER and receipt['role'] == 'CONFIG_MESSAGE_ASSOCIATION_FINISH_DATA'
    proof = []
    for raw in receipt['associationEdges']:
        edge = {k: deepcopy(raw[k]) for k in ('kind', 'pointer', 'value', 'submissionPointer',
                'submissionID', 'target', 'fullFieldsEOF', 'taskPointer', 'task', 'trigger',
                'tableSource', 'tableSha256', 'rowPointer', 'row', 'messageSectionID', 'identity') if k in raw}
        descriptor = raw.get('input') or (raw.get('source') if isinstance(raw.get('source'), dict) else None)
        if descriptor:
            edge['source'] = descriptor.get('literal', descriptor.get('logical'))
            edge['sourceSha256'] = descriptor['entrySha256']
            edge['packFile'] = Path(descriptor.get('packPath', descriptor.get('inputPack'))).name
            edge['packSha256'] = descriptor['packSha256']
            match = descriptor.get('catalogMatches', [{}])[0]
            edge['packOffset'] = descriptor.get('offset', match.get('offset'))
            edge['packLength'] = descriptor.get('length', match.get('length'))
            edge['sourceUrl'] = BASE + '/' + edge['packFile']
        elif isinstance(raw.get('source'), str):
            edge['source'] = raw['source']
        if 'tableSource' in raw:
            edge['sourceUrl'] = 'https://github.com/DimbreathBot/TurnBasedGameData/blob/' + raw['archiveCommit'] + '/' + raw['tableSource']
        if 'fieldSpan' in raw:
            edge['fieldSpan'] = {k: raw['fieldSpan'][k] for k in ('pointer', 'start', 'end')}
        proof.append(edge)
    source = SITE / 'data/documents/message-1508501.json'; document = read(source)
    assert sha(source) == receipt['associationEdges'][-1]['document']['sha256']
    assert document['source'] == 'MessageSectionConfig:1508501' and document['count'] == 26
    return {'id': document['id'], 'title': '달빛 아래의 갈대의 메시지', 'url': document['url'] + '#original',
            'documentSha256': sha(source), 'role': receipt['role'], 'runtimePlayback': 'UNVERIFIED',
            'sourceEdges': proof, 'excerpt': document['sections'][0]['rows'][1]['text']}


def main(args):
    evidence, joins, contexts, manifest, relations = map(read, (args.evidence, args.joins,
                                                   args.contexts, args.owner, args.relations))
    assert evidence['koreanJoinOutput']['sha256'] == sha(args.joins)
    assert evidence['contextsOutput']['sha256'] == sha(args.contexts)
    assert manifest['status'] == 'NATIVE_OWNER_TO_TYPED_DS_AND_12_EXACT_CABS_PASS'
    assert manifest['owner'] == OWNER and len(manifest['edges']) == 5
    edges = public_edges(manifest)
    relation_map = {r['timelineName']: r for r in relations['markerOptionRelations']}
    audit, normalized = deepcopy(evidence), deepcopy(contexts)
    assert all(len(t['owners']) == 1 and t['ownerStatus'] == 'ONE_EXPLICIT_OWNER' for t in audit['timelines'])
    audit['counts']['multiOwnerTimelines'] = 0
    for timeline in audit['timelines']:
        assert timeline['owners'][0]['mission'] == OWNER
        timeline['owners'][0]['ownerChain'] = deepcopy(edges)
    for context in normalized['timelines']:
        for owner in context['owners']:
            assert owner['originalOwnerTriggerContextStatus'] == 'UNAVAILABLE_EXACT_ARCHIVE_SOURCE'
            owner['originalOwnerTrigger'] = owner['nativeOriginalOwnerTrigger']
            trigger = owner['originalOwnerTrigger']
            trigger['sourceEvidence']['sha256'] = trigger['sourceEvidence']['entrySha256']
        for marker in context['simpleTalkMarkers']:
            if marker['nonzero']:
                relation = relation_map[context['timelineName']]
                assert relation['referenceOptionTalkID'] == marker['referenceOptionTalkID']
                marker['referenceStatus'] = 'EXACT_VALUE_IN_SAME_DS_SOURCE'
                marker['sameExplicitDSReferences'] = relation['sameExplicitDSReferences']
    result = project(audit, joins, normalized, owner_kind='EXPLICIT_NATIVE_MAIN_MISSION_ID')
    assert result['counts'] == {'missions': 1, 'scenes': 12, 'rows': 20, 'uniqueTalkIds': 20}
    native = {'clientVersion': 'OSPRODWin4.6.0', 'officialBaseUrl': BASE, 'edges': edges}
    for scene in result['missions'][OWNER]:
        scene['nativeOwnership'] = native
    # Actual PlayOptionTalk lists supply choices; marker references alone never
    # become spoken rows or standalone choices.
    choices = contexts['explicitDSChoices']
    selected = {r['TalkSentenceID'] for r in choices}
    preserved = {}
    for file in (SITE / 'data/dialogues').glob('*.json'):
        for index, row in enumerate(read(file)['section']['rows']):
            if row.get('talk_id') in selected:
                assert row['talk_id'] not in preserved
                preserved[row['talk_id']] = (file, index, row)
    assert set(preserved) == selected
    option_joins = {r['talkID']: r for r in contexts['optionReferenceKoreanJoins']}
    grouped = {}
    for choice in choices:
        tid = choice['TalkSentenceID']; join = option_joins[tid]
        file, index, original = preserved[tid]
        assert original['text'] == join['readableText'] and str(original['hash']) == join['textmapHash']
        assert original['voice'] == join['tableRecord'].get('VoiceID', 0)
        table = join['tableRecord']
        row = {'talk_id': tid, 'label': '선택지', 'speaker': join['readableSpeaker'] or '화자 미지정',
               'text': join['readableText'], 'raw': join['originalText'], 'hash': join['textmapHash'],
               'speaker_hash': join['speakerHash'], 'speaker_raw': join['speakerRecord']['raw'] if join['speakerRecord'] else '',
               'voice': table.get('VoiceID', 0), 'offset': join['textRecord']['offset'], 'end': join['textRecord']['end'],
               'url': '대사/' + file.stem + '.html#talk-' + str(tid),
               'preservedSource': {'file': 'data/dialogues/' + file.name, 'sha256': sha(file), 'pointer': '/section/rows/' + str(index)},
               'officialSource': {'clientVersion': joins['evidence']['clientVersion'], 'tableRow': join['tableRow'],
                   'tableOffset': table['_offset'], 'tableEnd': table['_end'], 'tableRecord': table,
                   'textRecord': join['textRecord'], 'speakerRecord': join['speakerRecord']},
               'choiceSource': {'taskPointer': choice['sourcePointer'], 'optionIndex': choice['optionIndex'],
                                'triggerCustomString': choice['TriggerCustomString']}}
        grouped.setdefault(choice['sourcePointer'], []).append(row)
    option_scenes = []
    for pointer, rows in grouped.items():
        key = edges[-1]['source'] + '#' + pointer
        option_scenes.append({'anchor': 'native-options-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'title': '연출 설정의 선택지', 'source': edges[-1]['source'],
            'sourceSha256': edges[-1]['sourceSha256'], 'sourceUrl': edges[-1]['sourceUrl'],
            'recordType': 'NATIVE_TIMELINE_CHOICES', 'mapping': 'EXACT_TYPED_DS_OPTION_TO_OFFICIAL_KOREAN_TALK',
            'ownership': edges, 'nativeOwnership': native, 'optionTaskPointer': pointer, 'rows': rows})
    # Keep each option list next to its explicitly preceding Timeline in the
    # same TaskList. This is source containment, not a global execution order.
    ordered = []
    for scene in result['missions'][OWNER]:
        ordered.append(scene)
        sequence = scene['timelineSource']['timelineFieldPointer'].split('/TaskList/')[0]
        ordered.extend(s for s in option_scenes if s['optionTaskPointer'].split('/TaskList/')[0] == sequence)
    assert len(ordered) == 15 and sum(len(s['rows']) for s in ordered) == 28
    result['missions'][OWNER] = ordered
    result['counts'] = {'missions': 1, 'scenes': 15, 'rows': 28, 'uniqueTalkIds': 28,
                        'spokenScenes': 12, 'spokenRows': 20, 'choiceScenes': 3, 'choiceRows': 8}
    result['evidence'].update(auditSha256=sha(args.evidence), joinSha256=sha(args.joins),
        contextsSha256=sha(args.contexts), nativeOwnerSha256=sha(args.owner), relationSha256=sha(args.relations),
        metadataSourceFiles={edges[3]['tableSource']: edges[3]['tableSha256']},
        sourceProfile='Explicit native group owner and NPC graph, registered D table, full-field DS, exact typed Timeline clips')
    result['relatedDocuments'] = {OWNER: [message_link(read(args.message))]}
    result['evidence']['messageAssociationSha256'] = sha(args.message)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8')
    print(json.dumps({'status': 'PASS', **result['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence', 'joins', 'contexts', 'owner', 'relations', 'message'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--output', type=Path, default=SITE / 'data/native-timeline-mission-dialogue.json')
    main(p.parse_args())
