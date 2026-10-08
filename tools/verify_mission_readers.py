"""Read-only verification of every built mission's primary original-text reader.

Compare DOM text with preserved source rows, not with another generated summary.
No whitespace or punctuation normalization is applied to dialogue text.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

BASE = '/starrail-quests'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class ReadingTemplatePage(HTMLParser):
    """Check custom-reader boundaries independently of source-text collection."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.errors=[];self.disclosures=[];self.summary=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=set(a.get('class','').split());kind=a.get('data-reading-template')
        boundary=kind=='reader' and {'rw-reader','not-content'}<=classes
        inside=boundary or any(x['boundary'] for x in self.stack)
        if kind=='reader' and not boundary:self.errors.append('reader boundary classes missing')
        if classes & {'original-row','quest-source-line'}:
            if kind!='row' or 'rw-source-row' not in classes:self.errors.append('source row common template missing')
            if not inside:self.errors.append('source row outside isolated reader boundary')
        if 'source-section' in classes and not boundary:self.errors.append('source scene common reader boundary missing')
        technical=bool(classes & {'source-details','mission-scene-index','mission-reference-scenes','quest-info','quest-scene-info'})
        disclosure=None
        if kind=='disclosure' or technical:
            if tag!='details' or kind!='disclosure' or 'rw-disclosure' not in classes:self.errors.append('disclosure common template missing')
            disclosure={'summaries':0};self.disclosures.append(disclosure)
        summary=None
        if tag=='summary' and self.stack and self.stack[-1]['disclosure'] is not None:
            self.stack[-1]['disclosure']['summaries']+=1;summary=[];self.summary=summary
        if tag not in VOID:self.stack.append({'tag':tag,'boundary':boundary,'disclosure':disclosure,'summary':summary})
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)
    def handle_data(self,text):
        if self.summary is not None:self.summary.append(text)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag']==tag:
                removed=self.stack[i:];del self.stack[i:]
                for element in removed:
                    if element['summary'] is not None:
                        if re.match(r'^\s*[>›▶▸▹▷→]', ''.join(element['summary'])):self.errors.append('disclosure summary has literal leading arrow')
                        self.summary=None
                break
    def finish(self):
        for disclosure in self.disclosures:
            if disclosure['summaries']!=1:self.errors.append('disclosure must have one immediate summary')
        return self.errors


class MissionPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = Counter()
        self.readers = []
        self.reader_states = []
        self.references = []
        self.reference_summaries = []
        self.summary = None
        self.rows = []
        self.sections = []
        self.progress_positions = []
        self.count_texts = []
        self.coverage_texts = []
        self.reader_links = []
        self.scope_notes = []
        self.scope_note = None
        self.headings = []
        self.heading = None
        self.position = 0
        self.current_row = self.body = self.count = self.coverage = None

    def handle_starttag(self,tag,attrs):
        self.position += 1
        a = dict(attrs)
        classes = set(a.get('class','').split())
        flags = set()
        if tag=='h1':
            self.heading=[];self.headings.append(self.heading);flags.add('heading')
        if a.get('id'): self.ids[a['id']] += 1
        if 'data-mission-reader' in a:
            self.readers.append(self.position)
            self.reader_states.append(a.get('data-reading-state'))
            flags.add('reader')
        if 'mission-scenes' in classes:flags.add('primaryScenes')
        primary_scene = 'primaryScenes' in flags or any('primaryScenes' in x[1] for x in self.stack)
        if 'data-reference-scenes' in a:
            flags.add('reference')
            self.references.append({'tag':tag,'attrs':a,'position':self.position})
        reference = 'reference' in flags or any('reference' in x[1] for x in self.stack)
        if tag=='summary' and reference:
            self.summary=[]
            self.reference_summaries.append(self.summary)
            flags.add('summary')
        inside = 'reader' in flags or any('reader' in x[1] for x in self.stack)
        if tag=='a' and inside and a.get('href'): self.reader_links.append(unquote(a['href']))
        if 'mission-progress' in classes: self.progress_positions.append(self.position)
        if 'source-section' in classes:
            self.sections.append({'id':a.get('id'),'insideReader':inside,'isReference':reference,'isPrimary':primary_scene})
        if 'source-scope-note' in classes:
            self.scope_note={'sectionId':self.sections[-1]['id'],'isReference':reference,'text':[]}
            self.scope_notes.append(self.scope_note)
            flags.add('scopeNote')
        if 'original-row' in classes:
            self.current_row = {'attrs':a,'insideReader':inside,'isReference':reference,'isPrimary':primary_scene,'bodies':[]}
            self.rows.append(self.current_row)
            flags.add('row')
        if tag=='p' and 'original-body' in classes:
            self.body = {'id':a.get('id'),'text':[],'paragraphs':0}
            if self.current_row is not None: self.current_row['bodies'].append(self.body)
            flags.add('body')
        if 'original-paragraph' in classes and self.body is not None:
            self.body['paragraphs'] += 1
        if 'mission-reader-count' in classes:
            self.count = []
            self.count_texts.append(self.count)
            flags.add('count')
        if 'coverage-note' in classes and inside:
            self.coverage = []
            self.coverage_texts.append(self.coverage)
            flags.add('coverage')
        if tag not in VOID: self.stack.append((tag,flags))

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID: self.handle_endtag(tag)

    def handle_endtag(self,tag):
        for n in range(len(self.stack)-1,-1,-1):
            if self.stack[n][0]==tag:
                flags=set().union(*(x[1] for x in self.stack[n:]))
                del self.stack[n:]
                if 'row' in flags: self.current_row=None
                if 'body' in flags: self.body=None
                if 'count' in flags: self.count=None
                if 'coverage' in flags: self.coverage=None
                if 'summary' in flags: self.summary=None
                if 'scopeNote' in flags: self.scope_note=None
                if 'heading' in flags: self.heading=None
                break

    def handle_data(self,text):
        if self.heading is not None:self.heading.append(text)
        if self.body is not None: self.body['text'].append(text)
        if self.count is not None: self.count.append(text)
        if self.coverage is not None: self.coverage.append(text)
        if self.summary is not None: self.summary.append(text)
        if self.scope_note is not None: self.scope_note['text'].append(text)


def expected_mission_title(document):
    """Independent display expectation; preserved source titles stay unchanged."""
    title=document.get('title')
    if document.get('category')=='퀘스트' and re.fullmatch(r'quest-\d+',document.get('id','')):
        if not isinstance(title,str) or not title.strip() or (title=='한국어 본문 미수록' and document.get('title_hash')==''):
            return '임무 '+document['id'].split('-',1)[1]+' · 제목 미확인'
    return title

class BrowseBindings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.catalogues=[]
    def handle_starttag(self,tag,attrs):
        attributes=dict(attrs)
        if 'browse' in attributes.get('class','').split():
            self.catalogues.append(attributes.get('data-catalog',''))


def passage(row):
    # Judge source availability before choice labels. Preserve the original text;
    # strip is used only to classify a genuinely empty/whitespace-only body.
    text=row.get('text')
    if row.get('label')=='대사 누락' or not isinstance(text,str) or not text.strip():return 'gap'
    if text=='한국어 본문 미수록' and row.get('hash')=='' and re.fullmatch(r'MessageItemConfig:\d+\.(?:MainText|OptionText)',row.get('source','')):
        return 'gap'
    if row.get('officialCaptionSource'):return 'caption'
    if row.get('displayKind') in ('choice','선택지') or row.get('label')=='선택지':return 'choice'
    return 'dialogue'


def explicitly_owned(chain):
    # Membership follows an explicit main-mission proof, never an ID prefix,
    # neighbouring directory, common speaker or matching dialogue number.
    return isinstance(chain,list) and bool(chain) and isinstance(chain[0],dict) and chain[0].get('kind')=='EXPLICIT_MAIN_MISSION_ID'


