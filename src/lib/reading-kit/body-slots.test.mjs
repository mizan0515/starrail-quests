import test from 'node:test';
import assert from 'node:assert/strict';
import {renderCvaModule} from './cva.mjs';
const raw='인물의 원문 <태그> & 기호',body='<a data-reading-link href="/person.html">인물</a>의 원문 &lt;태그&gt; &amp; 기호';
test('body link slots preserve each exact input record and allow adjacent original proof',()=>{
 for(const [type,variant] of [['cards','grid'],['comparison','columns'],['comparison','table'],['scene-composition','quest-route'],['scene-composition','feedback-ring'],['scene-composition','nested-world']]){
  const input={id:'body-slots',type,variant,items:[{id:'a',title:'첫 기록',body:raw},{id:'b',title:'둘째 기록',body:raw}],itemBodies:[body,body],itemExtras:['<details><summary>근거1</summary>원문1</details>','<details><summary>근거2</summary>원문2</details>']};
  const html=renderCvaModule(input),model=JSON.parse(html.match(/data-cva-model data-pagefind-ignore>([\s\S]*?)<\/script>/)[1]);
  assert.deepEqual(model.modules[0].props.items,input.items);assert.equal(html.split(body).length-1,2);assert.ok(html.includes('근거1'));assert.ok(html.includes('근거2'));
 }
 const base={id:'unsafe-bodies',type:'cards',variant:'grid',items:[{id:'a',title:'A',body:raw}]};
 for(const active of ['<script>alert(1)</script>','<a onclick="evil">인물</a>'])assert.throws(()=>renderCvaModule({...base,itemBodies:[active]}),/active HTML/);
 assert.throws(()=>renderCvaModule({...base,itemBodies:[body,body]}),/input item order/);
});
