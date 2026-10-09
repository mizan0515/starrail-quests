import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {applySourceIdentities} from './source-identities.mjs';

const original=JSON.parse(fs.readFileSync('data/explorer.json','utf8'),(_key,value,context)=>typeof value==='number'&&!Number.isSafeInteger(value)?context.source:value);
const identities=JSON.parse(fs.readFileSync('editorial/directory-discovery.json','utf8')).identities;

test('source identity changes reader labels while preserving every source story and entry',()=>{
  const before=JSON.stringify(original);
  const derived=applySourceIdentities(original,identities);
  assert.equal(JSON.stringify(original),before);
  assert.equal(derived.entries.length,original.entries.length);
  for(const [index,entry] of original.entries.entries()){
    const effective=derived.entries[index];
    assert.strictEqual(effective.stories,entry.stories);
    const identity=identities.find(i=>i.id===entry.id);
    if(!identity) assert.strictEqual(effective,entry);
    else {
      assert.equal(effective.sourceName,entry.name);
      assert.deepEqual(effective,{...entry,sourceName:entry.name,name:identity.name,nameVerified:true,nameEvidence:identity,group:'본문에 이름이 명시된 기록'});
    }
  }
  const hero=derived.entries.find(e=>e.id==='person-1509');
  assert.equal(hero.name,'길가메시');
  assert.equal(hero.nameEvidence.hash,'16429243332190848941');
  assert.equal(hero.nameEvidence.storyId,2);
});

for(const [label,change] of [
  ['wrong story',i=>i.storyId=1],['wrong hash',i=>i.hash='1'],
  ['wrong character',i=>i.id='person-1005'],['unknown character',i=>i.id='person-unknown'],
  ['invented name',i=>i.name='가상의 이름'],['invented quotation',i=>i.quote+=' 가상 문장'],
  ['empty name',i=>i.name=''],['numeric hash precision loss',i=>i.hash=Number(i.hash)],
]) test('rejects '+label,()=>{
  const changed=structuredClone(identities);change(changed[0]);
  assert.throws(()=>applySourceIdentities(original,changed),/Unverified source identity/);
});
test('rejects duplicate identity or duplicate source story',()=>{
  assert.throws(()=>applySourceIdentities(original,[...identities,identities[0]]),/Duplicate source identity/);
  const changed=structuredClone(original),entry=changed.entries.find(e=>e.id===identities[0].id);
  entry.stories.push(entry.stories.find(s=>s.story_id===identities[0].storyId));
  assert.throws(()=>applySourceIdentities(changed,identities),/Unverified source identity/);
});