def caption_owned(document,section):
    """Classify an exact caption owner independently of the UI adapter.

    MainMission seeds require the seed's exact JSON source, pointer and path in
    the first ownership edge, as well as a preserved canonical/alias mission.
    """
    owner=section.get('ownership',{});seed=owner.get('ownershipSeed',{})
    chain=owner.get('chain')
    if not isinstance(chain,list) or not chain or not isinstance(chain[0],dict):return False
    first=chain[0]
    runtime=seed.get('kind')=='EXPLICIT_RUNTIME_OWNERMAINMISSIONID'
    path=seed.get('missionJsonPath');pointer=seed.get('missionJsonPathPointer')
    source=seed.get('source')
    main=(seed.get('kind')=='EXPLICIT_MAIN_MISSION_ID'
          and isinstance(source,str) and bool(source)
          and isinstance(path,str) and bool(path) and isinstance(pointer,str) and bool(pointer)
          and first.get('kind')=='EXPLICIT_JSON_PATH' and first.get('source')==source
          and first.get('pointer')==pointer and first.get('target')==path)
    return ((runtime or main) and
            'quest-'+str(owner.get('missionId')) in document.get('missionParts',[document['id']]) and
            str(seed.get('missionId'))==str(owner.get('missionId')))


def caption_scope_self_test(root):
    read=lambda p:json.loads(p.read_text(encoding='utf8'))
    source=read(root/'data/official-video-captions.json');aliases=read(root/'data/aliases.json')
    measured=Counter();fixture=None
    for owner,scenes in source['missions'].items():
        target=aliases.get(owner,owner);document=read(root/'data/documents'/(target+'.json'))
        for section in scenes:
            assert caption_owned(document,section),('Exact caption source seed rejected',owner,section['anchor'])
            kind=section['ownership']['ownershipSeed']['kind']
            measured[kind]+=len(section['rows'])
            if kind=='EXPLICIT_MAIN_MISSION_ID' and fixture is None:fixture=(document,section)
    assert sum(measured.values())==source['counts']['rows'],'Exact caption source aggregation differs'
    assert fixture is not None,'MainMission caption regression fixture absent'
    document,section=fixture
    for field,value in [('kind','DIRECTORY_MATCH'),('missionJsonPath',''),
                        ('missionJsonPathPointer','/wrong'),('source','foreign.json'),('missionId',0)]:
        changed=json.loads(json.dumps(section));changed['ownership']['ownershipSeed'][field]=value
        assert not caption_owned(document,changed),('Unsafe caption seed accepted',field)
    for field,value in [('kind','EXPLICIT_PERFORMANCE_LOOKUP'),('target','foreign.json')]:
        changed=json.loads(json.dumps(section));changed['ownership']['chain'][0][field]=value
        assert not caption_owned(document,changed),('Unsafe caption first edge accepted',field)
    changed=json.loads(json.dumps(section));changed['ownership']['chain']=[]
    assert not caption_owned(document,changed),'Empty caption chain accepted'
    assert not caption_owned({'id':'quest-foreign'},section),'Foreign mission caption accepted'
    changed=json.loads(json.dumps(section));changed['ownership']['ownershipSeed'].pop('source');changed['ownership']['chain'][0].pop('source')
    assert not caption_owned(document,changed),'Both missing source identities accepted'
    owner='quest-'+str(section['ownership']['missionId'])
    assert caption_owned({'id':'quest-parent','missionParts':[owner]},section),'Exact preserved alias part rejected'
    return {'sourceRowsBySeed':dict(measured),'mutationsRejected':10}


def difference(actual,expected):
    offset=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
    return {'firstDifference':offset,'actualLength':len(actual),'expectedLength':len(expected),
            'actualContext':actual[max(0,offset-20):offset+35],
            'expectedContext':expected[max(0,offset-20):offset+35]}


