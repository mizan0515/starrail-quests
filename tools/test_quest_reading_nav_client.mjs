import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {stripTypeScriptTypes} from 'node:module';
import test from 'node:test';
import {safeReadingReturn,sourceReadingOrigin} from '../src/lib/reading-return.mjs';
const astro=fs.readFileSync(new URL('../src/components/QuestReadingNav.astro',import.meta.url),'utf8');
const script=stripTypeScriptTypes(astro.split('<script>')[1].split('</script>')[0].replace(/^\s*import .*;$/gm,'').replace('import.meta.env.BASE_URL',"'/starrail-quests/'"));

function reader({search='',source=true,saved=null,pointSaved=null,originalTop=0,pageScroll=0,sourceLinkTop=0,hash='',padding=0,margin=0,mobileMenu=false,menuOpen=true,navPresent=true,originalClosed=false,nativeLifecycle=false}={}){
 const events={},windowEvents={},links=[],buttons=[],scrolls=[],menuActions=[],nativeReady=[];
 class Element{closest(){return null;}}
 class HTMLElement extends Element{
  constructor(id,title=''){super();this.id=id;this.textContent=title;this.dataset={};this.attrs={};this.top=0;this.isConnected=true;}
  matches(selector){return selector==='h2,h3'&&this.heading||selector==='.original-body'&&this.originalBody;}
  querySelector(){return this.label||null;}
  closest(selector){for(let node=this;node;node=node.parentElement){if(selector==='.reader-guide-body'&&node===guideBody)return node;if(selector==='details.reader-guide'&&node===guide)return node;if(selector.includes('[hidden]')&&node.hidden)return node;if(selector.includes('details:not([open])')&&node instanceof HTMLDetailsElement&&!node.open)return node;}return null;}
  getClientRects(){return this.hidden||this.closest('[hidden],details:not([open])')?[]:[{}];}
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
 const guide=new HTMLDetailsElement('reader-guide');guide.open=menuOpen;
 const guideBody=new HTMLElement('guide-body');guideBody.scrollTop=0;guideBody.parentElement=guide;guideBody.getBoundingClientRect=()=>({top:0,bottom:100});
 const original=new HTMLElement('original'),extra=new HTMLElement('deep-timeline-originals');
 original.originalBody=true;original.top=originalTop;
 extra.label=new HTMLElement('', '이 임무에 연결된 추가 원문');extra.top=600;
 const parent=new HTMLDetailsElement('reference-scenes');parent.open=!originalClosed;original.parentElement=parent;
 const duplicate=new HTMLElement('original','중복 목차');duplicate.heading=true;
 const sourceLink=new HTMLAnchorElement();sourceLink.id='quest-nav-quest-1-timeline-abc';sourceLink.href='https://example.test/starrail-quests/대화/연출-timeline-0123456789abcdef.html';
 sourceLink.top=sourceLinkTop;
 const owners=['quest-1','quest-2'].map(id=>{const d=new HTMLDetailsElement('');d.dataset.readingMission=id;return d;});
 const title=new HTMLElement('', '현재 원문');
 const fallback={remove(){this.removed=true;}};
 const toc={scrollTop:0,append(link){links.push(link);},getClientRects(){return this.hidden?[]:[{}];},getBoundingClientRect(){return {top:0,bottom:100};},querySelector(){return fallback;},querySelectorAll(){return links;},addEventListener(name,cb){events['toc:'+name]=cb;},closest(){return {hidden:false};}};
 const disclosure=new HTMLDetailsElement('');disclosure.dataset.readingGroup='quest-2:연출 원문';
 sourceLink.attrs['data-quest-reading-link']='';sourceLink.parentElement=disclosure;disclosure.parentElement=owners[1];owners[1].parentElement=guideBody;
 const nav={closest:selector=>selector==='.reader-guide-body'?guideBody:selector==='details.reader-guide'?guide:null,querySelector:s=>s==='[data-current-reader-title]'?title:toc,querySelectorAll:s=>s==='[data-reading-mission]'?owners:s==='[data-reading-group]'?[disclosure]:source?[sourceLink]:[],addEventListener:(name,cb)=>events['nav:'+name]=cb};
 const menu={open:menuOpen,popoverPresent:nativeLifecycle||mobileMenu,scrollTop:0,hasAttribute(name){return name==='popover'&&this.popoverPresent;},matches:()=>menu.open,showPopover(){menuActions.push('show');menu.open=true;},hidePopover(){menu.open=false;}};
 if(nativeLifecycle)menu.localName='sl-sidebar-pane';
 const elements=new Map([[original.id,original],[extra.id,extra],[sourceLink.id,sourceLink],['starlight__sidebar',menu],['reader-guide',guide]]);
 const pageHeading=new HTMLElement('page-heading','현재 제목');
 const document={documentElement:{attrs:{},setAttribute(name,value){this.attrs[name]=value;},removeAttribute(name){delete this.attrs[name];},hasAttribute(name){return name in this.attrs;},toggleAttribute(name){const enabled=!(name in this.attrs);if(enabled)this.attrs[name]='';else delete this.attrs[name];original.top+=enabled?-35:35;return enabled;}},body:{append:button=>buttons.push(button)},querySelector:s=>s==='[data-quest-reading-nav]'?(navPresent?nav:null):pageHeading,querySelectorAll:selector=>selector.includes('main .original-body')?[original]:[original,duplicate,extra],
  createElement:()=>new HTMLAnchorElement(),getElementById:id=>elements.get(id)||null,addEventListener:(name,cb)=>events[name]=cb};
 const storage=new Map(saved?[['quest-reading-nav.v1:quest-2',JSON.stringify(saved)]]:[]);
 if(pointSaved)storage.set('quest-reading-nav-point.v1:/starrail-quests/대화/연출-timeline-0123456789abcdef.html'+search,JSON.stringify(pointSaved));
 const context={Element,HTMLElement,HTMLAnchorElement,HTMLDetailsElement,MouseEvent,document,innerHeight:800,scrollY:pageScroll,sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},location:{origin:'https://example.test',pathname:'/starrail-quests/대화/연출-timeline-0123456789abcdef.html',search,hash:''},
  getComputedStyle:()=>({scrollPaddingTop:padding+'px',scrollMarginTop:margin+'px'}),window:{addEventListener:(name,cb)=>windowEvents[name]=cb,scrollBy:(x,y)=>{scrolls.push([x,y]);context.scrollY+=y;original.top-=y;extra.top-=y;},scrollTo:(x,y)=>{const delta=y-context.scrollY;context.scrollY=y;scrolls.push([x,delta]);original.top-=delta;extra.top-=delta;}},matchMedia:()=>({matches:!mobileMenu}),requestAnimationFrame:cb=>cb(),URL,URLSearchParams,safeReadingReturn,sourceReadingOrigin};
 if(nativeLifecycle)context.customElements={whenDefined(name){assert.equal(name,'sl-sidebar-pane');return {then:callback=>nativeReady.push(callback)};}};
 context.location.hash=hash;
 vm.runInNewContext(script,context);
 const sidebar=fs.readFileSync(new URL('../src/components/PageSidebar.astro',import.meta.url),'utf8');
 const focusScript=stripTypeScriptTypes(sidebar.slice(sidebar.indexOf(" const focus=document.createElement('button');"),sidebar.indexOf('</script>')));
 if(navPresent){context.guide=guide;vm.runInNewContext(focusScript,context);}
 return {events,windowEvents,guide,guideBody,links,original,extra,parent,owners,menu,title,fallback,sourceLink,MouseEvent,disclosure,storage,location:context.location,buttons,scrolls,document,toc,menuActions,nativeReady,context};
}
test('actual headings produce unique local anchors, including an unlabeled original body and additional sources',()=>{
 const r=reader();assert.deepEqual(r.links.map(a=>a.href),['#original','#deep-timeline-originals']);
 assert.deepEqual(r.links.map(a=>a.textContent),['원문 읽기','이 임무에 연결된 추가 원문']);
 assert.equal(r.title.textContent,'현재 제목');assert.equal(r.fallback.removed,true);
 assert.equal(r.links[0].attrs['aria-current'],'location');
});
test('mobile local navigation closes the independent guide and opens the body ancestor before focusing the original',()=>{
 const r=reader({originalClosed:true,mobileMenu:true});r.events['toc:click'](new r.MouseEvent(r.links[0]));
 assert.equal(r.guide.open,false);assert.equal(r.menu.open,true);assert.equal(r.parent.open,true);assert.equal(r.original.focused,true);
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
 assert.equal(r.disclosure.open,true);assert.equal(r.guideBody.scrollTop,420);assert.deepEqual(r.owners.map(o=>o.open),[false,true]);
 r.disclosure.open=false;r.guideBody.scrollTop=220;r.windowEvents.pagehide();
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
 assert.equal(button.attrs['aria-controls'],'reader-guide starlight__sidebar');
 button.events.click();assert.equal(button.attrs['aria-pressed'],'true');assert.equal(button.textContent,'탐색 펼치기');
 assert.deepEqual(r.scrolls[0],[0,-35]);assert.ok('data-reading-focus' in r.document.documentElement.attrs);
 button.events.click();assert.equal(button.attrs['aria-pressed'],'false');assert.equal(button.textContent,'집중 모드');
 assert.deepEqual(r.scrolls[1],[0,35]);assert.ok(!('data-reading-focus' in r.document.documentElement.attrs));
});

