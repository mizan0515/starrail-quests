"""Check new official rows, source fields, ownership references and raw bytes."""
import argparse,hashlib,json,tarfile
from copy import deepcopy
from pathlib import Path
from build_official_universe_texts import corpus_digest
from verify_official_universe_texts import readable,at,safe

SITE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text('utf8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()

def row_check(row,e):
    o=row['officialSource'];t=o['tableRecord'];text=o['textRecord'];speaker=o['speakerRecord']
    assert type(row['talk_id']) is int and row['talk_id']==t['TalkSentenceID']
    assert o['clientVersion']==e['clientVersion']=='OSPRODWin4.6.0'
    assert str(t['TalkSentenceText']['Hash'])==row['hash']==str(text['hash'])
    assert str(t.get('TextmapTalkSentenceName',{}).get('Hash',0))==row['speaker_hash']
    assert row['raw']==text['raw'] and row['text']==readable(text['raw']) and row['text']
    assert row['offset']==text['offset'] and row['end']==text['end']
    assert 0<=row['offset']<row['end']<=e['entry']['length']
    assert 0<=o['tableOffset']<o['tableEnd']<=e['talkTable']['length']
    assert t['_offset']==o['tableOffset'] and t['_end']==o['tableEnd']
    assert 0<=o['tableRow']<e['talkTable']['rows']
    if row['speaker_hash']=='0':
        assert speaker is None and row['speaker_raw']=='' and row['speaker']=='화자 미지정'
    else:
        assert row['speaker_hash']==str(speaker['hash'])
        assert row['speaker_raw']==speaker['raw'] and row['speaker']==readable(speaker['raw'])
        assert 0<=speaker['offset']<speaker['end']<=e['entry']['length']

def verify(root=None,archive=None,skill=None):
    p=SITE/'data/official-mission-talks.json';raw=p.read_bytes();d=json.loads(raw)
    assert raw==(SITE/'public/official-mission-talks.json').read_bytes();safe(d)
    assert d['schema']=='starrail-official-mission-talks.v1'
    e=d['evidence'];assert e['preservedCorpus']==corpus_digest()
    assert e['catalogSha256']=='ae92b3dd2417efbb9cd08e463891051ed515df2f97d40137223cec394a7e6132'
    assert e['koreanPack']['sha256']=='99dadf3786823c934ff12e970df594a77d413f8b090d2645f58cc8ad903fda20'
    assert e['talkTable']['sha256']=='ae6cc8e41213ccecc430a346909daf38ff4013d6b1441ddba384032d77b3ffd4'
    assert e['entry']['fullEofVerified'] is True and e['talkTable']['fullEofVerified'] is True
    assert e['entry']['rows']==474191 and e['talkTable']['rows']==244380
    local={r['talk_id'] for file in (SITE/'data/dialogues').glob('*.json') for r in read(file)['section']['rows']}
    ids={r['talk_id'] for r in d['rows']};assert len(ids)==len(d['rows']) and not ids.intersection(local)
    assert d['counts']=={'selectedRows':len(ids),'preservedKoreanRows':len(local)}
    supplements=read(SITE/'data/mission-dialogue-supplements.json')
    assert e['metadataCommit']==supplements['evidence']['commit'] and e['archiveSha256']==supplements['evidence']['archiveSha256']
    for row in d['rows']:
        row_check(row,e)
        assert row['references']
        for ref in row['references']:
            assert ref['talkId']==row['talk_id'] and ref['source'] in supplements['coverage'][ref['missionId']]['sourceOwnership']
            assert ref['references'] and all(r['pointer'].startswith('/') and r['kind'] in ('TalkSentenceID','TalkSentenceIDList','TalkSentence event reference') for r in ref['references'])
    mutations=0
    for field,value in [('talk_id',d['rows'][0]['talk_id']+1),('text','altered'),('speaker','different'),('hash','1')]:
        changed=deepcopy(d['rows'][0]);changed[field]=value
        try:row_check(changed,e)
        except AssertionError:mutations+=1
        else:raise AssertionError('Accepted official-row mutation: '+field)
    deep=bool(root or archive or skill)
    if deep:
        assert root and archive and skill
        from build_official_mission_talks import decode_talk_input
        talks,texts,actual,projection=decode_talk_input(root,skill)
        for key in ('manifestSha256','catalogSha256','koreanPack','entry','talkTable'):assert e[key]==actual[key]
        assert sha(archive.read_bytes())==e['archiveSha256']
        wanted={ref['source'] for row in d['rows'] for ref in row['references']};metadata={}
        with tarfile.open(archive,'r:gz') as tf:
            for member in tf:
                name=member.name.split('/',1)[-1]
                if name in wanted:
                    source=tf.extractfile(member).read();assert sha(source)==supplements['evidence']['structureFiles'][name];metadata[name]=json.loads(source)
        assert set(metadata)==wanted
        for row in d['rows']:
            o=row['officialSource'];assert o['tableRecord']==talks[o['tableRow']]
            assert o['textRecord']==texts[row['hash']]
            assert o['speakerRecord']==texts.get(row['speaker_hash'])
            for ref in row['references']:
                for pointer in ref['references']:
                    expected='TalkSentence_'+str(row['talk_id']) if pointer['kind']=='TalkSentence event reference' else row['talk_id']
                    assert at(metadata[ref['source']],pointer['pointer'])==expected
    print(json.dumps({'status':'PASS','officialRows':len(ids),'preservedKoreanRows':len(local),'deepOriginalBytes':deep,'mutationRejections':mutations}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path);p.add_argument('--archive',type=Path);p.add_argument('--skill',type=Path);a=p.parse_args();verify(a.official_root,a.archive,a.skill)
