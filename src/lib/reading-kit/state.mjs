// Restore the reader's disclosure and focus state when returning from a source.
import './relation-layout.mjs';
const key='reading-state.v1:'+location.pathname+location.search;
const disclosures=()=>[...document.querySelectorAll('main details')];
let followed='';
let followedIndex=-1;
const save=()=>{try{sessionStorage.setItem(key,JSON.stringify({open:disclosures().map(d=>d.open),scrollY,followed,followedIndex}));}catch{}};
const restore=()=>{
 try {
  const state=JSON.parse(sessionStorage.getItem(key)||'null');
  if(!state)return;
  disclosures().forEach((d,i)=>{if(typeof state.open[i]==='boolean')d.open=state.open[i];});
  requestAnimationFrame(()=>{
   const links=[...document.querySelectorAll('main a')];
   const clicked=links[state.followedIndex];
   const target=clicked?.href===state.followed?clicked:links.find(a=>a.href===state.followed&&a.getClientRects().length);
   target?.focus({preventScroll:true});
   window.scrollTo(0,state.scrollY);
  });
 } catch{}
};
document.addEventListener('click',event=>{
 const link=event.target instanceof Element?event.target.closest('main a'):null;
 if(link){followed=link.href;followedIndex=[...document.querySelectorAll('main a')].indexOf(link);save();const url=new URL(link.href);if(url.origin===location.origin&&url.pathname===location.pathname&&url.search===location.search)requestAnimationFrame(()=>revealRelation(url.hash));}
});
function revealRelation(hash=location.hash){try{const target=document.getElementById(decodeURIComponent(hash.slice(1)));if(target?.matches('details.rw-map-evidence,details.rw-relation-proof')){target.open=true;target.querySelector('summary')?.focus({preventScroll:true});}}catch{}}
window.addEventListener('hashchange',()=>revealRelation());
revealRelation();
window.addEventListener('pagehide',save);
window.addEventListener('pageshow',event=>{
 if(event.persisted||performance.getEntriesByType('navigation')[0]?.type==='back_forward')restore();
 else requestAnimationFrame(()=>revealRelation());
});
