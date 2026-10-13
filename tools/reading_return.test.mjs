import test from 'node:test';
import assert from 'node:assert/strict';
import {safeReadingReturn,sourceReadingOrigin,isReadingCatalogue} from '../src/lib/reading-return.mjs';
const origin='https://mizan0515.github.io',base='/starrail-quests';
const safe=value=>safeReadingReturn(value,{origin,base});
const reading='/starrail-quests/문서/quest-1010203.html';
const make=(path,from)=>path+'?speaker='+encodeURIComponent('단항')+'&passage=dialogue&from='+encodeURIComponent(from)+'#quest-1010203-scene-1-row-3';
const resolved=value=>new URL(value,origin);

test('configuration range and edition readers return to the exact original without admitting arbitrary dialogue routes',()=>{
 const catalogue=base+'/대화.html#source-records';
 for(const [path,anchor] of [['범위-range-0aeda0e1f644fa52','talk-146787410-1'],['판본-202196417','talk-202196417-previous']]){
  const source=base+'/대화/'+path+'.html?from='+encodeURIComponent(catalogue)+'#'+anchor;
  const out=resolved(safe(source));
  assert.equal(out.hash,'#'+anchor);
  assert.equal(out.searchParams.get('from'),safe(catalogue));
  assert.equal(sourceReadingOrigin(base+'/대상/person-1407.html',source,{origin,base}),safe(source));
  assert.equal(isReadingCatalogue(source,{origin,base}),false);
 }
 for(const invalid of ['범위-range-123','범위-0aeda0e1f644fa52','판본-0','판본-abc','판본-202196417.html/../outside'])assert.equal(safe(base+'/대화/'+invalid+'.html'),null);
});

test('native, snapshot and Lua supplements retain the source sentence and filtered catalogue',()=>{
 const catalogue=base+'/대화/연출-목록-87.html?timelineQuery='+encodeURIComponent('파멸')+'&timelineMission='+encodeURIComponent('깊은 곳에 이른 혼란')+'&timelineLimit=36#universe-source-fresh-timeline-336dc14f509933f8b7f7';
 for(const [id,anchor] of [['fresh-timeline-336dc14f509933f8b7f7','talk-100020213-1'],['snapshot-timeline-31028fa3a55aee4f1abf','talk-103272902-1'],['lua-timeline-9192c8b22d0d8304','lua-screen-105009004-4']]){
  const source=base+'/대화/연출-'+id+'.html?from='+encodeURIComponent(catalogue)+'#'+anchor;
  const out=resolved(safe(source));
  assert.equal(out.hash,'#'+anchor);
  assert.equal(out.searchParams.get('from'),safe(catalogue));
  assert.deepEqual([...resolved(out.searchParams.get('from')).searchParams],[...resolved(catalogue).searchParams]);
  assert.equal(sourceReadingOrigin(base+'/대사/early-064.html',source,{origin,base}),safe(source));
  assert.equal(isReadingCatalogue(source,{origin,base}),false);
 }
 for(const invalid of ['fresh-timeline-336dc14f509933f8','snapshot-timeline-31028fa3a55aee4f','lua-timeline-9192c8b22d0d83041234','unknown-timeline-336dc14f509933f8b7f7','fresh-timeline-336dc14f509933f8b7f7.html/../outside'])assert.equal(safe(base+'/대화/연출-'+invalid+'.html'),null);
});

test('typed Timeline scene preserves filtered directory and exact repeated occurrence',()=>{
 const directory=base+'/대화/연출-목록-4.html?timelineQuery='+encodeURIComponent('폼폼')+'&timelineLimit=36#universe-source-timeline-1234567890abcdef';
 const scene=base+'/대화/연출-timeline-1234567890abcdef.html?from='+encodeURIComponent(directory)+'#talk-103010309-2';
 const out=resolved(safe(scene));
 assert.equal(out.hash,'#talk-103010309-2');
 assert.equal(out.searchParams.get('from'),resolved(directory).pathname+resolved(directory).search+resolved(directory).hash);
 assert.equal(isReadingCatalogue(directory,{origin,base}),true);
 assert.equal(sourceReadingOrigin(base+'/대사/early-083.html',scene,{origin,base}),safe(scene));
 for(const invalid of ['대화/연출-arbitrary.html','대화/연출-timeline-123.html','대화/연출-목록-a.html','대화/연출-timeline-1234567890abcdef.html/../outside.html'])assert.equal(safe(base+'/'+invalid),null);
});

