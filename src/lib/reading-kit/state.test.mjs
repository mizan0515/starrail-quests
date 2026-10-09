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

test('Back restores the clicked visible source link when earlier hidden proofs have the same URL',()=>{
 const href='https://example.test/source.html#field';
 const hidden={href,focused:false,getClientRects:()=>[],focus(){this.focused=true;}};
 const clicked={href,focused:false,getClientRects:()=>[{}],focus(){this.focused=true;}};
 const details=[{open:false},{open:true}],listeners={},events={};let stored=null,scroll=null;
 class Element {closest(){return clicked;}}
 const context={Element,location:{pathname:'/setting.html',search:'',hash:'',origin:'https://example.test'},scrollY:735,
  document:{getElementById(){return null;},querySelectorAll(selector){return selector==='main details'?details:[hidden,clicked];},addEventListener(name,handler){events[name]=handler;}},
  window:{addEventListener(name,handler){listeners[name]=handler;},scrollTo(x,y){scroll=y;}},
  sessionStorage:{getItem(){return stored;},setItem(key,value){stored=value;}},requestAnimationFrame:cb=>cb(),performance:{getEntriesByType(){return [{type:'back_forward'}];}},URL};
 vm.runInNewContext(source,context);events.click({target:new Element()});
 assert.equal(JSON.parse(stored).followedIndex,1);
 details[1].open=false;listeners.pageshow({persisted:false});
 assert.equal(details[1].open,true);assert.equal(clicked.focused,true);assert.equal(hidden.focused,false);assert.equal(scroll,735);
 clicked.focused=false;stored=JSON.stringify({open:[false,true],followed:href,scrollY:735});listeners.pageshow({persisted:true});
 assert.equal(clicked.focused,true);assert.equal(hidden.focused,false);
});
