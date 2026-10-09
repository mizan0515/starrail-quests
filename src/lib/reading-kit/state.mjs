// Restore the reader's disclosure and focus state when returning from a source.
import './relation-layout.mjs';
const key='reading-state.v1:'+location.pathname+location.search;
const disclosures=()=>[...document.querySelectorAll('main details')];
let followed='';
const save=()=>{try{sessionStorage.setItem(key,JSON.stringify({open:disclosures().map(d=>d.open),scrollY,followed}));}catch{}};
const restore=()=>{
 try {
  const state=JSON.parse(sessionStorage.getItem(key)||'null');
  if(!state)return;
  disclosures().forEach((d,i)=>{if(typeof state.open[i]==='boolean')d.open=state.open[i];});
  requestAnimationFrame(()=>{
   const target=[...document.querySelectorAll('main a')].find(a=>a.href===state.followed);
   target?.focus({preventScroll:true});
   window.scrollTo(0,state.scrollY);
  });
 } catch{}
};
document.addEventListener('click',event=>{
 const link=event.target instanceof Element?event.target.closest('main a'):null;
 if(link){followed=link.href;save();const url=new URL(link.href);if(url.origin===location.origin&&url.pathname===location.pathname&&url.search===location.search)requestAnimationFrame(()=>revealRelation(url.hash));}
});
function revealRelation(hash=location.hash){try{const target=document.getElementById(decodeURIComponent(hash.slice(1)));if(target?.matches('details.rw-map-evidence,details.rw-relation-proof')){target.open=true;target.querySelector('summary')?.focus({preventScroll:true});}}catch{}}
window.addEventListener('hashchange',()=>revealRelation());
revealRelation();
window.addEventListener('pagehide',save);
window.addEventListener('pageshow',event=>{
 if(event.persisted||performance.getEntriesByType('navigation')[0]?.type==='back_forward')restore();
 else requestAnimationFrame(()=>revealRelation());
});
