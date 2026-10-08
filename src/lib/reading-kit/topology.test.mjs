import test from 'node:test';import assert from 'node:assert/strict';import {validateTopology,topologyFromRelations} from './topology.mjs';import {createReadingKit} from './render.mjs';
const base=()=>({id:'flow',title:'관계',nodes:[{id:'a',name:'A',url:'/a',layer:0},{id:'b',name:'B',url:'/b',layer:1}],edges:[{id:'e',from:'a',to:'b',label:'변환',claimId:'c',reason:'실제 근거',evidence:[{quote:'원문'}]}]});
test('missing endpoints and unsupported evidence fail',()=>{const t=base();t.edges[0].to='missing';assert.throws(()=>validateTopology(t));assert.throws(()=>validateTopology(base(),()=>false));});
test('relative scale requires explicit scope',()=>{const t=base();t.nodes[1].scale='compact';assert.throws(()=>validateTopology(t));t.scaleNote='상대적인 크기; 수치 미확인';assert.doesNotThrow(()=>validateTopology(t));});
test('split and convergence preserve every edge and shared endpoint',()=>{const node=id=>({id,name:id,url:'/'+id});const r=[['a','b'],['a','c'],['b','d'],['c','d']].map(([a,b],i)=>({id:String(i),from:node(a),to:node(b),label:'관계',reasonClaimId:'c',reason:'근거'}));const t=topologyFromRelations(r);assert.equal(t.nodes.length,4);assert.equal(t.edges.length,4);assert.equal(t.nodes.find(n=>n.id==='d').layer,2);});
test('diagram has accessible labels and individual links outside decorative SVG',()=>{const html=createReadingKit({evidence:es=>es.map(e=>e.quote).join('')}).topology(base());assert.ok(html.includes('aria-hidden="true"'));assert.ok(html.includes('실제 근거'));assert.ok(html.includes('원문'));assert.ok(html.includes('href="/b"'));assert.ok(!html.includes('<text'));});

const directed=(from,to,label,id='edge')=>({id:'scar-map',title:'스카의 관계',nodes:[{id:'source',name:from,layer:0},{id:'target',name:to,layer:1,focus:true}],edges:[{id,from:'source',to:'target',label,claimId:'proof',reason:'원문 연결',evidence:[{quote:'보존된 원문',url:'/source#row'}]}]});
test('Scar incoming actions identify Jinhsi and Christoforo at every visible card link',()=>{
 for(const [subject,predicate]of [['금희','체포한다'],['크리스토포로','흑조를 통한 이동 방법을 설명한다']]) {
  const t=directed(subject,'스카',predicate),before=JSON.stringify(t),html=createReadingKit({evidence:es=>es.map(e=>`<a href="${e.url}">${e.quote}</a>`).join('')}).topology(t);
  const link=html.match(/<a class="rw-map-incoming"[^>]*>([\s\S]*?)<\/a>/)[0];
  const visible=link.replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
  assert.equal(visible,`${subject} → ${predicate} → 스카 ↗`);
  assert.ok(!link.includes('<small>'));
  for(const word of [subject,predicate,'스카'])assert.ok(link.includes(word));
  assert.ok(link.includes(`aria-label="주체: ${subject}. 관계: ${predicate}. 상대: 스카. 원문 근거 보기"`));
  assert.ok(!link.includes('rw-mobile-origin'));
  assert.ok(html.includes(`summary aria-label="주체: ${subject}. 관계: ${predicate}. 상대: 스카. 원문 근거"`));
  assert.ok(html.includes('href="/source#row"'));assert.equal(JSON.stringify(t),before);
 }
});
test('split, convergence and return links always preserve source predicate target identities',()=>{
 const t=base();t.nodes.push({id:'c',name:'C',layer:1});t.edges.push({id:'split',from:'a',to:'c',label:'나누다',claimId:'c'},{id:'merge',from:'c',to:'b',label:'합류하다',claimId:'c'},{id:'cycle',from:'b',to:'a',label:'돌아가다',kind:'return',claimId:'c'});
 const html=createReadingKit().topology(t);
 for(const e of t.edges){const from=t.nodes.find(n=>n.id===e.from).name,to=t.nodes.find(n=>n.id===e.to).name;assert.ok(html.includes(`aria-label="주체: ${from}. 관계: ${e.label}. 상대: ${to}. 원문 근거 보기"`));}
 assert.equal((html.match(/class="rw-map-incoming"/g)||[]).length,t.edges.length);assert.ok(html.includes('rw-back-edge'));
});

test('nominal faction membership is rendered without inventing Korean grammar',()=>{
 const t=directed('스카','잔성회','잔성회 간부');
 const html=createReadingKit().topology(t),link=html.match(/<a class="rw-map-incoming"[^>]*>([\s\S]*?)<\/a>/)[0];
 assert.equal(link.replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim(),'스카 → 잔성회 간부 → 잔성회 ↗');
 assert.ok(link.includes('aria-label="주체: 스카. 관계: 잔성회 간부. 상대: 잔성회. 원문 근거 보기"'));
});
