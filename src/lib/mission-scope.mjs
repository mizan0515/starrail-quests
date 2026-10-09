// Partition shared source files by their proved task scope, retaining every row.
export function missionRowLinked(section,row,coverage={}){
 if(section.recordType==='CUTSCENE_CAPTION'){
  const owner=section.ownership;
  const seed=owner?.ownershipSeed;
  const explicitRuntime=seed?.kind==='EXPLICIT_RUNTIME_OWNERMAINMISSIONID';
  const first=owner?.chain?.[0];
  const explicitMission=seed?.kind==='EXPLICIT_MAIN_MISSION_ID'
   &&typeof seed.missionJsonPath==='string'&&!!seed.missionJsonPath
   &&typeof seed.missionJsonPathPointer==='string'&&!!seed.missionJsonPathPointer
   &&first?.kind==='EXPLICIT_JSON_PATH'&&first.source===seed.source
   &&first.pointer===seed.missionJsonPathPointer&&first.target===seed.missionJsonPath;
  return (explicitRuntime||explicitMission)
   &&Array.isArray(coverage.missionIds)&&coverage.missionIds.some(id=>String(id)===String(owner.missionId))
   &&String(seed.missionId)===String(owner.missionId)
   &&Array.isArray(owner.chain)&&owner.chain.length>0;
 }
 const chain=section.relatedDocument?.ownership||coverage.sourceOwnership?.[section.source]||section.ownership;
 if(chain?.[0]?.kind==='EXPLICIT_NATIVE_MAIN_MISSION_ID'){
  const seed=chain[0];
  return ['TIMELINE_DIALOGUE','NATIVE_TIMELINE_CHOICES'].includes(section.recordType)
   &&seed.value===seed.missionId&&seed.missionId===seed.canonicalMissionId
   &&seed.pointer==='/OwnerMainMissionID'&&section.nativeOwnership?.edges?.length===5
   &&Array.isArray(coverage.missionIds)&&coverage.missionIds.some(id=>String(id)===String(seed.missionId));
 }
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
