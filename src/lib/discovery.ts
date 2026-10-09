import registry from '../../editorial/directory-discovery.json';
import {dataset,entityUrl} from './explorer';
import {atlas,atlasUrl} from './atlas';
import {doc,docUrl,href} from './data';
const byId=new Map(registry.rows.map(r=>[r.id,r]));
const kindLabels:Record<string,string>={person:'인물 소개 · 원문',faction:'집단 소개 · 원문',region:'장소 소개 · 원문',concept:'설정 설명 · 원문',mechanic:'전투·성장 안내 · 원문','reading-instruction':'시점·장면 안내 · 원문'};
export const discoveryAxes=[{id:'region',name:'지역',question:'역사·장소·생활의 기록'},{id:'person',name:'인물',question:'인물의 소개·과거·행적과 발언'},{id:'faction',name:'세력',question:'조직·단체의 목적과 구성'},{id:'concept',name:'세계관',question:'세계의 법칙·현상·종족·사건'},{id:'aeon',name:'에이언즈',question:'운명의 길과 신들의 기록'},{id:'reference',name:'게임 안내',question:'전투·성장과 시점 전환 안내'}].map(a=>({...a,url:href(a.id==='faction'?'세력.html':`관점/${a.id}.html`)}));
export const discoveryEntries=dataset.entries.map(e=>{
 const rule=byId.get(e.id);if(e.axis==='concept'&&!rule)throw Error('Unclassified original '+e.id);
 const axis=rule?rule.subjectType==='aeon'?'aeon':['mechanic','reading-instruction'].includes(rule.kind)?'reference':rule.kind:e.axis;
 return {id:e.id,name:e.name,axis,group:rule?.group||'source-'+e.axis,kind:rule?rule.subjectType==='aeon'?'에이언즈 소개 · 원문':rule.subjectType==='named-lifeform'?'생명체 소개 · 원문':kindLabels[rule.kind]:e.axis==='person'?'인물 이야기 · 원문':e.axis==='aeon'?'에이언즈 기록 · 원문':'지역 자료집',summary:e.excerpt,searchText:[e.name,e.excerpt,...(e.stories||[]).map(s=>s.text)].join(' '),url:entityUrl(e)};
});
const rawGroups=[...registry.groups,{id:'source-region',title:'지역별 원문 자료집',summary:'게임 표의 지역 이름으로 연결된 임무·서적·설정 기록입니다.'},{id:'source-person',title:'인물 이야기',summary:'인물의 과거와 행적을 설명하는 StoryAtlas 원문입니다. 이름 미확인 기록도 함께 보존합니다.'},{id:'source-aeon',title:'에이언즈의 관측 기록',summary:'에이언즈에 관한 기록자의 설명과 관점을 개별 원문에서 읽습니다.'}];
export const discoveryGroups=rawGroups.map(g=>({...g,items:discoveryEntries.filter(e=>e.group===g.id)})).filter(g=>g.items.length);
export const curatedGroups=discoveryAxes.filter(a=>a.id!=='reference'&&a.id!=='aeon').map(a=>({id:'curated-'+a.id,title:a.name+'의 사건과 관계',summary:'원문을 대조해 정리한 설명과 관계를 함께 읽습니다.',items:atlas.nodes.filter(n=>(n.directoryKind==='종족'?'concept':n.axis==='bridge'?'faction':n.axis)===a.id).map(n=>({id:'atlas-'+n.id,name:n.name,axis:a.id,kind:n.directoryKind||'원문을 대조한 설명',summary:n.directorySummary||n.intro,searchText:[n.name,n.question,n.intro,...n.terms].join(' '),url:atlasUrl(n.id)}))})).filter(g=>g.items.length);
const archive=doc('book-47');
export const factionArchiveGroup={id:'archive-factions',title:'열차의 파벌 아카이브',summary:'열차 아카이브에 수록된 파벌별 기록입니다. 자료명을 누르면 각 파벌의 원문으로 이동합니다.',items:archive.sections.slice(2).map(s=>({id:'book-47-'+s.anchor,name:s.title,axis:'faction',kind:'파벌 아카이브 · 원문',summary:s.rows.map(r=>r.text).join('\n').slice(0,240),searchText:s.rows.map(r=>r.text).join('\n'),url:docUrl('book-47')+'#'+s.anchor+'-row-1'}))};
export const allDiscoveryGroups=[...curatedGroups,...discoveryGroups,factionArchiveGroup];
