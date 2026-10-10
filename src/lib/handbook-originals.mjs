/** An additive view of preserved documents and independently observed originals. */
const indexes=new WeakMap();
function index(payload){
 if(indexes.has(payload))return indexes.get(payload);
 if(payload.schemaVersion!=='starrail-handbook-originals.v1')throw Error('Unknown handbook source profile');
 const documents=new Map();
 for(const d of payload.documents){if(documents.has(d.id))throw Error('Duplicate handbook document '+d.id);documents.set(d.id,d);}
 const result={documents,extensions:new Map(Object.entries(payload.extensions))};indexes.set(payload,result);return result;
}
export const handbookDocument=(id,payload)=>index(payload).documents.get(id);
export const handbookSearchText=d=>[d.title,...d.sections.flatMap(s=>[s.title,...s.rows.map(r=>r.text)])].join(' ');
export function extendDocument(original,id,payload){
 const {documents,extensions}=index(payload),fresh=documents.get(id);
 if(fresh){if(original)throw Error('Handbook overwrites original '+id);return fresh;}
 if(!original)throw Error('Unknown original '+id);
 const sections=extensions.get(id);
 if(!sections)return original;
 const anchors=new Set(original.sections.map(s=>s.anchor));
 for(const s of sections){if(anchors.has(s.anchor))throw Error('Duplicate original anchor '+id+'/'+s.anchor);anchors.add(s.anchor);}
 return {...original,sections:[...original.sections,...sections],count:original.count+sections.reduce((n,s)=>n+s.rows.length,0),handbookExtended:true};
}
export function extendCatalog(original,payload){
 const ids=new Set(original.map(d=>d.id)),{documents,extensions}=index(payload);
 for(const id of documents.keys())if(ids.has(id))throw Error('Handbook catalog collision '+id);
 for(const id of extensions.keys())if(!ids.has(id))throw Error('Handbook extension has no original '+id);
 return [...original.map(d=>{const ss=extensions.get(d.id);return ss?{...d,count:d.count+ss.reduce((n,s)=>n+s.rows.length,0),searchText:[d.searchText||'',...ss.flatMap(s=>[s.title,...s.rows.map(r=>r.text)])].join(' '),handbookExtended:true}:d;}),...payload.documents.map(d=>{
  const {sections,titleProof,...entry}=d;return {...entry,searchText:handbookSearchText(d)};
 })];
}
export function extendExplorer(original,payload){
 const extra=payload.documents.filter(d=>d.category==='캐릭터 이야기').map(d=>{
  const aid=d.sections[0].rows[0].avatar_id;
  return {id:'person-'+aid,axis:'person',name:d.title,nameVerified:true,source:'StoryAtlas',sourceDocument:d.id,documents:[d.id],excerpt:d.sections[0].rows[0].text.slice(0,220),description:'',evidence:[],mentions:[],stories:d.sections.map(s=>({...s.rows[0],label:s.title,anchor:s.anchor,handbookProof:s.handbookProof,handbookRelations:s.handbookRelations})),handbookNameProof:d.titleProof};
 });
 const ids=new Set(original.entries.map(e=>e.id));for(const e of extra)if(ids.has(e.id))throw Error('Handbook explorer collision '+e.id);
 return {...original,entries:[...original.entries,...extra],counts:{...original.counts,person:original.counts.person+extra.length}};
}
export function handbookDirectoryGroups(payload,resolve,url){
 const variants=new Map(payload.sameTitleGroups.map(g=>[g.representativeId,g]));
 return payload.groups.map(g=>({id:g.id,title:g.title,summary:g.id==='monsters'?'같은 명칭을 가진 표 항목은 한 카드에서 찾고, 각 변형의 원문과 식별자를 따로 읽습니다.':g.id==='blessings'?'축복·메아리 등록 표의 명시된 ID·레벨에 연결된 원문입니다. 수치 자리표시는 원문 그대로 읽습니다.':'자료명이나 본문 구절로 원문을 찾습니다.',items:g.documentIds.flatMap(id=>{
  const d=resolve(id),v=variants.get(id);
  if(d.sameTitleRepresentativeId&&d.sameTitleRepresentativeId!==id)return [];
  const ids=v?.documentIds||[id],all=ids.map(resolve),text=all.map(handbookSearchText).join(' ');
  return [{id,name:d.title,kind:d.category+(d.recordLevel!==undefined?' · 레벨 '+d.recordLevel:''),summary:d.sections.flatMap(s=>s.rows.map(r=>r.text)).join(' ').slice(0,220)+(ids.length>1?` · 같은 명칭의 표 항목 ${ids.length}개`:''),searchText:text+' '+ids.join(' '),url:url(id)}];
 })}));
}
