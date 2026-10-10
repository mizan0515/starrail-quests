import universe from '../../data/universe-catalog.json';
import backgrounds from '../../data/relic-backgrounds.json';
import handbook from '../../data/handbook-originals.json';
const addedCategories:Record<string,string>={'light-cones':'광추 이야기',items:'아이템 설정',relics:'유물 이야기',curios:'시뮬레이션 우주 설정'};
import {doc,href} from './data';
const subjects=universe.itemCollections.map(collection=>({...collection,items:[...collection.documents,...handbook.documents.filter(d=>d.category===addedCategories[collection.id]).map(d=>({...d,excerpt:d.sections.flatMap(s=>s.rows.map(r=>r.text)).join(' ').slice(0,220),searchText:d.sections.flatMap(s=>s.rows.map(r=>r.text)).join(' ')}))].map(d=>{
 const original=doc(d.id),texts=original.sections.flatMap(s=>s.rows.map(r=>r.text)).filter(Boolean);
 const nameOnly=texts.length>0&&texts.every(text=>text.trim()===d.title.trim());
 return {id:d.id,name:d.title,kind:nameOnly?'원문 · 명칭':collection.name+' · 원문',summary:nameOnly?'수록된 본문 필드는 이 명칭과 같습니다. 개별 원문에서 자료 식별자를 확인할 수 있습니다.':d.excerpt,url:href(d.url),searchText:d.searchText||texts.join(' '),nameOnly};
})}));
const descriptions:Record<string,string>={curios:'기물의 제작, 사용과 발견에 관한 배경 문구를 읽습니다.',relics:'유물의 모습과 유래를 설명하는 짧은 원문입니다. 장문 배경 이야기는 별도 묶음에서 읽을 수 있습니다.','light-cones':'광추의 설명과 배경 이야기 원문입니다.',items:'물품에 기록된 설명, 인물의 발언과 배경 문구를 이름이나 구절로 찾습니다.'};
export const itemGroups=[...subjects.map(c=>({id:c.id,title:c.name,summary:descriptions[c.id],items:c.items.filter(i=>!i.nameOnly)})),{id:'relic-backgrounds',title:'유물의 배경 이야기',summary:'유물의 이름과 짧은 설명에 연결되는 장문 기록입니다. 그라모스, 기억과 문명에 관한 이야기를 개별 원문으로 읽습니다.',items:backgrounds.records.map(r=>({id:r.id,name:r.title,kind:'유물 배경 이야기 · 원문',summary:r.text.slice(0,220),searchText:[r.title,r.storyTitle,r.text].join(' '),url:href('유물/'+r.id+'.html')}))},{id:'item-names',title:'명칭이 수록된 자료',summary:'본문에 이름이 수록된 자료입니다. 각 자료의 원문 필드는 해당 명칭과 같은 내용이며, 식별자와 함께 확인할 수 있습니다.',items:subjects.flatMap(c=>c.items.filter(i=>i.nameOnly))}].filter(g=>g.items.length);
