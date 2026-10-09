"""Independently compare official mission source disclosures with source rows."""
import argparse
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from verify_mission_readers import MissionPage,ReadingTemplatePage,VOID

SITE=Path(__file__).resolve().parents[1]

class ProofPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.proofs=[];self.conditions=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs);proof=next((n['proof'] for n in reversed(self.stack) if n['proof']),None)
        row=next((n['row'] for n in reversed(self.stack) if n['row']),None)
        if 'original-row' in a.get('class','').split():row=a
        own=None;capture=None
        if 'data-source-condition' in a:
            capture=[];self.conditions.append({'pointer':a['data-source-condition'],'owner':row,'text':capture})
        if 'data-official-talk-proof' in a:
            own={'id':a['data-official-talk-proof'],'attrs':a,'tag':tag,'owner':row,'summaries':[],'terms':[],'values':[]}
            self.proofs.append(own);proof=own
        if proof is not None and tag in ('summary','dt','dd'):
            capture=[];proof[{'summary':'summaries','dt':'terms','dd':'values'}[tag]].append(capture)
        if tag=='br':
            for n in self.stack:
                if n['capture'] is not None:n['capture'].append('\n')
        if tag not in VOID:self.stack.append({'tag':tag,'proof':own,'row':row if 'original-row' in a.get('class','').split() else None,'capture':capture})

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)

    def handle_data(self,text):
        for n in self.stack:
            if n['capture'] is not None:n['capture'].append(text)

    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag']==tag:
                del self.stack[i:];break

def expected_fields(row,e):
    o=row['officialSource'];t=e['talkTable'];k=e['koreanPack'];entry=e['entry']
    return [
        ('대사표의 본문과 화자',f"TalkSentenceConfig · 대사 {row['talk_id']}\n본문 문자열 {row['hash']}\n화자 문자열 {row['speaker_hash']}"),
        ('대사표 원본 위치',f"{t['file']}\n엔트리 {t['key']} · 팩 오프셋 {t['offset']}\n엔트리 내부 {o['tableOffset']}–{o['tableEnd']}\nSHA-256 · {t['sha256']}"),
        ('한국어 문자열 원본 위치',f"{k['file']}\n엔트리 {entry['key']} · 팩 오프셋 {entry['offset']}\n본문 {row['offset']}–{row['end']}\nSHA-256 · {k['sha256']}"),
        ('게임 파일의 한국어 문자열',row['raw']),
    ]

def check(html,rows,e):
    proof=ProofPage();proof.feed(html)
    template=ReadingTemplatePage();template.feed(html);assert not template.finish()
    assert Counter(p['id'] for p in proof.proofs)==Counter(str(r['talk_id']) for r in rows)
    expected={str(r['talk_id']):r for r in rows}
    for p in proof.proofs:
        r=expected[p['id']];a=p['attrs'];owner=p['owner']
        assert p['tag']=='details' and a['data-reading-template']=='disclosure' and 'rw-disclosure' in a['class'].split()
        assert owner and owner['data-speaker']==r['speaker'] and owner['data-passage']=='dialogue'
        assert [''.join(x) for x in p['summaries']]==['공식 한국어 원문 · '+r['officialSource']['clientVersion'].removeprefix('OSPRODWin')]
        assert list(zip([''.join(x) for x in p['terms']],[''.join(x) for x in p['values']]))==expected_fields(r,e)
        assert len(p['terms'])==len(p['values'])==4
    page=MissionPage();page.feed(html)
    for row in rows:
        for condition in row.get('sourceConditions',[]):
            matches=[c for c in proof.conditions if c['pointer']==condition['referencePointer']]
            assert len(matches)==1 and matches[0]['owner']['data-speaker']==row['speaker']
            assert ''.join(matches[0]['text'])==f"파일의 분기 조건 · {condition['name']} = {condition['value']}"
        matches=[r for r in page.rows if r['attrs'].get('data-speaker')==row['speaker'] and any(''.join(b['text'])==row['text'] for b in r['bodies'])]
        assert matches and any(r['isPrimary'] and not r['isReference'] for r in matches)
    return len(proof.proofs)

def main(dist):
    original=json.loads((SITE/'data/official-mission-talks.json').read_text('utf8'))
    supplements=json.loads((SITE/'data/mission-dialogue-supplements.json').read_text('utf8'))
    timelines=json.loads((SITE/'data/timeline-mission-dialogue.json').read_text('utf8'))
    assert timelines['evidence']['officialKorean']['talkTable']==original['evidence']['talkTable']
    assert timelines['evidence']['officialKorean']['entry']==original['evidence']['entry']
    missions={mid:[*supplements['missions'].get(mid,[]),*timelines['missions'].get(mid,[])]
              for mid in set(supplements['missions'])|set(timelines['missions'])}
    expected={mid:[r for s in scenes for r in s['rows'] if r.get('officialSource')] for mid,scenes in missions.items()}
    expected={mid:rows for mid,rows in expected.items() if rows}
    count=mutations=0
    for mid,rows in expected.items():
        html=(dist/'문서'/(mid+'.html')).read_text('utf8')
        count+=check(html,rows,original['evidence'])
        canary=rows[0]
        for old,new in [(f'data-official-talk-proof="{canary["talk_id"]}"','data-removed-proof="missing"'),
                        ('공식 한국어 원문 · 4.6.0','공식 한국어 원문 · 4.5.0'),
                        (canary['officialSource']['tableRecord']['TalkSentenceText']['Hash'].__str__(),'1'),
                        (original['evidence']['koreanPack']['sha256'],'0'*64),
                        *([('data-source-condition=','data-removed-condition=')] if any(r.get('sourceConditions') for r in rows) else [])]:
            assert old in html
            try:check(html.replace(old,new),rows,original['evidence'])
            except AssertionError:mutations+=1
            else:raise AssertionError('Accepted source disclosure mutation: '+old)
    all_proofs=sum(p.read_text('utf8').count('data-official-talk-proof=') for p in (dist/'문서').glob('quest-*.html'))
    assert count==all_proofs and count>=len(original['rows'])
    print(json.dumps({'status':'PASS','missions':len(expected),'officialSourceDisclosures':count,'htmlMutationRejections':mutations}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dist',type=Path,default=SITE/'dist');a=p.parse_args();main(a.dist)
