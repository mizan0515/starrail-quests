"""Project audited typed Timeline clips into the existing mission reader.

The inputs are preserved source-audit artifacts. They are never published as
local paths, and the original dialogue/supplement files are not rewritten.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(evidence, joins, contexts):
    assert evidence['status'] == 'TYPED_DIALOGUE_ROUTE_FULL_FIELD_EOF_PASS'
    assert evidence['counts']['multiOwnerTimelines'] == 0
    assert evidence['counts']['malformedAccepted'] == 0
    lookup = {row['talkID']: row for row in joins['joins']}
    assert len(lookup) == len(joins['joins'])
    context_lookup = {row['timelineName']: row for row in contexts['timelines']}
    option_lookup = {row['talkID']: row for row in contexts['optionReferenceKoreanJoins']}
    aliases = read(SITE / 'data/aliases.json')
    legacy = read(SITE / 'data/mission-dialogue-supplements.json')
    missions = {}
    empty = []
    for timeline in evidence['timelines']:
        assert timeline['ownerStatus'] == 'ONE_EXPLICIT_OWNER'
        owners = timeline['owners']
        assert len({owner['mission'] for owner in owners}) == 1
        owner = owners[0]
        context = context_lookup[timeline['timelineName']]
        context_owner = next(o for o in context['owners'] if o['mission'] == owner['mission'] and
                             o['timelineFieldPointer'] == owner['timelineFieldPointer'])
        trigger = context_owner['originalOwnerTrigger']
        assert trigger['task']['$type'] == 'RPG.GameCore.TriggerPerformance'
        trigger_conditions = trigger['context']['conditions']
        options = []
        for marker in context['simpleTalkMarkers']:
            if not marker['nonzero']:
                continue
            assert marker['role'] == 'NON_SPOKEN_OPTION_REFERENCE'
            assert marker['referenceStatus'] == 'EXACT_VALUE_IN_SAME_DS_SOURCE'
            option = option_lookup[marker['referenceOptionTalkID']]
            assert option['status'] == 'EXACT_TALKID_TABLE_TEXTMAP_JOIN'
            options.append({'talk_id': option['talkID'], 'text': option['readableText'],
                            'raw': option['originalText'], 'hash': option['textmapHash'],
                            'role': marker['role'], 'start': marker['timelineStart'],
                            'pathID': str(marker['sourceObject']['pathID']),
                            'objectSha256': marker['sourceObject']['sha256'],
                            'references': [{'source': r['source'], 'pointer': r['pointer'],
                                            'entrySha256': r['entrySha256']} for r in marker['sameExplicitDSReferences']],
                            'officialSource': {'tableRow': option['tableRow'], 'tableRecord': option['tableRecord'],
                                               'textRecord': option['textRecord']}})
        assert owner['ownerExactValidation'] == 'PASS'
        assert all(check['status'] == 'PASS' for check in owner['ownerSourceChecks'])
        mid = owner['mission']
        target = aliases.get(mid, mid)
        document = read(SITE / 'data/documents' / (target + '.json'))
        assert mid in document.get('missionParts', [document['id']])
        seed = owner['ownerChain'][0]
        assert seed['kind'] == 'EXPLICIT_MAIN_MISSION_ID'
        assert seed['canonicalMissionId'] == int(mid.removeprefix('quest-'))
        assert 'quest-' + str(seed['missionId']) in document.get('missionParts', [document['id']])
        anchor = 'timeline-' + hashlib.sha256(timeline['timelineName'].encode()).hexdigest()[:16]
        rows = []
        clips = sorted(timeline['spokenClips'], key=lambda clip: (clip['timelineClip']['m_Start'], clip['trackClipIndex']))
        for clip in clips:
            join = lookup[clip['talkID']]
            assert join['status'] == 'EXACT_TALKID_TABLE_TEXTMAP_JOIN'
            assert join['preservedStatus'] == 'EXACT_HASH_READABLE_VOICE_AGREEMENT'
            assert join['tableMatchCount'] == 1 and join['preservedMatchCount'] == 1
            preserved = join['preservedComparisons'][0]
            original = preserved['preservedRow']
            assert original['text'] == join['readableText']
            assert str(original['hash']) == join['textmapHash']
            assert original['voice'] == join['tableRecord'].get('VoiceID', 0)
            obj = clip['sourceObject']
            assert obj['script']['m_ClassName'] == 'PlaySimpleTalkClip'
            assert clip['assetEOF'] == obj['byteSize']
            field = clip['talkIDField']
            assert field['field'] == 'PlaySimpleTalkClip.Config.TalkSentenceID'
            assert field['value'] == clip['talkID']
            assert 0 <= field['span'][0] < field['span'][1] <= obj['byteSize']
            start, duration = clip['timelineClip']['m_Start'], clip['timelineClip']['m_Duration']
            assert all(isinstance(n, (int, float)) and math.isfinite(n) for n in (start, duration))
            assert start >= 0 and duration > 0
            table = join['tableRecord']
            rows.append({
                'talk_id': clip['talkID'], 'label': '대사', 'speaker': join['readableSpeaker'] or '화자 미지정',
                'text': join['readableText'], 'hash': join['textmapHash'], 'speaker_hash': join['speakerHash'],
                'voice': table.get('VoiceID', 0), 'raw': join['originalText'],
                'speaker_raw': join['speakerRecord']['raw'] if join['speakerRecord'] else '',
                'offset': join['textRecord']['offset'], 'end': join['textRecord']['end'],
                'url': '대사/' + Path(preserved['sourceFile']).stem + '.html#talk-' + str(clip['talkID']),
                'preservedSource': {'file': 'data/dialogues/' + Path(preserved['sourceFile']).name,
                                    'sha256': preserved['sourceFileSha256'], 'pointer': preserved['rowPointer']},
                'officialSource': {'clientVersion': joins['evidence']['clientVersion'],
                                   'tableRow': join['tableRow'], 'tableOffset': table['_offset'], 'tableEnd': table['_end'],
                                   'tableRecord': table, 'textRecord': join['textRecord'], 'speakerRecord': join['speakerRecord']},
                'timelineClip': {'trackClipIndex': clip['trackClipIndex'], 'start': start, 'duration': duration,
                                 'pathID': str(obj['pathID']), 'trackPathID': str(clip['trackPathID']),
                                 'objectByteStart': obj['byteStart'], 'objectByteSize': obj['byteSize'],
                                 'objectSha256': obj['sha256'], 'talkIDSpan': field['span']},
            })
        if not rows:
            empty.append({'mission': mid, 'source': timeline['timelineName']})
            continue
        receipt = timeline['sourceReceipt']
        missions.setdefault(target, []).append({
            'anchor': anchor, 'title': '연출의 대사',
            'source': timeline['timelineName'], 'mapping': 'EXACT_TYPED_TIMELINE_TO_OFFICIAL_KOREAN_TALK',
            'recordType': 'TIMELINE_DIALOGUE', 'ownership': owner['ownerChain'], 'rows': rows,
            'triggerContext': {'source': trigger['source'], 'sourceSha256': trigger['sourceEvidence']['sha256'],
                               'referencePointer': trigger['referencePointer'], 'conditions': trigger_conditions,
                               'performanceId': trigger['task']['PerformanceID'],
                               'dsConditions': context_owner['strictBinaryDSContext']['conditions']},
            'optionReferences': options,
            'timelineSource': {
                'ownerMissionId': seed['missionId'], 'logicalJsonPath': owner['logicalJsonPath'],
                'nameHash': owner['nameHash'], 'entrySha256': owner['entrySha256'],
                'timelineFieldPointer': owner['timelineFieldPointer'],
                'timelineFieldByteProof': owner['timelineFieldByteProof'], 'entryBytes': owner['consumedBytes'],
                'blockFile': Path(receipt['block']['path']).name, 'blockSha256': receipt['block']['sha256'],
                'bundleOffset': receipt['expectedSpan']['offset'], 'bundleBytes': receipt['expectedSpan']['length'],
                'cabName': receipt['expectedSpan']['cab'], 'cabSha256': receipt['cabSha256'],
                'containerKey': timeline['directRootContainer']['key'],
                'rootPathID': str(timeline['rootPathID']), 'talkTrackPathID': str(timeline['talkTrackPathID']),
                'parentRouteTalkToRoot': list(map(str, timeline['parentRouteTalkToRoot'])),
                'trackRawSha256': clips[0]['trackRawSha256'],
                'serializedIndices': [clip['trackClipIndex'] for clip in timeline['spokenClips']],
                'timeSortedIndices': [clip['trackClipIndex'] for clip in clips],
            },
        })
    counts = {'missions': len(missions), 'scenes': sum(map(len, missions.values())),
              'rows': sum(len(scene['rows']) for scenes in missions.values() for scene in scenes),
              'uniqueTalkIds': len({row['talk_id'] for scenes in missions.values() for scene in scenes for row in scene['rows']})}
    assert counts['rows'] == evidence['counts']['typedSpokenClipOccurrences']
    return {'schema': 'starrail-timeline-mission-dialogue.v1',
            'evidence': {'installedVersion': evidence['installedVersion'],
                         'officialKorean': joins['evidence'],
                         'metadataRepository': legacy['evidence']['repository'], 'metadataCommit': legacy['evidence']['commit'],
                         'metadataSourceFiles': {edge[key]: edge[hash_key] for scenes in missions.values() for scene in scenes
                                                 for edge in scene['ownership']
                                                 for key, hash_key in [('source', 'sourceSha256'), ('tableSource', 'tableSha256')]
                                                 if key in edge and hash_key in edge},
                         'sourceProfile': 'Observed PlaySimpleTalkClip.Config.TalkSentenceID; whole-field EOF and exact PPtr route',
                         'readingOrder': 'Within each TalkTrack, ascending m_Start then original trackClipIndex',
                         'scope': 'Typed spoken clip route; other animation/control bodies and runtime branching remain unverified'},
            'missions': missions, 'emptyTimelines': empty, 'counts': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--joins', required=True, type=Path)
    parser.add_argument('--contexts', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=SITE / 'data/timeline-mission-dialogue.json')
    args = parser.parse_args()
    evidence, joins = read(args.evidence), read(args.joins)
    assert sha(args.joins) == evidence['koreanJoinOutput']['sha256']
    contexts = read(args.contexts)
    assert contexts['inputs'][0]['sha256'] == sha(args.evidence)
    assert contexts['inputs'][1]['sha256'] == sha(args.joins)
    output = project(evidence, joins, contexts)
    output['evidence']['auditSha256'] = sha(args.evidence)
    output['evidence']['joinSha256'] = sha(args.joins)
    output['evidence']['contextsSha256'] = sha(args.contexts)
    args.output.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS', **output['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
