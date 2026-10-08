import test from 'node:test';
import assert from 'node:assert/strict';
import {safeReadingReturn} from '../src/lib/reading-return.mjs';
const origin='https://mizan0515.github.io',base='/starrail-quests';
const safe=value=>safeReadingReturn(value,{origin,base});
const reading='/starrail-quests/문서/quest-1010203.html';
const make=(path,from)=>path+'?speaker='+encodeURIComponent('단항')+'&passage=dialogue&from='+encodeURIComponent(from)+'#quest-1010203-scene-1-row-3';
const resolved=value=>new URL(value,origin);

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

test('catalogue allowlist and one-level chain limit',()=>{
 for(const path of ['index.html','versions/early.html','quests/main.html','설정집.html']) {
  const out=resolved(safe(make(reading,base+'/'+path+'?q=abc&from='+encodeURIComponent(reading))));
  const catalogue=resolved(out.searchParams.get('from'));
  assert.equal(decodeURI(catalogue.pathname),base+'/'+path);
  assert.equal(catalogue.searchParams.get('q'),'abc');
  assert.equal(catalogue.searchParams.has('from'),false);
 }
});

test('unsafe reading origins and malformed/encoded paths are rejected',()=>{
 for(const bad of [null,'','https://evil.example'+reading,'//evil.example'+reading,
  '/wuwa-quests/문서/q.html',base+'/index.html',base+'/문서/%ZZ.html',
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
