import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {stripTypeScriptTypes} from 'node:module';
import test from 'node:test';
import {safeReadingReturn,sourceReadingOrigin} from '../src/lib/reading-return.mjs';
const astro=fs.readFileSync(new URL('../src/components/QuestReadingNav.astro',import.meta.url),'utf8');
const script=stripTypeScriptTypes(astro.split('<script>')[1].split('</script>')[0].replace(/^\s*import .*;$/gm,'').replace('import.meta.env.BASE_URL',"'/starrail-quests/'"));

function reader({search='',source=true,saved=null,hash='',padding=0,margin=0,mobileMenu=false,menuOpen=true,navPresent=true,originalClosed=false,nativeLifecycle=false}={}){
 const events={},windowEvents={},links=[],buttons=[],scrolls=[],menuActions=[],nativeReady=[];
 class Element{closest(){return null;}}
 class HTMLElement extends Element{
  constructor(id,title=''){super();this.id=id;this.textContent=title;this.dataset={};this.attrs={};this.top=0;this.isConnected=true;}
  matches(selector){return selector==='h2,h3'&&this.heading;}
  querySelector(){return this.label||null;}
  closest(selector){for(let node=this;node;node=node.parentElement){if(selector.includes('[hidden]')&&node.hidden)return node;if(selector.includes('details:not([open])')&&node instanceof HTMLDetailsElement&&!node.open)return node;}return null;}
  getClientRects(){return this.hidden||this.closest('[hidden],details:not([open])')||this===sourceLink&&menu.popoverPresent&&!menu.open?[]:[{}];}
  getBoundingClientRect(){return {top:this.top,bottom:this.top+20};}
  setAttribute(name,value){this.attrs[name]=value;}
  removeAttribute(name){delete this.attrs[name];}
  hasAttribute(name){return name in this.attrs;}
  focus(){if(this.getClientRects().length){this.focused=true;menuActions.push('focus:'+this.id);}}
  scrollIntoView(){this.scrolled=true;menuActions.push('scroll:'+this.id);}
  addEventListener(name,cb){(this.events||={})[name]=cb;}
 }
 class HTMLAnchorElement extends HTMLElement{
  constructor(){super('');this.href='';}
  closest(selector){return selector.startsWith('a[')?this:super.closest(selector);}
 }
 class HTMLDetailsElement extends HTMLElement{constructor(id){super(id);this.open=false;}}
 class MouseEvent{constructor(target,ctrlKey=false){this.target=target;this.button=0;this.ctrlKey=ctrlKey;}}
 const original=new HTMLElement('original'),extra=new HTMLElement('deep-timeline-originals');
 extra.label=new HTMLElement('', '이 임무에 연결된 추가 원문');extra.top=600;
 const parent=new HTMLDetailsElement('reference-scenes');parent.open=!originalClosed;original.parentElement=parent;
 const duplicate=new HTMLElement('original','중복 목차');duplicate.heading=true;
 const sourceLink=new HTMLAnchorElement();sourceLink.id='quest-nav-quest-1-timeline-abc';sourceLink.href='https://example.test/starrail-quests/대화/연출-timeline-0123456789abcdef.html';
 const owners=['quest-1','quest-2'].map(id=>{const d=new HTMLDetailsElement('');d.dataset.readingMission=id;return d;});
 const title=new HTMLElement('', '현재 원문');
 const fallback={remove(){this.removed=true;}};
 const toc={scrollTop:0,append(link){links.push(link);},getClientRects(){return this.hidden?[]:[{}];},getBoundingClientRect(){return {top:0,bottom:100};},querySelector(){return fallback;},querySelectorAll(){return links;},addEventListener(name,cb){events['toc:'+name]=cb;},closest(){return {hidden:false};}};
 const disclosure=new HTMLDetailsElement('');disclosure.dataset.readingGroup='quest-2:연출 원문';
 sourceLink.attrs['data-quest-reading-link']='';sourceLink.parentElement=disclosure;disclosure.parentElement=owners[1];
 const nav={querySelector:s=>s==='[data-current-reader-title]'?title:toc,querySelectorAll:s=>s==='[data-reading-mission]'?owners:s==='[data-reading-group]'?[disclosure]:source?[sourceLink]:[],addEventListener:(name,cb)=>events['nav:'+name]=cb};
 const menu={open:menuOpen,popoverPresent:nativeLifecycle||mobileMenu,scrollTop:0,hasAttribute(name){return name==='popover'&&this.popoverPresent;},matches:()=>menu.open,showPopover(){menuActions.push('show');menu.open=true;},hidePopover(){menu.open=false;}};
 if(nativeLifecycle)menu.localName='sl-sidebar-pane';
 const elements=new Map([[original.id,original],[extra.id,extra],[sourceLink.id,sourceLink],['starlight__sidebar',menu]]);
 const pageHeading=new HTMLElement('page-heading','현재 제목');
 const document={documentElement:{attrs:{},setAttribute(name,value){this.attrs[name]=value;},toggleAttribute(name){const enabled=!(name in this.attrs);if(enabled)this.attrs[name]='';else delete this.attrs[name];original.top+=enabled?-35:35;return enabled;}},body:{append:button=>buttons.push(button)},querySelector:s=>s==='[data-quest-reading-nav]'?(navPresent?nav:null):pageHeading,querySelectorAll:selector=>selector==='main .original-body'?[original]:[original,duplicate,extra],
  createElement:()=>new HTMLAnchorElement(),getElementById:id=>elements.get(id)||null,addEventListener:(name,cb)=>events[name]=cb};
 const storage=new Map(saved?[['quest-reading-nav.v1:quest-2',JSON.stringify(saved)]]:[]);
 const context={Element,HTMLElement,HTMLAnchorElement,HTMLDetailsElement,MouseEvent,document,innerHeight:800,sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},location:{origin:'https://example.test',pathname:'/starrail-quests/대화/연출-timeline-0123456789abcdef.html',search,hash:''},
  getComputedStyle:()=>({scrollPaddingTop:padding+'px',scrollMarginTop:margin+'px'}),window:{addEventListener:(name,cb)=>windowEvents[name]=cb,scrollBy:(x,y)=>{scrolls.push([x,y]);original.top-=y;extra.top-=y;}},requestAnimationFrame:cb=>cb(),URL,URLSearchParams,safeReadingReturn,sourceReadingOrigin};
 if(nativeLifecycle)context.customElements={whenDefined(name){assert.equal(name,'sl-sidebar-pane');return {then:callback=>nativeReady.push(callback)};}};
 context.location.hash=hash;
 vm.runInNewContext(script,context);
 return {events,windowEvents,links,original,extra,parent,owners,menu,title,fallback,sourceLink,MouseEvent,disclosure,storage,location:context.location,buttons,scrolls,document,toc,menuActions,nativeReady};
}
test('actual headings produce unique local anchors, including an unlabeled original body and additional sources',()=>{
 const r=reader();assert.deepEqual(r.links.map(a=>a.href),['#original','#deep-timeline-originals']);
 assert.deepEqual(r.links.map(a=>a.textContent),['원문 읽기','이 임무에 연결된 추가 원문']);
 assert.equal(r.title.textContent,'현재 제목');assert.equal(r.fallback.removed,true);
 assert.equal(r.links[0].attrs['aria-current'],'location');
});
test('mobile local navigation closes the actual popover and opens the body ancestor before focusing the original',()=>{
 const r=reader({originalClosed:true});r.events['toc:click'](new r.MouseEvent(r.links[0]));
 assert.equal(r.menu.open,false);assert.equal(r.parent.open,true);assert.equal(r.original.focused,true);
});
test('modified local navigation retains browser new-tab behavior without closing or moving focus',()=>{
 const r=reader();r.events['toc:click'](new r.MouseEvent(r.links[0],true));
 assert.equal(r.menu.open,true);assert.equal(r.original.focused,undefined);
});
test('hidden filtered targets cannot remain the active local heading',()=>{
 const r=reader();r.original.hidden=true;r.extra.top=20;r.events.scroll();
 assert.equal(r.links[0].attrs['aria-current'],undefined);assert.equal(r.links[1].attrs['aria-current'],'location');
});
test('shared ownership uses only a validated existing owner from navigation history',()=>{
 const r=reader({search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-2.html#original')});
 assert.deepEqual(r.owners.map(o=>o.open),[false,true]);
 const invalid=reader({search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-3.html#original')});
 assert.deepEqual(invalid.owners.map(o=>o.open),[false,false]);
});
test('sidebar source link retains the existing quest reading origin and filter rather than replacing it',()=>{
 const origin='/starrail-quests/문서/quest-2.html?speaker=운리#scene-2';
 const r=reader({search:'?from='+encodeURIComponent(origin)});
 assert.equal(decodeURI(new URL(r.sourceLink.href).searchParams.get('from')),origin);
});
test('same quest navigation restores keyed disclosure and scroll without changing ownership',()=>{
 const r=reader({search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-2.html#original'),saved:{open:{'quest-2:연출 원문':true,'quest-3:연출 원문':true},scroll:420}});
 assert.equal(r.disclosure.open,true);assert.equal(r.menu.scrollTop,420);assert.deepEqual(r.owners.map(o=>o.open),[false,true]);
 r.disclosure.open=false;r.menu.scrollTop=220;r.windowEvents.pagehide();
 const saved=JSON.parse(r.storage.get('quest-reading-nav.v1:quest-2'));
 assert.equal(saved.open['quest-2:연출 원문'],false);assert.equal(saved.scroll,220);assert.equal(saved.open['quest-3:연출 원문'],undefined);
});
test('explicit sidebar return anchor overrides a previously collapsed source group',()=>{
 const r=reader({search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-2.html#original'),saved:{open:{'quest-2:연출 원문':false},scroll:420},hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.disclosure.open,true);assert.equal(r.owners[1].open,true);assert.equal(r.sourceLink.focused,true);
});
test('current section includes actual fixed header padding and anchor margin after mobile navigation',()=>{
 const r=reader({padding:140.5,margin:119});r.original.top=-100;r.extra.top=259.6;r.events.scroll();
 assert.equal(r.links[0].attrs['aria-current'],undefined);assert.equal(r.links[1].attrs['aria-current'],'location');
});

test('changing a quest filter after load updates the sidebar return URL at navigation time',()=>{
 const r=reader();r.location.pathname='/starrail-quests/문서/quest-1.html';
 r.location.search='?speaker='+encodeURIComponent('운리')+'&passage=dialogue';
 r.events['nav:click'](new r.MouseEvent(r.sourceLink));
 const from=new URL(new URL(r.sourceLink.href).searchParams.get('from'),'https://example.test');
 assert.equal(decodeURI(from.pathname),'/starrail-quests/문서/quest-1.html');
 assert.equal(from.searchParams.get('speaker'),'운리');assert.equal(from.searchParams.get('passage'),'dialogue');
 assert.equal(from.hash,'#quest-nav-quest-1-timeline-abc');
});

test('focus mode retains the visible original offset and exposes an accessible restore control',()=>{
 const r=reader();r.original.top=200;const button=r.buttons[0];
 assert.equal(button.attrs['aria-controls'],'starlight__sidebar');
 button.events.click();assert.equal(button.attrs['aria-pressed'],'true');assert.equal(button.textContent,'탐색 펼치기');
 assert.deepEqual(r.scrolls[0],[0,-35]);assert.ok('data-reading-focus' in r.document.documentElement.attrs);
 button.events.click();assert.equal(button.attrs['aria-pressed'],'false');assert.equal(button.textContent,'집중 모드');
 assert.deepEqual(r.scrolls[1],[0,35]);assert.ok(!('data-reading-focus' in r.document.documentElement.attrs));
});

test('mobile source return opens native menu before scrolling and focusing the now visible link',()=>{
 const r=reader({mobileMenu:true,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc',search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-2.html#original'),saved:{open:{'quest-2:연출 원문':false},scroll:420}});
 assert.equal(r.menu.open,true);assert.equal(r.disclosure.open,true);assert.equal(r.owners[1].open,true);
 assert.equal(r.sourceLink.getClientRects().length,1);assert.equal(r.sourceLink.focused,true);
 assert.deepEqual(r.menuActions,['show','scroll:quest-nav-quest-1-timeline-abc','focus:quest-nav-quest-1-timeline-abc']);
});

test('desktop source return keeps the menu without popover and restores its visible link',()=>{
 const r=reader({mobileMenu:false,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.menu.open,false);assert.equal(r.sourceLink.focused,true);assert.equal(r.sourceLink.getClientRects().length,1);
 assert.ok(!r.menuActions.includes('show'));
});

test('return waits for native Starlight desktop adaptation instead of treating the SSR attribute as mobile',()=>{
 const r=reader({nativeLifecycle:true,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.sourceLink.focused,undefined);assert.equal(r.nativeReady.length,1);
 r.menu.popoverPresent=false;r.nativeReady[0]();
 assert.equal(r.sourceLink.focused,true);assert.ok(!r.menuActions.includes('show'));
});

test('duplicate TOC scope is enabled only after a context navigation exists',()=>{
 assert.ok('data-context-lnb' in reader().document.documentElement.attrs);
 const absent=reader({navPresent:false});assert.ok(!('data-context-lnb' in absent.document.documentElement.attrs));assert.equal(absent.buttons.length,0);
 const css=fs.readFileSync(new URL('../src/styles/reading-system.css',import.meta.url),'utf8');
 assert.match(css,/html\[data-context-lnb\]\s+:is\(\.right-sidebar-container,mobile-starlight-toc\)\{display:none\}/);
 assert.match(css,/inset-block-end:5\.25rem/);
});

test('active section follows inside local TOC once without replacing a subsequent manual menu scroll',()=>{
 const r=reader();r.links[1].top=250;r.original.top=-100;r.extra.top=20;r.events.scroll();
 assert.equal(r.toc.scrollTop,170);assert.equal(r.scrolls.length,0);
 r.toc.scrollTop=39;r.events.scroll();assert.equal(r.toc.scrollTop,39);
});

test('resize preserves the visible original paragraph offset recorded before layout changes',()=>{
 const r=reader();r.original.top=200;r.events.scroll();r.original.top=110;r.windowEvents.resize();
 assert.deepEqual(r.scrolls,[[0,-90]]);assert.equal(r.original.top,200);
 r.original.top=260;r.windowEvents.resize();assert.deepEqual(r.scrolls[1],[0,60]);assert.equal(r.original.top,200);
});

test('hidden closed or disconnected original paragraphs cannot drive a resize restoration',()=>{
 for(const change of [r=>r.original.hidden=true,r=>r.parent.open=false,r=>r.original.isConnected=false]){
  const r=reader();r.original.top=200;r.events.scroll();change(r);r.original.top=300;r.windowEvents.resize();assert.equal(r.scrolls.length,0);
 }
});
