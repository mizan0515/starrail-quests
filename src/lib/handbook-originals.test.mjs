import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {extendCatalog,extendDocument,extendExplorer,handbookDocument,handbookDirectoryGroups} from './handbook-originals.mjs';
import {safeReadingReturn,isReadingCatalogue} from './reading-return.mjs';
const read=p=>JSON.parse(fs.readFileSync(new URL('../../'+p,import.meta.url),'utf8'));
const payload=read('data/handbook-originals.json'),catalog=read('data/catalog.json'),old=read('data/documents/book-647.json');
const resolve=id=>extendDocument(handbookDocument(id,payload)?null:read('data/documents/'+id+'.json'),id,payload);
test('new volume is in the existing series, preserves all old anchors and adds searchable text',()=>{
 const copy=structuredClone(old),d=extendDocument(old,'book-647',payload);
 assert.deepEqual(old,copy);assert.deepEqual(d.sections.slice(0,old.sections.length),old.sections);
 assert.equal(d.sections.at(-1).rows[0].book_id,192195);assert.equal(d.sections.at(-1).anchor,'official46-book-192195');
 const c=extendCatalog(catalog.map(x=>x.id==='book-647'?{...x,searchText:'old catalogue phrase'}:x),payload).find(x=>x.id==='book-647');
 assert(c.searchText.includes('old catalogue phrase'));assert(c.searchText.includes('외톨이 개구리'));
 assert.equal(c.count,old.count+1);
});
test('Pearl uses exact name annotation and all five source sections without changing old explorer',()=>{
 const original=read('data/explorer.json'),copy=structuredClone(original),next=extendExplorer(original,payload),e=next.entries.find(e=>e.id==='person-1503');
 assert.deepEqual(original,copy);assert.equal(e.name,'펄');assert.equal(e.stories.length,5);assert.equal(e.handbookNameProof.handbookSource.kind,'PINNED_METADATA_HASH_REFERENCE');
 assert.deepEqual(e.stories.map(s=>s.anchor),['official46-story-1','official46-story-2','official46-story-3','official46-story-4','official46-story-5']);
 assert.equal(next.counts.person,original.counts.person+1);
});
test('title folding retains every variant and searchable nonrepresentative source text',()=>{
 const groups=handbookDirectoryGroups(payload,resolve,id=>'/starrail-quests/문서/'+id+'.html');
 const variant=payload.sameTitleGroups.find(g=>g.group==='monsters'&&g.documentIds.length>1);
 const card=groups.find(g=>g.id==='monsters').items.find(i=>i.id===variant.representativeId);
 assert(card);assert.equal(groups.find(g=>g.id==='monsters').items.filter(i=>variant.documentIds.includes(i.id)).length,1);
 for(const id of variant.documentIds){assert(card.searchText.includes(id));assert.deepEqual(resolve(id).sameTitleDocumentIds,variant.documentIds);}
 assert(groups.find(g=>g.id==='books').items.some(i=>i.id==='book-647'));
 assert.equal(groups.find(g=>g.id==='blessings').title,'축복·메아리 원문');
});
test('catalog collisions, missing extension targets and anchor collisions fail',()=>{
 const bad={...payload,extensions:{'absent-original':payload.extensions['book-647']}};
 assert.throws(()=>extendCatalog(catalog,bad),/no original/);
 assert.throws(()=>extendDocument({...old,sections:[...old.sections,payload.extensions['book-647'][0]]},old.id,payload),/Duplicate original anchor/);
 assert.throws(()=>extendCatalog([...catalog,payload.documents[0]],payload),/collision/);
});
test('handbook return preserves query/group/anchor but rejects external and traversal origins',()=>{
 const options={origin:'https://mizan0515.github.io',base:'/starrail-quests'},origin='/starrail-quests/도감.html?q=얼음&group=monsters#handbook-entry-'+payload.documents[0].id;
 assert(isReadingCatalogue(origin,options));
 const reader='/starrail-quests/문서/'+payload.documents[0].id+'.html?from='+encodeURIComponent(origin);
 assert.equal(new URL(safeReadingReturn(reader,options),options.origin).searchParams.get('from'),new URL(origin,options.origin).pathname+new URL(origin,options.origin).search+new URL(origin,options.origin).hash);
 assert.equal(safeReadingReturn('https://evil.invalid/starrail-quests/도감.html',options),null);
 assert.equal(safeReadingReturn('/starrail-quests/../도감.html',options),null);
});
