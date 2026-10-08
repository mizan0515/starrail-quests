// Partition shared source files by their proved task scope, retaining every row.
export function missionRowLinked(section,row,coverage={}){
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
  if(selected.length)primary.push({...section,rows:selected,talkScope:coverage.sourceTalkScopes?.[section.source]});
  if(remaining.length)reference.push({...section,anchor: selected.length?section.anchor+'-reference':section.anchor,rows:remaining,talkScope:coverage.sourceTalkScopes?.[section.source]});
 }
 return {primary,reference};
}
