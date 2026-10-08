// Partition shared source files by their proved task scope, retaining every row.
export function missionRowLinked(section,row,coverage={}){
 if(section.recordType==='CUTSCENE_CAPTION'){
  const owner=section.ownership;
  return owner?.ownershipSeed?.kind==='EXPLICIT_RUNTIME_OWNERMAINMISSIONID'
   &&Array.isArray(coverage.missionIds)&&coverage.missionIds.some(id=>String(id)===String(owner.missionId))
   &&String(owner.ownershipSeed.missionId)===String(owner.missionId)
   &&Array.isArray(owner.chain)&&owner.chain.length>0;
 }
 const chain=section.relatedDocument?.ownership||coverage.sourceOwnership?.[section.source]||section.ownership;
 if(chain?.[0]?.kind!=='EXPLICIT_MAIN_MISSION_ID')return false;
 const scope=section.relatedDocument?undefined:coverage.sourceTalkScopes?.[section.source];
 if(!section.relatedDocument&&chain.some(edge=>edge.kind==='EXPLICIT_SUBMISSION_FINISH_SCOPE'&&edge.target===section.source)&&!scope)throw Error('Missing proved dialogue scope: '+section.source);
 if(scope&&!Array.isArray(scope.talkIds))throw Error('Invalid proved dialogue scope: '+section.source);
 return !scope||scope.talkIds.some(id=>String(id)===String(row.talk_id));
}
export function partitionMissionSections(sections,coverage={}){
 const primary=[],reference=[];
 for(const section of sections){
  if(!section.rows.length)continue;
  const selected=[],remaining=[];
  section.rows.forEach((row,index)=>{
   const located={...row,readerRowAnchor:row.readerRowAnchor||`${section.anchor}-row-${index+1}`};
   (missionRowLinked(section,row,coverage)?selected:remaining).push(located);
  });
  const talkScope=section.recordType==='CUTSCENE_CAPTION'?undefined:coverage.sourceTalkScopes?.[section.source];
  if(selected.length)primary.push({...section,rows:selected,talkScope});
  if(remaining.length)reference.push({...section,anchor: selected.length?section.anchor+'-reference':section.anchor,rows:remaining,talkScope});
 }
 return {primary,reference};
}
