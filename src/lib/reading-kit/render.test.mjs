import test from 'node:test';import assert from 'node:assert/strict';import {createReadingKit,paragraphRuns,safeHref} from './render.mjs';
const kit=createReadingKit();
test('source text cannot create markup or nested paragraphs',()=>{const html=kit.source([{id:'raw',text:'첫 문단 <script>alert(1)</script>\n\n둘째 & 문단'}]);assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));assert.equal((html.match(/<p>/g)||[]).length,2);});
test('paragraph segmentation preserves every character',()=>{for(const text of ['a\n\nb','\n\na\n \nb\n','한 줄\n다음 줄'])assert.equal(paragraphRuns(text).map(p=>p.text+p.separator).join(''),text);});
test('unsafe and protocol-relative links fail',()=>{for(const url of ['javascript:alert(1)','data:text/html,a','//external.test'])assert.throws(()=>safeHref(url));assert.equal(safeHref('/문서/a.html#원문'),'/문서/a.html#원문');});
test('independent events do not imply chronology',()=>{assert.ok(kit.timeline([]).includes('data-order="independent"'));assert.ok(kit.timeline([],{ordered:true}).includes('data-order="source"'));});
test('cycles require a return relation',()=>{assert.throws(()=>kit.process([],{kind:'cycle'}));assert.ok(kit.process([],{kind:'cycle',returnLabel:'재처리'}).includes('재처리'));});
test('relation endpoints remain separate links',()=>{const html=kit.relations([{from:{name:'A',url:'/a.html'},to:{name:'B',url:'/b.html'},label:'보호한다',reason:'근거 문장'}]);assert.equal((html.match(/<a /g)||[]).length,2);assert.ok(html.includes('보호한다'));assert.ok(html.includes('근거 문장'));});
