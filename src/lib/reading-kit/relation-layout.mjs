// Draw only the declared edges between visible, measured source relation cards.
export function relationConnector({focus,card,direction,layout='orbit'}) {
 const valid=r=>r&&['left','top','right','bottom','width','height'].every(k=>Number.isFinite(r[k]))&&r.width>0&&r.height>0;
 if(!valid(focus)||!valid(card)||!['incoming','outgoing'].includes(direction)||!['orbit','fan','pair'].includes(layout))return null;
 let a,b;
 if(layout==='fan'){
  if(card.top<focus.bottom)return null;
  a={x:focus.left+focus.width/2,y:focus.bottom+2};b={x:card.left+card.width/2,y:card.top-2};
 }else if(card.right<=focus.left){
  a={x:card.right+2,y:card.top+card.height/2};b={x:focus.left-2,y:focus.top+focus.height/2};
 }else if(card.left>=focus.right){
  a={x:focus.right+2,y:focus.top+focus.height/2};b={x:card.left-2,y:card.top+card.height/2};
 }else return null;
 // The initial points follow geometric reading order; the IDs choose direction.
 const focusFirst=layout==='fan'||card.left>=focus.right;
 if((direction==='outgoing')!==focusFirst)[a,b]=[b,a];
 const n=value=>Math.round(value*100)/100;
 const middle=layout==='fan'?(a.y+b.y)/2:(a.x+b.x)/2;
 return layout==='fan'?`M ${n(a.x)} ${n(a.y)} C ${n(a.x)} ${n(middle)} ${n(b.x)} ${n(middle)} ${n(b.x)} ${n(b.y)}`:`M ${n(a.x)} ${n(a.y)} C ${n(middle)} ${n(a.y)} ${n(middle)} ${n(b.y)} ${n(b.x)} ${n(b.y)}`;
}

export function mountRelationLayout(root=document) {
 const ns='http://www.w3.org/2000/svg';
 for(const wrapper of root.querySelectorAll('.rw-focus-relations[data-focus-id]')){
  if(wrapper.hasAttribute('data-rw-connector-mounted'))continue;
  wrapper.dataset.rwConnectorMounted='';
  const orbit=wrapper.querySelector('.sc-orbit'),focus=wrapper.querySelector('.sc-orbit-placeholder,.cva-flow-list>.cva-node:first-child');
  if(!focus)continue;
  const svg=document.createElementNS(ns,'svg');svg.setAttribute('class','rw-directed-connectors');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');svg.setAttribute('data-pagefind-ignore','');
  const markerId='rw-arrow-'+wrapper.querySelector('.cva-module').id;
  const defs=document.createElementNS(ns,'defs'),marker=document.createElementNS(ns,'marker'),tip=document.createElementNS(ns,'path');
  marker.setAttribute('id',markerId);marker.setAttribute('viewBox','0 0 10 10');marker.setAttribute('refX','9');marker.setAttribute('refY','5');marker.setAttribute('markerWidth','6');marker.setAttribute('markerHeight','6');marker.setAttribute('orient','auto');tip.setAttribute('d','M 1 1 L 9 5 L 1 9');marker.append(tip);defs.append(marker);svg.append(defs);wrapper.prepend(svg);
  let pending=false;
  const draw=()=>{
   pending=false;svg.querySelectorAll(':scope > path').forEach(p=>p.remove());
   const box=wrapper.getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${box.width} ${box.height}`);
   if(box.width<1||getComputedStyle(svg).display==='none'||(orbit&&getComputedStyle(orbit).display==='flex'))return;
   const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left-box.left,top:r.top-box.top,right:r.right-box.left,bottom:r.bottom-box.top,width:r.width,height:r.height};};
   for(const band of wrapper.querySelectorAll('.rw-relation-band[data-relation-from][data-relation-to]')){
    const from=band.dataset.relationFrom,to=band.dataset.relationTo,id=wrapper.dataset.focusId;
    if((from===id)===(to===id))continue;
    const card=band.closest('.sc-card,.cva-node');if(!card)continue;
    const d=relationConnector({focus:rect(focus),card:rect(card),direction:from===id?'outgoing':'incoming',layout:orbit||wrapper.dataset.hubShape==='branch'?'orbit':wrapper.dataset.hubShape==='pair'?'pair':'fan'});
    if(!d)continue;
    const path=document.createElementNS(ns,'path');path.setAttribute('d',d);path.setAttribute('marker-end',`url(#${markerId})`);path.dataset.relationFrom=from;path.dataset.relationTo=to;svg.append(path);
   }
  };
  const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(draw);}};
  const observer=new ResizeObserver(schedule);
  for(const element of [wrapper,focus,...wrapper.querySelectorAll('.sc-card,.cva-node')])observer.observe(element);
  wrapper.addEventListener('toggle',schedule,true);window.addEventListener('resize',schedule);window.addEventListener('pageshow',schedule);document.fonts?.ready.then(schedule);schedule();
 }
}
if(typeof document!=='undefined')mountRelationLayout();