test('mobile source return opens the guide and focuses the visible link without opening the global menu',()=>{
 const r=reader({mobileMenu:true,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc',search:'?from='+encodeURIComponent('/starrail-quests/문서/quest-2.html#original'),saved:{open:{'quest-2:연출 원문':false},scroll:420}});
 assert.equal(r.guide.open,true);assert.equal(r.menu.open,false);assert.equal(r.disclosure.open,true);assert.equal(r.owners[1].open,true);
 assert.equal(r.sourceLink.getClientRects().length,1);assert.equal(r.sourceLink.focused,true);
 assert.deepEqual(r.menuActions,['focus:quest-nav-quest-1-timeline-abc']);
});

test('desktop source return keeps the menu without popover and restores its visible link',()=>{
 const r=reader({mobileMenu:false,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.menu.open,false);assert.equal(r.sourceLink.focused,true);assert.equal(r.sourceLink.getClientRects().length,1);
 assert.ok(!r.menuActions.includes('show'));
});

test('source navigation captures the visible paragraph and restores its offset after a fragment jump',()=>{
 const before=reader({originalTop:345.9375,pageScroll:752});
 before.events['nav:click'](new before.MouseEvent(before.sourceLink));
 const key='quest-reading-nav-point.v1:'+before.location.pathname+before.location.search;
 const saved=JSON.parse(before.storage.get(key));
 assert.deepEqual(saved,{link:before.sourceLink.id,id:'original',top:345.9375,scroll:752});
 const after=reader({pointSaved:saved,originalTop:-704.0625,pageScroll:1802,hash:'#'+before.sourceLink.id});
 assert.equal(after.original.top,345.9375);assert.equal(after.context.scrollY,752);
 assert.equal(after.storage.has(key),false);assert.equal(after.sourceLink.scrolled,undefined);
 assert.equal(after.sourceLink.focused,true);
});

test('revealing a return link scrolls only its guide without recentering the body',()=>{
 const restored=reader({hash:'#quest-nav-quest-1-timeline-abc',sourceLinkTop:160,originalTop:200,pageScroll:600});
 assert.equal(restored.sourceLink.scrolled,undefined);assert.equal(restored.context.scrollY,600);
 assert.equal(restored.guideBody.scrollTop,80);assert.equal(restored.original.top,200);assert.deepEqual(restored.scrolls,[]);
});

test('a saved body point is ignored for a different return link',()=>{
 const r=reader({pointSaved:{link:'other-link',id:'original',top:345,scroll:752},originalTop:90,pageScroll:1200,hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.original.top,90);assert.equal(r.context.scrollY,1200);assert.deepEqual(r.scrolls,[]);
});

test('source return has no dependency on native Starlight constructor or global popover state',()=>{
 const r=reader({nativeLifecycle:true,menuOpen:false,hash:'#quest-nav-quest-1-timeline-abc'});
 assert.equal(r.nativeReady.length,0);assert.equal(r.guide.open,true);assert.equal(r.menu.open,false);
 assert.equal(r.sourceLink.focused,true);assert.ok(!r.menuActions.includes('show'));
});
test('one independent guide replaces duplicate native TOC suppression and has a no-JS flow fallback',()=>{
 const r=reader();assert.ok(!('data-context-lnb' in r.document.documentElement.attrs));
 const absent=reader({navPresent:false});assert.equal(absent.links.length,0);assert.equal(absent.buttons.length,0);
 const sidebar=fs.readFileSync(new URL('../src/components/Sidebar.astro',import.meta.url),'utf8');assert.ok(!sidebar.includes('QuestReadingNav'));
 const page=fs.readFileSync(new URL('../src/components/PageSidebar.astro',import.meta.url),'utf8');assert.match(page,/<QuestReadingNav route=\{route\}/);
 const css=fs.readFileSync(new URL('../src/styles/reader-shell.css',import.meta.url),'utf8');
 assert.match(css,/\.reader-guide-body\{position:static/);assert.match(css,/\[data-guide-ready\] \.reader-guide-body\{position:absolute/);
});

test('active section follows inside local TOC once without replacing a subsequent manual menu scroll',()=>{
 const r=reader();r.links[1].top=250;r.original.top=-100;r.extra.top=20;r.events.scroll();
 assert.equal(r.guideBody.scrollTop,170);assert.equal(r.scrolls.length,0);
 r.guideBody.scrollTop=39;r.events.scroll();assert.equal(r.guideBody.scrollTop,39);
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

test('reopening the guide reveals the current heading even when its active ID is unchanged',()=>{
 const r=reader();r.links[1].top=250;r.original.top=-100;r.extra.top=20;r.events.scroll();r.guideBody.scrollTop=0;
 r.guide.open=true;r.guide.events.toggle();assert.equal(r.guideBody.scrollTop,170);assert.equal(r.scrolls.length,0);
});
test('malformed source-return hash does not throw or focus another group',()=>{
 for(const hash of ['#%','#E0%A4','#%E0%A4']){const r=reader({hash,menuOpen:false});assert.equal(r.sourceLink.focused,undefined);assert.equal(r.guide.open,false);}
});
test('actual resize controller moves focus before a narrow guide closes or a wide summary hides',()=>{
 const sidebar=fs.readFileSync(new URL('../src/components/PageSidebar.astro',import.meta.url),'utf8');
 const code=sidebar.slice(sidebar.indexOf('  const apply=()=>{'),sidebar.indexOf("  apply();guide.closest")).replaceAll('<HTMLElement>','');
 const calls=[],summary={focus:options=>calls.push(['summary',options.preventScroll])},link={focus:options=>calls.push(['link',options.preventScroll])};
 const guide={open:true,contains:element=>element===link||element===summary,querySelector:()=>link};
 const context={guide,summary,wide:{matches:false},document:{activeElement:link}};
 vm.runInNewContext(code+'apply();',context);assert.equal(guide.open,false);assert.deepEqual(calls,[['summary',true]]);
 context.wide.matches=true;context.document.activeElement=summary;calls.length=0;vm.runInNewContext('apply();',context);
 assert.equal(guide.open,true);assert.deepEqual(calls,[['link',true]]);
});