test('dialogue use scene retains paginated source catalogue query and exact Talk anchor',()=>{
 const catalogue=base+'/대화/목록-0-2.html?contextQuery='+encodeURIComponent('단항')+'&contextWorld='+encodeURIComponent('선주')+'&contextLimit=24#universe-source-context-8ca624144ab93fcc';
 const source=base+'/대화/context-8ca624144ab93fcc.html?from='+encodeURIComponent(catalogue)+'#talk-156020600';
 const out=resolved(safe(source));
 assert.equal(out.hash,'#talk-156020600');
 assert.equal(out.searchParams.get('from'),resolved(catalogue).pathname+resolved(catalogue).search+resolved(catalogue).hash);
 assert.equal(isReadingCatalogue(catalogue,{origin,base}),true);
 assert.equal(safe(base+'/대화/context-../../outside.html'),null);
 assert.equal(safe(base+'/대화/not-a-context.html'),null);
});

test('setting → original retains Korean reading location, filters, exact anchor and version catalogue',()=>{
 const catalogue='/starrail-quests/versions/1.0.html?q='+encodeURIComponent('벨로보그')+'&kind=main&limit=840#results';
 const out=resolved(safe(make(reading,catalogue)));
 assert.equal(decodeURI(out.pathname),reading);
 assert.equal(out.searchParams.get('speaker'),'단항');
 assert.equal(out.searchParams.get('passage'),'dialogue');
 assert.equal(out.hash,'#quest-1010203-scene-1-row-3');
 assert.equal(out.searchParams.get('from'),catalogue);
 assert.equal(safe(out.pathname+out.search+out.hash),out.pathname+out.search+out.hash);
});

test('source → source inherits original location rather than a growing reading loop',()=>{
 const original=safe(make(reading,'/starrail-quests/index.html?q=1010203&version=1.0'));
 assert.equal(safe(original),original);
 const loop=resolved(safe(make(reading,'/starrail-quests/대사/other.html?from='+encodeURIComponent(original))));
 assert.equal(loop.searchParams.has('from'),false);
 assert.equal(loop.hash,'#quest-1010203-scene-1-row-3');
});

test('universe records retain their filtered list and exact reading anchor',()=>{
 const catalogue=base+'/우주/divergent-universe.html?recordQuery='+encodeURIComponent('소멸파')+'&recordLimit=24#universe-source-divergent-universe-150100';
 assert.equal(safe(catalogue),resolved(catalogue).pathname+resolved(catalogue).search+resolved(catalogue).hash);
 const record=base+'/우주/기록/divergent-universe-150100.html?from='+encodeURIComponent(catalogue)+'#divergent-universe-150100-scene-1-row-1';
 const out=resolved(safe(record));
 assert.equal(out.searchParams.get('from'),resolved(catalogue).pathname+resolved(catalogue).search+resolved(catalogue).hash);
 assert.equal(out.hash,'#divergent-universe-150100-scene-1-row-1');
 assert.equal(safe(base+'/우주/기록/../../outside.html'),null);
 assert.equal(safe(base+'/우주/기록/a%2fb.html'),null);
});

test('official universe text retains its kind, query, expanded list and exact field',()=>{
 const catalogue=base+'/우주/divergent-universe.html?textQuery='+encodeURIComponent('황금')+'&textKind=formula&textLimit=36#universe-source-official46-formula-10114000';
 const path=base+'/우주/설정/official46-formula-10114000.html';
 const source=path+'?from='+encodeURIComponent(catalogue)+'#official46-formula-10114000-FormulaStory-body';
 const out=resolved(safe(source));
 assert.equal(decodeURI(out.pathname),path);
 assert.equal(out.searchParams.get('from'),resolved(catalogue).pathname+resolved(catalogue).search+resolved(catalogue).hash);
 assert.equal(out.hash,'#official46-formula-10114000-FormulaStory-body');
 assert.equal(safe(out.pathname+out.search+out.hash),out.pathname+out.search+out.hash);
 assert.equal(safe(base+'/우주/설정/../../outside.html'),null);
 assert.equal(safe(base+'/우주/설정/a%2fb.html'),null);
});

test('catalogue allowlist and one-level chain limit',()=>{
 for(const path of ['index.html','versions/early.html','quests/main.html','설정집.html']) {
  const out=resolved(safe(make(reading,base+'/'+path+'?q=abc&from='+encodeURIComponent(reading))));
  const catalogue=resolved(out.searchParams.get('from'));
  assert.equal(decodeURI(catalogue.pathname),base+'/'+path);
  assert.equal(catalogue.searchParams.get('q'),'abc');
  assert.equal(catalogue.searchParams.has('from'),false);
 }
});

