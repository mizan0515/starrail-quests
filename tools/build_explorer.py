"""Build complete exploration axes from re-decoded local tables and source rows."""
import argparse,json,re,sys
from collections import defaultdict
from pathlib import Path
from export_dialogue_browser import clean,dump

def name_position(body,name):
    if len(name)==1:
        m=re.search(r'[「『“]('+re.escape(name)+r')[」』”]',body)
        return m.start(1) if m else None
    for m in re.finditer(re.escape(name),body):
        if m.start()>0 and body[m.start()-1].isalnum():continue
        tail=body[m.end():]
        if tail and tail[0].isalnum() and not re.match(r'^(?:은|는|이|가|을|를|의|에|에서|에게|와|과|도|로|으로|부터|까지|께서|씨(?:가|는|의|도|를)?)(?=$|[^\w])',tail):continue
        return m.start()
    return None
def main():
    p=argparse.ArgumentParser();p.add_argument('--game-data',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--structure',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.skill/'scripts'));from binary import LocalData,decode_table,decode_textmap
    data=LocalData(a.game_data);schemas=json.loads((a.skill/'assets/schemas-v4.json').read_text('utf8'));tables={};sources={}
    for name in ['WorldDataConfig','StoryAtlas','LoadingDesc','RogueAeonDisplay','RogueAeonStoryConfig']:
        b,s=data.entry(schemas[name]['entry_hash']);tables[name]=decode_table(b,schemas[name]['schema']);sources[name]={**s,'file':Path(s['file']).name}
    kr=next(f for f in data.catalog if f['language']=='kr');b,s=data.entry(kr['entries'][0][0]);texts={r['hash']:clean(r['raw']) for r in decode_textmap(b)}
    def text(v):return texts.get(v.get('Hash',0),'') if isinstance(v,dict) else ''
    c=json.loads((a.site/'data/catalog.json').read_text('utf8'));docs={d['id']:json.loads((a.site/'data/documents'/(d['id']+'.json')).read_text('utf8')) for d in c};byid={d['id']:d for d in c}
    def evidence(d):
        return [{'id':d['id'],'title':d['title'],'anchor':s['anchor'],'quote':r['text'][:220],'hash':r['hash'],'status':'게임 내 원문'} for s in d['sections'] for r in s['rows'] if r.get('hash') and r['text']][:2]
    worlds={r['ID']:text(r.get('WorldName')) for r in tables['WorldDataConfig'] if text(r.get('WorldName'))}
    public=json.loads((a.structure/'ExcelOutput/LoadingDesc.json').read_text('utf8'));pub={r['ID']:r for r in public};enum_map={}
    for r in tables['LoadingDesc']:
        ref=pub.get(r['ID'])
        if not ref or ref['TitleTextmapID']['Hash']!=r['TitleTextmapID']['Hash'] or ref['DescTextmapID']['Hash']!=r['DescTextmapID']['Hash']:raise ValueError('LoadingDesc structure hash mismatch')
        if r['Group'] in enum_map and enum_map[r['Group']]!=ref['Group']:raise ValueError('Conflicting group enum')
        enum_map[r['Group']]=ref['Group']
    entries=[]
    # World table includes older worlds with names but no description field.
    for r in tables['WorldDataConfig']:
        name=text(r.get('WorldName'))
        if not name:continue
        wid=r['ID'];matching=[d for d in c if d['world']==name];description=text(r.get('WorldDesc')) or text(r.get('SimpleWorldDesc'))
        entries.append({'id':'region-'+str(wid),'axis':'region','name':name,'group':'전체 지역','excerpt':description[:220] or '임무·기록·인물의 원문에서 이곳의 맥락을 읽습니다.','description':description,'source':'WorldDataConfig','sourceRow':r,'documents':[d['id'] for d in matching],'stories':[],'evidence':evidence(docs['world-'+str(wid)]) if 'world-'+str(wid) in docs else []})
    chars=defaultdict(list)
    for r in tables['StoryAtlas']:chars[r['AvatarID']].append(r)
    for aid,rows in chars.items():
        did='avatar-'+str(aid);name=byid.get(did,{}).get('title','이름이 연결되지 않은 인물 기록');known=did in byid
        stories=[{'label':'인물 이야기 '+str(r['StoryID']),'text':text(r.get('Story')),'hash':str(r.get('Story',{}).get('Hash',0)),'story_id':r['StoryID'],'offset':r['_offset'],'end':r['_end']} for r in rows]
        entries.append({'id':'person-'+str(aid),'axis':'person','name':'개척자 · '+('첫 번째 기록' if aid==8001 else '두 번째 기록') if aid in [8001,8002] else name,'group':'캐릭터 이야기' if known else '이름 미확인 기록','excerpt':next((s['text'][:150] for s in stories if s['text']),''),'source':'StoryAtlas','sourceDocument':did if known else None,'documents':[did] if known else [],'stories':stories,'evidence':evidence(docs[did]) if known else [],'nameVerified':known})
    # Complete local named Aeons: archived stories plus four distinct loading entries.
    aeon_docs={d['title']:d['id'] for d in c if d['category']=='에이언즈·운명의 길'}
    for did in ['lore-10042','lore-10084','lore-10087','lore-10089']:aeon_docs[byid[did]['title']]=did
    for name,did in aeon_docs.items():
        related=[d['id'] for d in c if d['category']=='세계관·용어' and d['title']==name]
        ids=list(dict.fromkeys([did]+related));e=[x for id in ids for x in evidence(docs[id])]
        entries.append({'id':'aeon-'+did,'axis':'aeon','name':name,'group':'에이언즈','excerpt':e[0]['quote'][:170] if e else '', 'source':'RogueAeonStoryConfig / LoadingDesc','documents':ids,'stories':[],'evidence':e})
    for r in tables['LoadingDesc']:
        did='lore-'+str(r['ID']);d=docs.get(did)
        if not d:continue
        group=enum_map[r['Group']];world=worlds.get(int(group[5:])) if group.startswith('World') else None
        label=world or {'NormalIP':'우주·세력·존재','NormalRule':'힘·기술·게임 규칙','StoryLine':'이야기 속 개념'}.get(group,group)
        entries.append({'id':did,'axis':'concept','name':d['title'],'group':label,'excerpt':text(r['DescTextmapID'])[:190],'source':'LoadingDesc','documents':[did],'stories':[],'evidence':evidence(d),'world':world,'sourceGroup':group})
    # Attach exact name occurrences as discovery aids, not inferred relationships.
    for e in entries:
        if e['axis'] not in ['person','aeon'] or not e.get('nameVerified',True):continue
        name=e['name'].split(' · ')[0];names=[name,name.replace('•','·'),name.replace('·','•')]
        if name=='개척자':continue
        mentions=[]
        for d in docs.values():
            if d['id'] in e['documents'] or d['category'] in ['아이템 설정','유물 이야기']:continue
            hit=None
            for sec in d['sections']:
                for row in sec['rows']:
                    body=row['text'];pos=next((pos for n in names if (pos:=name_position(body,n)) is not None),None)
                    if pos is not None:
                        start=max(0,pos-65);hit={'id':d['id'],'title':d['title'],'category':d['category'],'anchor':sec['anchor'],'quote':body[start:start+210],'hash':row['hash'],'status':'이름이 등장하는 원문 · 관계의 확정 근거와 구분'};break
                if hit:break
            if hit:mentions.append(hit)
        e['mentions']=mentions
    # Loading group gives an explicit region binding; supplement world metadata.
    for e in entries:
        if e['axis']=='region':e['concepts']=[x['id'] for x in entries if x['axis']=='concept' and x.get('world')==e['name']]
    dump(a.site/'data/explorer.json',{'entries':entries,'counts':{axis:sum(e['axis']==axis for e in entries) for axis in ['region','person','concept','aeon']},'evidence':{'tables':sources,'sources':[{**v,'file':Path(k).name} for k,v in data.evidence.items()],'loadingGroupMapping':'Exact ID + title/body Hash match; numeric group enum consistently mapped to metadata group name','unresolvedCharacters':sum(e['axis']=='person' and not e.get('nameVerified') for e in entries)}})
    data.verify_unchanged();print(json.dumps({'entries':len(entries),'counts':{axis:sum(e['axis']==axis for e in entries) for axis in ['region','person','concept','aeon']}},ensure_ascii=False))
if __name__=='__main__':main()
