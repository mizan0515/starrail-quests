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

test('ordinary relations have one predicate per band and evidence beside that relation',()=>{
 const source={id:'c',name:'크리스토포로',url:'/people/christoforo.html',kind:'인물'},focus={id:'a',name:'아비디우스',url:'/people/avidius.html',kind:'인물'},target={id:'g',name:'갈브레나',url:'/people/galbrena.html',kind:'인물'};
 const input=[{id:'form',from:source,to:focus,label:'형체를 제공했다고 말한다',reasonClaimId:'claim-1',claimKind:'attributed',speaker:'크리스토포로',reason:'크리스토포로의 설명',evidence:[{quote:'원문 1',url:'/quest#scene-42'}]},{id:'wish',from:focus,to:target,label:'힘과 소원을 맡긴다',reasonClaimId:'claim-2',claimKind:'attributed',speaker:'아비디우스',reason:'아비디우스의 부탁',evidence:[{quote:'원문 2',url:'/quest#scene-41'}]}];
 const before=JSON.stringify(input),html=createReadingKit({evidence:es=>es.map(e=>`<a href="${e.url}">${e.quote}</a>`).join('')}).network(input,{id:'structure',focusId:'a'});
 assert.equal((html.match(/class="rw-relation-band"/g)||[]).length,2);
 assert.ok(!html.includes('rw-map-incoming'));assert.ok(!html.includes('rw-map-canvas'));assert.ok(!html.includes('<svg'));
 assert.equal((html.match(/<strong>형체를 제공했다고 말한다<\/strong>/g)||[]).length,1);
 assert.ok(html.includes('발언·기록에 따른 관계 · 크리스토포로'));assert.ok(html.includes('발언·기록에 따른 관계 · 아비디우스'));
 assert.ok(html.includes('id="structure-edge-form"'));assert.ok(html.includes('id="structure-edge-wish"'));
 assert.ok(html.includes('href="/quest#scene-42"'));assert.ok(html.includes('href="/quest#scene-41"'));assert.equal(JSON.stringify(input),before);
});

test('editorial reading connections show reasons without an actor-action diagram',()=>{
 const relation={id:'reading',from:{id:'borisin',name:'보리인과 여우족'},to:{id:'paths',name:'에이언즈·운명의 길·파벌',url:'/paths'},label:'단륜사의 신앙과 비살생',reasonClaimId:'reason',claimKind:'inference',speaker:'군 교재',reason:'두 기록을 함께 읽는 이유',evidence:[{quote:'보존된 인용',url:'/book#row'}]};
 const html=createReadingKit({evidence:es=>es.map(e=>e.quote).join('')}).network([relation],{id:'structure'});
 assert.ok(html.includes('함께 읽을 설정'));assert.ok(html.includes('rw-reading-connection'));
 assert.ok(html.includes('편집자의 연결 · 보리인과 여우족에서 이어 읽기'));
 assert.ok(!html.includes('편집자의 연결 · 군 교재'));
 assert.ok(!html.includes('rw-relation-direction'));assert.ok(!html.includes('rw-relation-band-line'));
 assert.ok(html.includes('href="/paths"'));assert.ok(html.includes('id="structure-edge-reading"'));assert.ok(html.includes('두 기록을 함께 읽는 이유'));
});

test('source speakers remain visible in evidence for authored return diagrams',()=>{
 const t=base();t.edges[0].claimKind='attributed';t.edges[0].speaker='파수인';
 const html=createReadingKit().topology(t);
 assert.ok(html.includes('발언·기록에 따른 관계 · 파수인'));
 const invalid=base();invalid.presentation='unknown';assert.throws(()=>validateTopology(invalid),/presentation/);
});
