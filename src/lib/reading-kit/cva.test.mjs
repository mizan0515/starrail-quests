import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {renderCvaModule,cvaModuleDefinitions} from './cva.mjs';

const escaped=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sourceText='원문 <태그> & 기호 "인용" </script><script>alert(1)</script>';
const inputItems=Array.from({length:4},(_,index)=>({id:'source-'+index,title:'원문 제목 '+index,body:sourceText+' '+index,label:'원문 구절',value:index===0?'입력 값':'',image:''}));
const models=html=>JSON.parse(html.match(/<script type="application\/json" data-cva-model data-pagefind-ignore>([\s\S]*?)<\/script>/)[1]);
const visible=html=>html.replace(/<script type="application\/json"[\s\S]*?<\/script>/g,'');
const definition=type=>cvaModuleDefinitions.find(value=>value.type===type);
const sourceAsset={id:'source-image',src:'/verified/source-image.webp',alt:'검증용 대체 텍스트 < & >',width:731,height:419,sourceUrl:'https://example.org/verified-original'};

function inputFor(type,variant){
 const fields=definition(type).fields,props={title:'실제 입력 제목',body:sourceText};
 if(fields.some(field=>field.key==='relationLabel'))props.relationLabel='입력된 관계 문장';
 if(fields.some(field=>field.key==='caption'))props.caption='입력된 출처 문장';
 if(fields.some(field=>field.key==='cite'))props.cite='입력된 인용 출처';
 const hasItems=fields.some(field=>field.kind==='items');
 const items=hasItems?inputItems.slice(0,type==='scene-composition'&&variant==='before-after'?2:4):undefined;
 return {id:'module-under-test',type,variant,props,...(hasItems?{items}:{})};
}

test('canonical authored subset exposes 14 types and 52 original variants, with actual vendor source hashes',()=>{
 assert.equal(cvaModuleDefinitions.length,14);
 assert.equal(cvaModuleDefinitions.reduce((count,value)=>count+value.variants.length,0),52);
 const base=new URL('./cva/',import.meta.url),p=JSON.parse(fs.readFileSync(new URL('provenance.json',base),'utf8'));
 assert.equal(p.license,'GPL-3.0');
 for(const file of p.files){
  const hash=crypto.createHash('sha256').update(fs.readFileSync(new URL(file.file,base))).digest('hex');
  assert.equal(hash,file.vendorSha256);
  if(!file.adaptation)assert.equal(file.sourceSha256,file.vendorSha256);
  else assert.equal(crypto.createHash('sha256').update(file.patch).digest('hex'),file.patchSha256);
 }
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(new URL(p.licenseFile,base))).digest('hex'),p.licenseSha256);
 const adapter=fs.readFileSync(new URL('./cva.mjs',import.meta.url),'utf8');
 for(const api of ['CVA_MODULES.create','CVA_MODULES.normalizeDocument','CVA_RENDERER.renderBlock'])assert.ok(adapter.includes(api));
});

