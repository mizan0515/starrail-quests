"""Keep newly readable, exactly referenced official Korean rows separate."""
import argparse,hashlib,json,sys
from pathlib import Path
from build_official_universe_texts import official_input,corpus_digest

SITE=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text('utf8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()

def decode_talk_input(root,skill):
    texts,evidence,projection=official_input(root,skill)
    from binary import decode_table,read_catalog
    spec=read(skill/'assets/schemas-v4.json')['TalkSentenceConfig']
    catalog=read_catalog((root/evidence['catalogFile']).read_bytes())
    matches=[(f,e) for f in catalog for e in f['entries'] if e[0]==int(spec['entry_hash'])]
    assert len(matches)==1
    info,(key,length,offset)=matches[0]
    assert not info['language']
    pack=(root/info['file']).read_bytes()
    assert len(pack)==info['size'] and hashlib.md5(pack).hexdigest()==Path(info['file']).stem
    entry=pack[offset:offset+length];talks=decode_table(entry,spec['schema'])
    assert len({r.get('TalkSentenceID',0) for r in talks})==len(talks)
    evidence['talkTable']={'file':info['file'],'sha256':sha(pack),'md5':Path(info['file']).stem,'size':len(pack),'key':str(key),'offset':offset,'length':length,'entrySha256':sha(entry),'rows':len(talks),'fullEofVerified':True,'schema':spec['schema']}
    return talks,texts,evidence,projection

def build(root,skill):
    preserved=corpus_digest();supplements=read(SITE/'data/mission-dialogue-supplements.json')
    local={r['talk_id'] for p in (SITE/'data/dialogues').glob('*.json') for r in read(p)['section']['rows']}
    candidates={}
    for ref in supplements['unresolvedReferences']:
        candidates.setdefault(ref['talkId'],[]).append(ref)
    # Rebuilding after adoption preserves the explicit source references.
    for mid,scenes in supplements['missions'].items():
        for scene in scenes:
            for row in scene['rows']:
                if row.get('officialSource'):
                    candidates.setdefault(row['talk_id'],[]).append({'missionId':mid,'source':scene['source'],'talkId':row['talk_id'],'references':row['references']})
    talks,texts,evidence,projection=decode_talk_input(root,skill);selected=[]
    for index,table in enumerate(talks):
        tid=table.get('TalkSentenceID')
        if tid in local or tid not in candidates:continue
        text_hash=str(table.get('TalkSentenceText',{}).get('Hash',0));speaker_hash=str(table.get('TextmapTalkSentenceName',{}).get('Hash',0))
        if text_hash not in texts or not texts[text_hash]['raw']:continue
        if speaker_hash!='0' and speaker_hash not in texts:continue
        text=texts[text_hash];speaker=texts.get(speaker_hash)
        refs=[]
        for ref in candidates[tid]:
            if ref not in refs:refs.append(ref)
        selected.append({'talk_id':tid,'label':'대사','speaker':projection(speaker['raw']) if speaker else '화자 미지정','text':projection(text['raw']),'raw':text['raw'],'speaker_raw':speaker['raw'] if speaker else '', 'hash':text_hash,'speaker_hash':speaker_hash,'offset':text['offset'],'end':text['end'],
            'officialSource':{'clientVersion':evidence['clientVersion'],'tableRow':index,'tableOffset':table['_offset'],'tableEnd':table['_end'],'tableRecord':table,'textRecord':text,'speakerRecord':speaker},'references':refs})
    result={'schema':'starrail-official-mission-talks.v1','evidence':{**evidence,'preservedCorpus':preserved,'metadataCommit':supplements['evidence']['commit'],'archiveSha256':supplements['evidence']['archiveSha256']},'rows':selected,'counts':{'selectedRows':len(selected),'preservedKoreanRows':len(local)}}
    assert corpus_digest()==preserved
    for path in (SITE/'data/official-mission-talks.json',SITE/'public/official-mission-talks.json'):
        path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),'utf8')
    print(json.dumps(result['counts']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--official-root',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);a=p.parse_args();build(a.official_root,a.skill)
