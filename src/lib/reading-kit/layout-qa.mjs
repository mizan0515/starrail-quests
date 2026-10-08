/** Validate measured browser geometry; unit fixtures are not browser evidence.
 * sample: {document:{scrollWidth,clientWidth},elements:[{id,role,
 * rect:{left,top,right,bottom,width,height},parentRect:same,
 * computed:{marginInlineStart,listStyleType,listStylePosition,
 * beforeContent,beforeDisplay,afterContent,afterDisplay,minWidth}}]}.
 * role: summary | control | body | row. Parent is the containing reader/row/
 * controls content box, never the viewport for a nested element.
 * Optional expectedMarginTop is a caller-owned template invariant (e.g. 0
 * for a grid child); computed.marginTop must then be measured in CSS pixels.
 */
export function validateLayout(sample) {
 const errors=[],fail=(error,id)=>errors.push({error,...(id?{id}:{})});
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const box=r=>r&&['left','top','right','bottom','width','height'].every(k=>finite(r[k]))&&r.width>0&&r.height>0;
 const doc=sample?.document;
 if(!doc||!finite(doc.scrollWidth)||!finite(doc.clientWidth)||doc.clientWidth<=0) fail('document measurement missing');
 else if(doc.scrollWidth>doc.clientWidth+1)fail('document horizontal overflow');
 if(!Array.isArray(sample?.elements)||!sample.elements.length)fail('reader element measurements missing');
 for(const e of Array.isArray(sample?.elements)?sample.elements:[]) {
  if(!e){fail('element geometry missing');continue;}
  if(!['summary','control','body','row'].includes(e.role)){fail('unknown measured reader role',e.id);continue;}
  if(!box(e.rect)||!box(e.parentRect)){fail('element geometry missing',e.id);continue;}
  const r=e.rect,p=e.parentRect,c=e.computed||{};
  if(r.left<p.left-1||r.right>p.right+1||r.top<p.top-1||r.bottom>p.bottom+1)fail('reader element exceeds containing box',e.id);
  if((e.role==='summary'||e.role==='control')&&r.height<44)fail('interactive target height below 44px',e.id);
  if(e.role==='control'&&r.width<44)fail('interactive target width below 44px',e.id);
  if(e.role==='summary') {
   if(!['disclosure-closed','disclosure-open'].includes(c.listStyleType)||c.listStylePosition!=='inside')fail('native disclosure marker missing or outside',e.id);
   if(!finite(c.marginInlineStart))fail('summary inline margin measurement missing',e.id);
   else if(c.marginInlineStart<0)fail('framework negative summary margin',e.id);
   for(const prefix of ['before','after']) {
    const content=c[prefix+'Content'],display=c[prefix+'Display'];
    if(typeof content!=='string'||typeof display!=='string')fail('disclosure pseudo marker measurement missing',e.id);
    else if(display!=='none'&&!['none','normal'].includes(content))fail('duplicate disclosure pseudo arrow',e.id);
   }
  }
  if(finite(e.expectedMarginTop)&&(!finite(c.marginTop)||Math.abs(c.marginTop-e.expectedMarginTop)>0.5))fail('framework block margin differs from template',e.id);
  if(e.role==='control'&&finite(c.minWidth)&&c.minWidth>r.width+1)fail('control minimum width exceeds available box',e.id);
 }
 return {status:errors.length?'FAIL':'PASS',errors};
}

/** Validate visible responsive card collection geometry measured in the browser.
 * sample: {document:{scrollWidth,clientWidth},collections:[{id,
 * containerRect, moduleRect, cardsRect, cardMinWidth, columnGap,
 * direction:'ltr'|'rtl', cards:[{id,rect,parentRect,
 * computed:{marginTop,marginBottom}}]}]}.
 * Rects use CSS pixels and all six fields of validateLayout's rect schema.
 * containerRect is the host content box; moduleRect is its CVA module's
 * border box; cardsRect is the cards' shared parent content box. Each card's
 * parentRect must be measured from that actual parent, not the viewport.
 * cards must be in DOM order. Only visible, nonempty collections are sampled;
 * zero-size or missing measurements cannot establish success.
 * cardMinWidth is an independent template requirement in CSS pixels, not
 * the current card width or grid-template-columns. columnGap is measured.
 * A single card fills the cards box. Multiple cards use at least two columns
 * when two minimum widths plus the gap fit, otherwise one full-width column.
 * Block margins on these sibling cards must be zero. direction defaults to
 * ltr and describes the intended visual reading direction.
 * Unit fixtures exercise this validator; they are not browser evidence.
 */