test('all 52 actual variants × 4 profiles × 3 orientations preserve the supplied model and escaped body',()=>{
 let count=0;
 for(const entry of cvaModuleDefinitions)for(const variant of entry.variants){
  const input=inputFor(entry.type,variant.id);let prior;
  for(const profile of ['ttaem','elio','editor','forma'])for(const orientation of ['original','vertical','horizontal']){
   const html=renderCvaModule({...input,profile,orientation}),doc=models(html),block=doc.modules[0];count++;
   assert.equal(doc.profile,profile);assert.equal(block.orientation,orientation);assert.equal(block.type,entry.type);assert.equal(block.variant,variant.id);
   assert.equal(block.props.body,sourceText);
   assert.ok(html.includes('data-cva-profile="'+profile+'"')&&html.includes('data-orientation="'+orientation+'"'));
   assert.ok(!visible(html).includes('<h1'));
   assert.ok(!visible(html).includes('<script'));
   assert.ok(html.includes(escaped(sourceText)));
   const signature=JSON.stringify({...block,orientation:undefined});
   if(prior)assert.equal(signature,prior);else prior=signature;
   if(input.items){
    assert.deepEqual(block.props.items,input.items);
    for(const item of input.items)assert.ok(html.includes(escaped(item.body)));
    assert.equal((html.match(/data-cva-item-index="/g)||[]).length,input.items.length);
   }
  }
 }
 assert.equal(count,624);
});

test('missing and explicitly undefined fields are empty, and authored fixture text/images never leak',()=>{
 for(const entry of cvaModuleDefinitions)for(const variant of entry.variants){
  const hasItems=entry.fields.some(field=>field.kind==='items');
  const items=entry.type==='flow'?Array.from({length:variant.id==='fork-join'?4:2},(_,i)=>({id:'empty-'+i,title:'',body:''})):[];
  const html=renderCvaModule({id:'empty-model',type:entry.type,variant:variant.id,props:{title:undefined,body:null},...(hasItems?{items}:{})});
  const block=models(html).modules[0];
  for(const field of entry.fields)assert.deepEqual(block.props[field.key],field.kind==='items'?items:'');
  assert.ok(!visible(html).includes('<img'));
  for(const forbidden of ['brand-welcome','scene-hub-role','product-architecture','가상 예시','작성 예시','CVA / PAGE','루파의 기억','청동거울을,','제공된 Elio','내용을 추가하면','장면 자료를 먼저','관계 문구를 입력하면'])assert.ok(!html.includes(forbidden),forbidden);
 }
});

test('trusted link/evidence slots use each actual item ordinal and preserve escaped original body',()=>{
 for(const entry of cvaModuleDefinitions.filter(value=>value.fields.some(field=>field.kind==='items')))for(const variant of entry.variants){
  const input=inputFor(entry.type,variant.id),titles=input.items.map((item,i)=>'<a href="/documents/'+i+'.html">'+escaped(item.title)+'</a>');
  const extras=input.items.map((item,i)=>'<details><summary>원문 근거 '+i+'</summary><a href="/source/'+i+'.html">원문 확인 '+i+'</a></details>');
  const html=renderCvaModule({...input,itemTitles:titles,itemExtras:extras});
  input.items.forEach((item,index)=>{
   assert.ok(html.includes(escaped(item.body)));
   assert.equal(html.split(titles[index]).length-1,1);
   assert.equal(html.split(extras[index]).length-1,1);
   const marker='data-cva-item-extra="'+index+'"';assert.ok(html.includes(marker));
  });
  assert.deepEqual(models(html).modules[0].props.items,input.items);
 }
});

test('registered media stays isolated and preserves explicit dimensions, alt and source',()=>{
 const base={id:'media-test',type:'cards',variant:'grid',items:[{id:'image-item',title:'원문 이미지',body:'원문 설명',image:sourceAsset.id}],media:[sourceAsset]};
 const html=renderCvaModule(base);assert.ok(html.includes('width="731" height="419"'));
 assert.ok(html.includes('src="'+sourceAsset.src+'"')&&html.includes('alt="'+escaped(sourceAsset.alt)+'"'));
 assert.ok(html.includes('data-source-url="'+sourceAsset.sourceUrl+'"')&&html.includes('href="'+sourceAsset.sourceUrl+'"'));
 assert.ok(html.includes('data-cva-media data-pagefind-ignore'));
 assert.throws(()=>renderCvaModule({...base,media:[]}));
 const next={...sourceAsset,src:'/other-game/another.webp',alt:'다른 자료',width:101,height:203};
 const second=renderCvaModule({...base,media:[next]});
 assert.ok(second.includes('width="101" height="203"')&&!second.includes(sourceAsset.src));
 assert.ok(renderCvaModule(base).includes(sourceAsset.src));
});

test('invalid IDs, unknown types/variants/profiles/orientations and invented media fail closed',()=>{
 const input={id:'safe-module',type:'text',variant:'prose',props:{body:'원문'}};
 for(const change of [{id:undefined},{id:'나쁜 id'},{id:'cva-page-top'},{type:'unknown'},{type:'forma-pattern',variant:'original'},
  {variant:'made-up'},{profile:'unknown'},{orientation:'diagonal'},{props:{html:'<b>임의 HTML</b>'}}])assert.throws(()=>renderCvaModule({...input,...change}));
 assert.throws(()=>renderCvaModule({...input,props:JSON.parse('{"__proto__":{"title":"bad"}}')}));
 for(const change of [{src:'https://example.org/image.webp'},{src:'../source.webp'},{src:'assets/%2e%2e/source.webp'},
  {src:'//remote/image.webp'},{width:0},{width:1.5},{height:undefined},{sourceUrl:'javascript:alert(1)'}])assert.throws(()=>renderCvaModule({...input,media:[{...sourceAsset,...change}]}));
 assert.throws(()=>renderCvaModule({...input,media:[sourceAsset,sourceAsset]}));
 const cards={id:'bad-items',type:'cards',variant:'grid',items:[inputItems[0]]};
 assert.throws(()=>renderCvaModule({...cards,items:[inputItems[0],inputItems[0]]}));
 assert.throws(()=>renderCvaModule({...cards,itemExtras:['<script>alert(1)</script>']}));
 assert.throws(()=>renderCvaModule({...cards,itemTitles:['<a onclick="bad()">원문</a>']}));
 assert.throws(()=>renderCvaModule({...cards,itemExtras:['one','two']}));
});

test('24 item bound is exact, and embedded model JSON safely round-trips closing script text',()=>{
 const items=Array.from({length:24},(_,index)=>({id:'bounded-'+index,title:'제목 '+index,body:sourceText}));
 const input={id:'bounded-module',type:'cards',variant:'list',items};
 const html=renderCvaModule(input);assert.equal(models(html).modules[0].props.items.length,24);
 assert.equal((html.match(/data-cva-item-index="/g)||[]).length,24);
 assert.throws(()=>renderCvaModule({...input,items:[...items,{id:'extra-item',title:'',body:''}]}));
 const raw=html.match(/data-cva-model data-pagefind-ignore>([\s\S]*?)<\/script>/)[1];
 assert.ok(!raw.includes('<')&&raw.includes('\\u003c/script>'));
 assert.equal(JSON.parse(raw).modules[0].props.items[0].body,sourceText);
 const quoted='<pre>'+escaped('원문 코드 onclick="source()" javascript: 설명 <script>원문</script>')+'</pre>';
 const withQuote=renderCvaModule({id:'quoted-source',type:'cards',variant:'list',items:[items[0]],itemExtras:[quoted]});
 assert.ok(withQuote.includes(quoted));
 assert.throws(()=>renderCvaModule({id:'long-body',type:'text',variant:'prose',props:{body:'가'.repeat(20001)}}));
});

test('CSS imports actual scoped source, keeps site tones and keyboard/narrow screen rules',()=>{
 const css=fs.readFileSync(new URL('./cva.css',import.meta.url),'utf8');
 assert.ok(css.includes("@import './cva/vendor/module-styles.css'")&&css.includes("@import './cva/vendor/scene-styles.css'"));
 assert.ok(css.includes('--cva-accent:var(--brass,var(--sl-color-accent))')&&css.includes('--cva-bg:var(--paper,var(--sl-color-black))'));
 assert.ok(css.includes(':focus-visible')&&css.includes('max-width:600px')&&css.includes('prefers-reduced-motion'));
 assert.ok(!/^\s*(?:body|:root|h1|h2|p|img)\s*[{,]/m.test(css));
 assert.ok(!css.includes('@font-face')&&!css.includes('http'));
});