test('official Talk originals retain their observed-version list, filters and exact row',()=>{
 const catalogue=base+'/대사/official-4.6.html?talkQuery='+encodeURIComponent('아이스구리')+'&talkKind=new&talkLimit=24#universe-source-official-4.6-412470001';
 const source=base+'/대사/official-4.6-412470001.html?from='+encodeURIComponent(catalogue)+'#talk-412470001';
 const out=resolved(safe(source));
 assert.equal(out.searchParams.get('from'),resolved(catalogue).pathname+resolved(catalogue).search+resolved(catalogue).hash);
 assert.equal(out.hash,'#talk-412470001');
 assert.equal(safe(out.pathname+out.search+out.hash),out.pathname+out.search+out.hash);
 for(const foreign of ['대사/official-4.5.html','대사/foreign.html','대사/official-4.6.html/../foreign.html'])
  assert.equal(resolved(safe(make(reading,base+'/'+foreign))).searchParams.has('from'),false);
});

test('unsafe reading origins and malformed/encoded paths are rejected',()=>{
 for(const bad of [null,'','https://evil.example'+reading,'//evil.example'+reading,
  '/wuwa-quests/문서/q.html',base+'/문서/%ZZ.html',
  base+'/문서/%2foutside.html',base+'/문서/%5cother.html',base+'/문서/%252fother.html',base+'/문서/%2e%2e/문서/q.html',
  base+'/문서/../../outside.html','https://user@'+new URL(origin).host+reading,
  base+'/문서/a.html\\evil',base+'/문서/a.html?x=%E0%A4']) assert.equal(safe(bad),null,bad);
 assert.equal(decodeURI(resolved(safe(base+'/%EB%AC%B8%EC%84%9C/q.html#original')).pathname),base+'/문서/q.html');
});

test('invalid nested return is dropped without losing the valid original',()=>{
 for(const bad of ['https://evil.example/index.html',base+'/people.html',base+'/versions/%ZZ.html',
  base+'/문서/q.html',base+'/versions/a%2fb.html','javascript:alert(1)']) {
  const out=resolved(safe(make(reading,bad)));
  assert.equal(out.searchParams.has('from'),false,bad);
  assert.equal(out.searchParams.get('speaker'),'단항');
  assert.equal(out.hash,'#quest-1010203-scene-1-row-3');
 }
});

test('every grouped directory and relic reader retains its exact entry and expanded state',()=>{
 for(const path of ['index.html','versions/4.4.html','quests/main.html','우주.html','대사.html','대화.html','설정집.html','세력.html','관점/person.html','관점/region.html','관점/concept.html','관점/aeon.html','관점/reference.html','유물.html']){
  const catalogue=base+'/'+path+'?find='+encodeURIComponent('기억')+'&entityLimit=72#explore-entry-lore-10023';
  const direct=resolved(safe(catalogue));
  assert.equal(direct.hash,'#explore-entry-lore-10023');
  assert.equal(direct.searchParams.get('entityLimit'),'72');
  const reader=resolved(safe(make(base+'/유물/relic-background-101-head.html',catalogue)));
  assert.equal(reader.searchParams.get('from'),direct.pathname+direct.search+direct.hash);
 }
 for(const path of ['관점/foreign.html','관점/a%2fb.html','유물/arbitrary.html','세력.html/../foreign.html'])assert.equal(safe(base+'/'+path),null,path);
});

test('a source reached from a directory keeps the source sentence as the context origin',()=>{
 const options={origin,base},catalogue=base+'/관점/person.html?find=엘리오&entityLimit=48#explore-entry-lore-10023';
 const source=base+'/대상/lore-10023.html?from='+encodeURIComponent(catalogue)+'#original';
 const location=sourceReadingOrigin(source,catalogue,options);
 assert.equal(isReadingCatalogue(catalogue,options),true);
 assert.equal(isReadingCatalogue(source,options),false);
 assert.equal(location,safe(source));
 const deeper=base+'/맥락/hunters.html?from='+encodeURIComponent(location)+'#structure';
 assert.equal(sourceReadingOrigin(deeper,location,options),location);
 for(const path of ['문서/quest-1010203.html','유물/relic-background-101-head.html','우주/기록/divergent-universe-150100.html']){
  const current=base+'/'+path+'?from='+encodeURIComponent(base+'/우주.html?itemLimit=72')+'#original';
  assert.equal(sourceReadingOrigin(current,base+'/우주.html?itemLimit=72',options),safe(current));
 }
});
