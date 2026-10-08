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
 const box=r=>r&&['left','top','right','bottom','width','height'].every(k=>finite(r[k]))&&r.width>=0&&r.height>=0;
 const doc=sample?.document;
 if(!doc||!finite(doc.scrollWidth)||!finite(doc.clientWidth)||doc.clientWidth<=0) fail('document measurement missing');
 else if(doc.scrollWidth>doc.clientWidth+1)fail('document horizontal overflow');
 if(!Array.isArray(sample?.elements)||!sample.elements.length)fail('reader element measurements missing');
 for(const e of sample?.elements||[]) {
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
