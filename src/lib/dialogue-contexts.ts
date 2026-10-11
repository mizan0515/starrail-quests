import fs from 'node:fs';
import path from 'node:path';
import contexts from '../../data/dialogue-contexts.json';
import official from '../../data/official-talk-library.json';
const rows=new Map<number,any>();
for(const file of fs.readdirSync('data/dialogues').filter(file=>file.endsWith('.json'))){
 const document=JSON.parse(fs.readFileSync(path.resolve('data/dialogues',file),'utf8'));
 for(const row of document.section.rows)rows.set(row.talk_id,{...row,url:'대사/'+document.id+'.html#talk-'+row.talk_id});
}
const current=new Map(official.rows.map(row=>[row.talk_id,{...row,url:'대사/official-4.6-'+row.talk_id+'.html#talk-'+row.talk_id}]));
export {contexts};
export const contextRows=(group:any)=>group.rows.map(ref=>{
 const row=ref.edition==='official'?current.get(ref.talkId):rows.get(ref.talkId);
 if(!row)throw Error('Missing preserved context Talk ID '+ref.talkId);
 const roles=[...new Set(ref.references.map(r=>r.displayKind))];
 const usageLabels=[...new Set(ref.references.map(r=>r.usageLabel).filter(Boolean))];
 const targetRegions=group.source==='ExcelOutput/HeartDialTalk.json'?[...new Set(ref.references.flatMap(r=>r.recordContext.fields.FloorIDList||[]))].map(id=>contexts.regions[String(id)]).filter(r=>r&&r.name!=='지역 이름 미확인'):[];
 return {...row,contextReferences:ref.references,usageLabels,targetRegions,displayKind:roles.join('·'),isChoice:roles.includes('선택지'),isDialogue:roles.includes('대사')};
});
export const contextLinks=new Map<number,any[]>();
for(const group of contexts.groups)for(const ref of group.rows){
 const list=contextLinks.get(ref.talkId)||[];
 list.push({id:group.id,title:group.title,kind:group.kind});contextLinks.set(ref.talkId,list);
}
export const contextRegions=(group:any)=>[...new Map(group.regions.map(r=>{const region=contexts.regions[String(r.floorId)];return [region.name+' · '+region.world,region];})).values()] as any[];
