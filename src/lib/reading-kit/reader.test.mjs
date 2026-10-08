import test from 'node:test';import assert from 'node:assert/strict';
import {readerAttributes,rowAttributes,disclosureAttributes,readerFrame,readerDisclosure,sourceLinkAttributes,sourceLink} from './reader.mjs';
test('source adapters share an isolated HTML boundary and retain supplied body',()=>{const raw='<p>첫 문장 &amp; 둘째 문장</p>';const frame=readerFrame(raw,{id:'scene-1',label:'대사'});assert.ok(frame.includes('rw-reader not-content'));assert.ok(frame.includes('data-reading-template="reader"'));assert.ok(frame.endsWith(raw+'</div>'));assert.equal(readerAttributes({className:'source-section'}).class,'rw-reader not-content source-section');});
test('disclosure owns one immediate native summary and escapes its label',()=>{const html=readerDisclosure('출처 <식별자>','<dl><dt>자료</dt><dd>원문</dd></dl>',{className:'source-details',open:true,attributes:{'data-pagefind-ignore':''}});assert.equal((html.match(/<summary>/g)||[]).length,1);assert.ok(html.includes('출처 &lt;식별자&gt;'));assert.ok(!html.includes('▶'));assert.ok(html.includes('data-pagefind-ignore=""'));assert.ok(html.includes(' open>'));assert.throws(()=>disclosureAttributes({attributes:{onclick:'alert(1)'}}));});
test('row kinds distinguish original text, choices and source gaps',()=>{for(const kind of ['dialogue','choice','gap','branch','original'])assert.equal(rowAttributes(kind)['data-reading-kind'],kind);assert.throws(()=>rowAttributes('made-up'));});
test('source links separate local reading return behavior from external provenance',()=>{
 const local=sourceLink('/starrail-quests/문서/message-1506201.html#section-1','메시지 원문 · 1506201',{reading:true,id:'message-original'});
 assert.ok(local.includes('data-reading-template="source-link"'));assert.ok(local.includes('data-reading-link'));assert.ok(local.includes('id="message-original"'));assert.ok(local.includes('#section-1'));
 const external=sourceLink('https://example.com/source?q=1&v=2','원문 출처');
 assert.ok(external.includes('q=1&amp;v=2'));assert.ok(!external.includes('data-reading-link'));
 assert.equal(sourceLinkAttributes({reading:false,variant:'inline'})['data-source-link-variant'],'inline');
 assert.throws(()=>sourceLink('https://example.com','외부',{reading:true}),/must be local/);
});
test('source link text and attributes escape markup without admitting unsafe URLs or options',()=>{
 const html=sourceLink('/source#row','원문 <표> & 기록',{className:'proof" onclick="evil',id:'row"',variant:'inline'});
 assert.ok(html.includes('원문 &lt;표&gt; &amp; 기록'));assert.ok(html.includes('proof&quot; onclick=&quot;evil'));assert.ok(html.includes('id="row&quot;"'));
 for(const url of ['javascript:alert(1)','//other.example/source','/source\\evil','/source\nnext'])assert.throws(()=>sourceLink(url,'자료'));
 assert.throws(()=>sourceLinkAttributes({variant:'made-up'}));assert.throws(()=>sourceLinkAttributes({reading:'false'}));
});
