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

test('a filter URL changed after load owns its saved link and focus state on a fresh Back navigation',()=>{
 const href='https://example.test/subject.html',saved=new Map();
 let scroll=null;
 const make=(search,type)=>{
  const clicked={href,focused:false,getClientRects:()=>[{}],focus(){this.focused=true;}},events={},listeners={};
  class Element{closest(){return clicked;}}
  const context={Element,location:{pathname:'/directory.html',search,hash:'',origin:'https://example.test'},scrollY:432,
   document:{getElementById(){return null;},querySelectorAll(selector){return selector==='main details'?[]:[clicked];},addEventListener(name,handler){events[name]=handler;}},
   window:{addEventListener(name,handler){listeners[name]=handler;},scrollTo(x,y){scroll=y;}},
   sessionStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)},requestAnimationFrame:cb=>cb(),performance:{getEntriesByType:()=>[{type}]},URL};
  vm.runInNewContext(source,context);return {context,clicked,events,listeners,Element};
 };
 const outgoing=make('','navigate');outgoing.context.location.search='?q=academy';
 outgoing.events.click({target:new outgoing.Element()});outgoing.listeners.pagehide();
 assert.ok(saved.has('reading-state.v1:/directory.html?q=academy'));
 assert.equal(saved.has('reading-state.v1:/directory.html'),false);
 const returning=make('?q=academy','back_forward');returning.listeners.pageshow({persisted:false});
 assert.equal(returning.clicked.focused,true);assert.equal(scroll,432);
});

test('Back waits for an asynchronously rendered visible catalog link and then disconnects',()=>{
 const href='https://example.test/subject.html?from=%2Fcatalog%3Fq%3Da';
 const clicked={href,focused:false,getClientRects:()=>[{}],focus(){this.focused=true;}};
 let links=[],observer,scroll=null;const listeners={};
 class MutationObserver{constructor(callback){this.callback=callback;observer=this;}observe(){this.connected=true;}disconnect(){this.connected=false;}}
 const context={MutationObserver,location:{pathname:'/catalog',search:'?q=a',hash:''},document:{body:{},getElementById(){return null;},querySelector(){return {};},querySelectorAll:selector=>selector==='main details'?[]:links,addEventListener(){}},window:{addEventListener:(name,cb)=>listeners[name]=cb,scrollTo:(x,y)=>scroll=y},sessionStorage:{getItem:()=>JSON.stringify({open:[],followed:href,followedIndex:0,scrollY:512})},requestAnimationFrame:cb=>cb(),performance:{getEntriesByType:()=>[{type:'back_forward'}]},setTimeout:()=>1,clearTimeout(){},URL};
 vm.runInNewContext(source,context);listeners.pageshow({persisted:false});
 assert.equal(observer.connected,true);assert.equal(clicked.focused,false);
 links=[clicked];observer.callback();
 assert.equal(clicked.focused,true);assert.equal(scroll,512);assert.equal(observer.connected,false);
});