export function validateCollectionLayout(sample) {
 const errors=[],measurements=[],fail=(error,id)=>errors.push({error,...(id?{id}:{})});
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 const tolerance=1;
 const box=r=>r&&['left','top','right','bottom','width','height'].every(k=>finite(r[k]))&&r.width>0&&r.height>0&&Math.abs(r.right-r.left-r.width)<=tolerance&&Math.abs(r.bottom-r.top-r.height)<=tolerance;
 const contained=(r,p)=>r.left>=p.left-tolerance&&r.right<=p.right+tolerance&&r.top>=p.top-tolerance&&r.bottom<=p.bottom+tolerance;
 const sameBox=(r,p)=>['left','top','right','bottom','width','height'].every(k=>Math.abs(r[k]-p[k])<=tolerance);
 const fillsWidth=(r,p)=>Math.abs(r.left-p.left)<=tolerance&&Math.abs(r.right-p.right)<=tolerance&&Math.abs(r.width-p.width)<=tolerance;
 const doc=sample?.document;
 if(!doc||!finite(doc.scrollWidth)||!finite(doc.clientWidth)||doc.scrollWidth<=0||doc.clientWidth<=0)fail('document measurement missing or inactive');
 else if(doc.scrollWidth>doc.clientWidth+tolerance)fail('document horizontal overflow');
 if(!Array.isArray(sample?.collections)||!sample.collections.length)fail('collection measurements missing');
 for(const collection of Array.isArray(sample?.collections)?sample.collections:[]) {
  const id=collection?.id,c=collection||{},direction=c.direction??'ltr';
  if(!['ltr','rtl'].includes(direction))fail('collection reading direction invalid',id);
  if(!box(c.containerRect)||!box(c.moduleRect)||!box(c.cardsRect)){fail('collection geometry missing or inactive',id);continue;}
  if(!fillsWidth(c.moduleRect,c.containerRect))fail('collection module does not fill available width',id);
  if(!contained(c.moduleRect,c.containerRect))fail('collection module exceeds containing box',id);
  if(!contained(c.cardsRect,c.moduleRect))fail('collection cards box exceeds module',id);
  if(!finite(c.cardMinWidth)||c.cardMinWidth<=0||!finite(c.columnGap)||c.columnGap<0){fail('collection width requirement or gap missing',id);continue;}
  if(!Array.isArray(c.cards)||!c.cards.length){fail('collection card measurements missing',id);continue;}
  const cards=[],ids=new Set();
  for(const [index,card] of c.cards.entries()) {
   const cardId=card?.id||id;
   if(typeof card?.id!=='string'||!card.id||ids.has(card.id))fail('collection card identity missing or duplicated',cardId);
   ids.add(card?.id);
   if(!box(card?.rect)||!box(card?.parentRect)){fail('collection card geometry missing or inactive',cardId);continue;}
   if(!sameBox(card.parentRect,c.cardsRect))fail('collection card parent differs from measured cards box',cardId);
   if(!contained(card.rect,card.parentRect))fail('collection card exceeds containing box',cardId);
   const computed=card.computed||{};
   if(!finite(computed.marginTop)||!finite(computed.marginBottom))fail('collection sibling margin measurement missing',cardId);
   else if(Math.abs(computed.marginTop)>0.5||Math.abs(computed.marginBottom)>0.5)fail('collection sibling block margin is not zero',cardId);
   if(card.rect.width<Math.min(c.cardMinWidth,c.cardsRect.width)-tolerance)fail('collection card below minimum available width',cardId);
   cards.push({index,id:cardId,rect:card.rect});
  }
  if(cards.length!==c.cards.length)continue;
  const rows=[];
  for(const card of [...cards].sort((a,b)=>a.rect.top-b.rect.top||a.index-b.index)) {
   const last=rows.at(-1);
   if(last&&Math.abs(card.rect.top-last.top)<=tolerance)last.cards.push(card);
   else rows.push({top:card.rect.top,cards:[card]});
  }
  const visual=rows.flatMap(row=>row.cards.sort((a,b)=>direction==='rtl'?b.rect.right-a.rect.right:a.rect.left-b.rect.left));
  if(visual.some((card,index)=>card.index!==index))fail('collection visual order differs from DOM order',id);
  for(let a=0;a<cards.length;a++)for(let b=a+1;b<cards.length;b++) {
   const r=cards[a].rect,p=cards[b].rect;
   if(Math.min(r.right,p.right)-Math.max(r.left,p.left)>tolerance&&Math.min(r.bottom,p.bottom)-Math.max(r.top,p.top)>tolerance)fail('collection cards overlap',cards[b].id);
  }
  const columns=Math.max(...rows.map(row=>row.cards.length));
  const wide=cards.length>1&&c.cardsRect.width>=2*c.cardMinWidth+c.columnGap-tolerance;
  const expected=cards.length===1?'full-width':wide?'multi-column':'single-column';
  if(wide&&columns<2)fail('collection loses multiple columns at available width',id);
  if(!wide&&columns!==1)fail('collection must use one column at narrow width',id);
  if(!wide)for(const card of cards)if(!fillsWidth(card.rect,c.cardsRect))fail('collection single-column card does not fill available width',card.id);
  measurements.push({id,cardCount:cards.length,availableWidth:c.cardsRect.width,columns,expected});
 }
 return {status:errors.length?'FAIL':'PASS',errors,measurements};
}