def main(dist):
    root=Path(__file__).resolve().parents[1]
    caption_scope_self_test(root)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    source_catalog=read(root/'data/catalog.json')
    quests=[d for d in source_catalog if d['category']=='퀘스트']
    supplements_data=read(root/'data/mission-dialogue-supplements.json')
    original_captions=read(root/'data/official-video-captions.json')['missions']
    source_aliases=read(root/'data/aliases.json')
    captions={}
    for owner,scenes in original_captions.items():
        target=source_aliases.get(owner,owner)
        original=read(root/'data/documents'/(target+'.json'))
        assert owner in original.get('missionParts',[target]),'Caption owner missing from preserved mission parts: '+owner
        captions.setdefault(target,[]).extend(scenes)
    supplement={mid:[*supplements_data['missions'].get(mid,[]),*captions.get(mid,[])] for mid in set(supplements_data['missions'])|set(captions)}
    coverage=supplements_data.get('coverage',{})
    built_catalog=read(dist/'reading-catalog.json')
    built_quests={d['id']:d for d in built_catalog if d['category']=='퀘스트'}
    versions=read(dist/'versions-data.json')
    evidence=read(root/'editorial/mission-versions.json')
    aliases=read(root/'data/aliases.json')
    errors,stats=[],Counter()
    def require(condition,error,**context):
        if not condition:errors.append({'error':error,**context})
    ids={d['id'] for d in quests}
    require(set(built_quests)==ids,'reading catalogue quest coverage differs')
    require(len([d for d in built_catalog if d['category']=='퀘스트'])==len(ids),
            'reading catalogue contains duplicate quest IDs')
    require(set(versions)==ids,'version metadata quest coverage differs')
    catalogue_bytes=(dist/'reading-catalog.json').read_bytes()
    expected_catalogue_version=hashlib.sha256(catalogue_bytes).hexdigest()[:12]
    browse_candidates={dist/name for name in ('index.html','시작.html','설정집.html')}
    for folder in ('versions','quests'):
        browse_candidates.update((dist/folder).glob('*.html'))
    required_browse={dist/'index.html',dist/'versions/1.0.html'}
    for page_path in sorted(browse_candidates):
        require(page_path.exists(),'browse wrapper page missing',page=str(page_path.relative_to(dist)))
        if not page_path.exists():continue
        bindings=BrowseBindings();bindings.feed(page_path.read_text(encoding='utf8'))
        if page_path in required_browse:
            require(bool(bindings.catalogues),'required page lacks Browse catalogue binding',page=str(page_path.relative_to(dist)))
        for endpoint in bindings.catalogues:
            parsed=urlsplit(endpoint)
            require(not parsed.scheme and not parsed.netloc and parsed.path==BASE+'/reading-catalog.json'
                    and parse_qs(parsed.query).get('v')==[expected_catalogue_version] and not parsed.fragment,
                    'Browse catalogue cache version differs from actual API bytes',
                    page=str(page_path.relative_to(dist)),endpoint=endpoint,expectedVersion=expected_catalogue_version)
            stats['browseCatalogueBindings']+=1
    part_versions={}
    for id,parent in aliases.items():
        if id in evidence['missions']:
            part_versions.setdefault(parent,set()).add(evidence['missions'][id])
    for item in quests:
        id=item['id']
        doc=read(root/'data/documents'/(id+'.json'))
        related=[]
        related_sections=[]
        mission_coverage=coverage.get(id,{})
        ownership=mission_coverage.get('sourceOwnership',{})
        require(isinstance(ownership,dict),'mission source ownership map invalid',quest=id)
        if not isinstance(ownership,dict):ownership={}
        # Preserve first document position and first fallback proof; any explicit
        # main-mission reference outranks a folder-only fallback for the same ID.
        message_refs={}
        for ref in mission_coverage.get('relatedDocuments',[]):
            key=ref.get('id') or ref.get('docId')
            prior=message_refs.get(key)
            if prior is None or (not explicitly_owned(prior.get('ownership')) and explicitly_owned(ref.get('ownership'))):
                message_refs[key]=ref
        canary_messages={'quest-1034108':{'message-1307000','message-1307100'},
                         'quest-8000177':{'message-1113500'}}.get(id,set())
        for message_id in canary_messages:
            ref=message_refs.get(message_id)
            require(ref is not None and explicitly_owned(ref.get('ownership')),
                    'explicit message proof lost to fallback deduplication',quest=id,document=message_id)
        for ref in message_refs.values():
            related_id=ref.get('id') or ref.get('docId')
            require(isinstance(related_id,str) and related_id.startswith('message-'),
                    'related message document ID is invalid',quest=id,reference=ref)
            if not isinstance(related_id,str) or not related_id.startswith('message-'):continue
            source_path=root/'data/documents'/(related_id+'.json')
            require(source_path.is_file(),'related message source document missing',quest=id,document=related_id)
            if not source_path.is_file():continue
            source_bytes=source_path.read_bytes()
            message=json.loads(source_bytes.decode('utf-8'))
            require(hashlib.sha256(source_bytes).hexdigest()==ref.get('sha256'),
                    'related message source SHA differs',quest=id,document=related_id)
            require(message['id']==related_id and message['category']=='메시지',
                    'related document identity or category differs',quest=id,document=related_id)
            require(message['title']==ref.get('title'),
                    'related message title differs',quest=id,document=related_id)
            require(bool(ref.get('referenceSource')) and bool(ref.get('pointer')) and
                    bool(re.fullmatch(r'[0-9a-f]{64}',ref.get('referenceSourceSha256',''))),
                    'related message structure source proof incomplete',quest=id,document=related_id)
            related.append((ref,message))
            for section in message['sections']:
                related_sections.append({**section,'anchor':'mission-message-'+message['id']+'-'+section['anchor'],
                                         '_messageOwnership':ref.get('ownership',[])})
        sections=[*doc['sections'],*supplement.get(id,[]),*related_sections]
        def linked(section):
            if section.get('recordType')=='CUTSCENE_CAPTION':
                return caption_owned(doc,section)
            chain=section['_messageOwnership'] if '_messageOwnership' in section else ownership.get(section.get('source'),section.get('ownership',[]))
            return explicitly_owned(chain)
        scopes=mission_coverage.get('sourceTalkScopes',{})
        for source,chain in ownership.items():
            if explicitly_owned(chain) and any(edge.get('kind')=='EXPLICIT_SUBMISSION_FINISH_SCOPE' and edge.get('target')==source for edge in chain):
                require(source in scopes and isinstance(scopes[source].get('talkIds'),list),
                        'shared source ownership lacks exact dialogue scope',quest=id,source=source)
        primary,reference=[],[]
        for section in sections:
            scope=scopes.get(section.get('source')) if '_messageOwnership' not in section and section.get('recordType')!='CUTSCENE_CAPTION' else None
            selected,remaining=[],[]
            for i,row in enumerate(section['rows'],1):
                located={**row,'readerRowAnchor':section['anchor']+'-row-'+str(i)}
                target=selected if linked(section) and (not scope or row.get('talk_id') in scope['talkIds']) else remaining
                target.append(located)
            if selected:primary.append({**section,'rows':selected})
            if remaining:reference.append({**section,'anchor':section['anchor']+'-reference' if selected else section['anchor'],'rows':remaining})
        active=[*primary,*reference]
        expected=[]
        for s in active:
            for i,row in enumerate(s['rows'],1):
                expected.append((row['readerRowAnchor'],row,s in reference))
        anchors=[a for a,_,_ in expected]
        require(len(set(anchors))==len(anchors),'source row anchors collide',quest=id)
        source_kinds=Counter(passage(row) for s in primary for row in s['rows'])
        choices=source_kinds['choice'];dialogues=source_kinds['dialogue'];gaps=source_kinds['gap'];caption_count=source_kinds['caption']
        require(choices+dialogues+gaps+caption_count==sum(len(s['rows']) for s in primary),
                'primary source rows are not partitioned into dialogue/choice/gap',quest=id)
        state='dialogue-linked' if dialogues else 'captions-linked' if caption_count else 'choices-only' if choices else 'overview-only'
        counts={'dialogueCount':dialogues,'captionCount':caption_count,'choiceCount':choices,'gapCount':gaps,'sceneCount':len(primary),
                'referenceRows':sum(len(s['rows']) for s in reference),'referenceSceneCount':len(reference),'state':state}
        counts['count']=item['count']+sum(len(s['rows']) for s in supplement.get(id,[]))+sum(len(s['rows']) for s in related_sections)
        if id=='quest-1000400':
            canary=[s for s in active if s.get('source')=='Config/Level/Mission/1000401/Act/Act100040101.json']
            require(bool(canary),'Kafka cross-mission ownership canary source missing',quest=id)
            require(all(not linked(s) for s in canary),'Kafka cross-mission dialogue incorrectly owned by mission',quest=id)
        built=built_quests.get(id,{})
        expected_title=expected_mission_title(doc)
        require(built.get('title')==expected_title,'reading catalogue display title differs from source-aware expectation',quest=id,expected=expected_title,actual=built.get('title'))
        stats['displayTitlesChecked']+=1
        stats['displayTitleFallbacks' if expected_title!=doc.get('title') else 'unchangedSourceTitles']+=1
        for field,value in counts.items():
            require(built.get(field)==value,'reading catalogue field differs',quest=id,field=field,expected=value,actual=built.get(field))
        observed={evidence['missions'].get(id,'unknown'),*part_versions.get(id,set())}
        expected_versions=observed|({'early'} if any(re.fullmatch(r'\d+\.\d+',v) and float(v)<=2.6 for v in observed) else set())
        require(set(versions.get(id,[]))==expected_versions,'mission versions differ from evidence mapping',quest=id)
        require(set(built.get('versions',[]))==expected_versions,'reading catalogue versions differ',quest=id)
        for version in expected_versions:
            require((dist/'versions'/(version+'.html')).is_file(),'version reader page missing',quest=id,version=version)
        path=dist/'문서'/(id+'.html')
        if not path.is_file():
            errors.append({'error':'mission document missing','quest':id})
            continue
        html=path.read_text(encoding='utf-8')
        template=ReadingTemplatePage();template.feed(html)
        for error in template.finish():require(False,error,quest=id)
        page=MissionPage()
        page.feed(html)
        require([''.join(parts).strip() for parts in page.headings]==[expected_title.strip()],'mission page h1 differs from source-aware expectation',quest=id,expected=expected_title,actual=[''.join(parts).strip() for parts in page.headings])
        for ref,message in related:
            original_url=BASE+'/'+message['url'].lstrip('/')
            require(original_url in page.reader_links,'inline message original document link missing',quest=id,
                    document=message['id'],expected=original_url)
        require(page.reader_states==[state],'mission reader state differs from primary sources',quest=id,expected=state,actual=page.reader_states)
        require(len(page.references)==(1 if reference else 0),'reference dialogue container count differs',quest=id)
        for container in page.references:
            require(container['tag']=='details' and 'open' not in container['attrs'],
                    'reference dialogue is not initially collapsed',quest=id)
        if reference:
            require(bool(page.reference_summaries) and ''.join(page.reference_summaries[0]).startswith('임무 자료의 추가 대화'),
                    'reference dialogue label missing',quest=id)
        scope_notes={note['sectionId']:note for note in page.scope_notes}
        require(len(scope_notes)==len(reference),'reference source scope note missing or duplicated',quest=id)
        for section in reference:
            note=scope_notes.get(section['anchor'],{})
            scoped=bool(scopes.get(section.get('source')))
            expected_note='이 묶음은 아래에 표시한 임무 연결 범위 밖의 원문입니다.' if scoped else '임무 자료에 함께 수록된 추가 원문입니다.'
            require(note.get('isReference') and ''.join(note.get('text',[]))==expected_note,
                    'reference source proof implies primary row ownership',quest=id,anchor=section['anchor'])
        require(len(page.readers)==1,'primary mission reader count differs',quest=id,actual=len(page.readers))
        for anchor in ('original','linked-dialogue'):
            require(page.ids[anchor]==1,'primary reader legacy anchor missing or duplicated',quest=id,anchor=anchor)
        for anchor,count in page.ids.items():
            require(count==1,'duplicate DOM anchor',quest=id,anchor=anchor,count=count)
        if doc['stages']:
            require(len(page.progress_positions)==1,'mission progress section missing or duplicated',quest=id)
            if page.readers and page.progress_positions:
                require(page.readers[0]<page.progress_positions[0],'progress appears before original reader',quest=id)
            for step in doc['stages']:
                anchor='stage-'+str(step['id'])
                require(page.ids[anchor]==1,'legacy stage anchor missing or duplicated',quest=id,anchor=anchor)
                stats['stageAnchors']+=1
        actual_sections=[s['id'] for s in page.sections if s['insideReader']]
        expected_location={s['anchor']:s in reference for s in active}
        for section in page.sections:
            if section['insideReader'] and section['id'] in expected_location:
                require(section['isPrimary']==(not expected_location[section['id']]),
                        'scene primary reader container placement differs',quest=id,anchor=section['id'])
                require(section['isReference']==expected_location[section['id']],
                        'scene mission ownership placement differs',quest=id,anchor=section['id'])
        require(Counter(actual_sections)==Counter(s['anchor'] for s in active),
                'primary reader section coverage differs',quest=id)
        actual=[]
        for row in page.rows:
            require(row['insideReader'],'original row rendered outside primary reader',quest=id)
            require(len(row['bodies'])==1,'original row body count differs',quest=id,actual=len(row['bodies']))
            for body in row['bodies']: actual.append((body['id'],row,body))
        require([a for a,_,_ in actual]==anchors,'original row order, coverage or duplication differs',quest=id,
                actualRows=len(actual),expectedRows=len(expected))
        actual_by_anchor={a:(r,b) for a,r,b in actual}
        for anchor,source,is_reference in expected:
            if anchor not in actual_by_anchor:continue
            rendered,body=actual_by_anchor[anchor]
            require(rendered['isPrimary']==(not is_reference),'row primary reader container placement differs',quest=id,anchor=anchor)
            require(rendered['isReference']==is_reference,'row mission ownership placement differs',quest=id,anchor=anchor)
            text=''.join(body['text'])
            require(text==source['text'],'primary reader original text differs',quest=id,anchor=anchor,
                    **(difference(text,source['text']) if text!=source['text'] else {}))
            require(body['paragraphs']>0,'original paragraph spans missing',quest=id,anchor=anchor)
            require(rendered['attrs'].get('data-speaker')==(source.get('speaker') or '화자 미지정'),
                    'reader speaker filter attribution differs',quest=id,anchor=anchor)
            require(rendered['attrs'].get('data-passage')==passage(source),
                    'reader dialogue/choice/gap filter semantics differ',quest=id,anchor=anchor)
            stats['originalRows']+=1
            stats['originalParagraphSpans']+=body['paragraphs']
        count_texts=[''.join(x) for x in page.count_texts]
        expected_header=f'대사 {dialogues:,}행 · 선택지 {choices:,}개 · 장면 {len(primary):,}개'
        if caption_count:expected_header+=f' · 영상 자막 {caption_count:,}행'
        require(len(count_texts)==1 and count_texts[0].startswith(expected_header),'visible reader count differs',quest=id,expectedPrefix=expected_header,actual=count_texts)
        if gaps:
            require(bool(count_texts) and bool(re.search(r'(?:본문 연결 확인|미연결|누락)\s*'+re.escape(f'{gaps:,}')+r'(?:행|개)',count_texts[0])),
                    'visible source gap count missing or differs',quest=id,gapCount=gaps,actual=count_texts)
        if state=='overview-only':
            require(bool(page.coverage_texts),'zero dialogue mission lacks coverage disclosure',quest=id)
            text=''.join(''.join(x) for x in page.coverage_texts)
            require('임무 개요' in text and '연결' in text,'zero dialogue disclosure does not describe coverage boundary',quest=id)
        stats[state]+=1
        stats['quests']+=1
        stats['scenes']+=len(primary)
        stats['referenceScenes']+=len(reference)
        stats['referenceRows']+=counts['referenceRows']
        stats['choices']+=choices
        stats['dialogueRows']+=dialogues
        stats['captionRows']+=caption_count
        stats['gapRows']+=gaps
        stats['inlineMessageDocuments']+=len(related)
        stats['inlineMessageRows']+=sum(len(s['rows']) for s in related_sections)
    print(json.dumps({'status':'PASS' if not errors else 'FAIL','scope':'all-mission-primary-and-reference-original-preservation',
                      **dict(stats),'errorsTotal':len(errors),'errorsByKind':dict(Counter(e['error'] for e in errors)),
                      'errors':errors[:25]},ensure_ascii=False))
    return bool(errors)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist',type=Path,default=Path(__file__).resolve().parents[1]/'dist')
    raise SystemExit(main(parser.parse_args().dist.resolve()))
