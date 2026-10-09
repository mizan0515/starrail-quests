import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('./state.mjs',import.meta.url),'utf8').replace(/^import .*;\r?\n/m,'');

test('direct proof anchors open the current template and focus its summary, including encoded IDs',()=>{
 for(const kind of ['rw-relation-proof','rw-map-evidence']){
  const id='proof/원문',summary={focused:false,focus(){this.focused=true;}},target={open:false,matches(selector){return selector.split(',').some(s=>s==='details.'+kind);},querySelector(){return summary;}};
  const listeners={},context={location:{pathname:'/people/a.html',search:'',hash:'#'+encodeURIComponent(id)},document:{getElementById(value){return value===id?target:null;},querySelectorAll(){return [];},addEventListener(){}},window:{addEventListener(name,handler){listeners[name]=handler;}},sessionStorage:{getItem(){return null;}},requestAnimationFrame:cb=>cb(),performance:{getEntriesByType(){return [];}},URL};
  vm.runInNewContext(source,context);
  assert.equal(target.open,true);assert.equal(summary.focused,true);
  summary.focused=false;listeners.pageshow({persisted:false});assert.equal(summary.focused,true);
  target.open=false;summary.focused=false;listeners.hashchange();assert.equal(target.open,true);assert.equal(summary.focused,true);
  context.location.hash='#%ZZ';assert.doesNotThrow(()=>listeners.hashchange());
 }
});
