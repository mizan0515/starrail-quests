/* GPL-3.0 CVA source adapter. The canonical renderer owns every module layout. */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

const sourceNames=['components.js','scene-catalog.js','modules.js','scene-renderer.js','module-renderer.js'];
// Astro prerender bundles move import.meta.url; its build runs from the site root.
const colocated=new URL('./cva/vendor/components.js',import.meta.url);
const vendorRoot=fs.existsSync(colocated)?new URL('./cva/vendor/',import.meta.url):path.resolve('src/lib/reading-kit/cva/vendor');
const scripts=sourceNames.map(name=>new vm.Script(fs.readFileSync(vendorRoot instanceof URL?new URL(name,vendorRoot):path.join(vendorRoot,name),'utf8'),{filename:'cva/vendor/'+name}));
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const idPattern=/^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);

function plain(value,where){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.getPrototypeOf(value)!==Object.prototype)throw new TypeError(where+' must be a plain data object');
 if(Object.getOwnPropertySymbols(value).length)throw new TypeError(where+' contains a symbol');
 for(const [key,descriptor] of Object.entries(Object.getOwnPropertyDescriptors(value))){
  if(['__proto__','constructor','prototype'].includes(key)||descriptor.get||descriptor.set)throw new TypeError(where+' contains an unsafe field');
 }
 return value;
}

function text(value,where){
 if(typeof value!=='string'||value.length>20000)throw new TypeError(where+' must be text of at most 20000 characters');
 return value;
}

function localSource(value){
 text(value,'media.src');
 if(!/^\/?[A-Za-z0-9_%.-]+(?:\/[A-Za-z0-9_%.-]+)*\.(?:png|jpe?g|webp|gif|avif|svg)$/i.test(value)||value.startsWith('//'))throw new TypeError('media.src must be an approved local image path');
 let decoded;try{decoded=decodeURIComponent(value);}catch{throw new TypeError('media.src is not a valid local path');}
 if(decoded.includes('\\')||decoded.split('/').some(part=>part==='.'||part==='..')||/[\u0000-\u0020<>"':?#]/.test(decoded))throw new TypeError('media.src is not a safe local image path');
 return value;
}

function sourceURL(value){
 if(value===undefined||value==='')return '';
 text(value,'media.sourceUrl');
 if(/^https:\/\//.test(value)){
  const url=new URL(value);if(url.username||url.password)throw new TypeError('Image source credentials are not allowed');
  return value;
 }
 if(/^\/[A-Za-z0-9_%./-]+$/.test(value)&&!value.startsWith('//')&&!decodeURIComponent(value).split('/').some(part=>part==='..'))return value;
 throw new TypeError('media.sourceUrl must be an explicit HTTPS or local source URL');
}

function mediaRegistry(input){
 if(!Array.isArray(input)||input.length>25)throw new TypeError('media must be a local registry of at most 25 images');
 const ids=new Set(),sources=new Set();
 return input.map((asset,index)=>{
  plain(asset,'media['+index+']');
  const allowed=['id','src','alt','width','height','sourceUrl','label','kind'];
  if(Object.keys(asset).some(key=>!allowed.includes(key)))throw new TypeError('Unknown media field');
  if(!idPattern.test(asset.id)||ids.has(asset.id))throw new TypeError('Media IDs must be unique safe identifiers');
  ids.add(asset.id);const src=localSource(asset.src);
  if(sources.has(src))throw new TypeError('Register each local image once');sources.add(src);
  if(!Number.isInteger(asset.width)||!Number.isInteger(asset.height)||asset.width<1||asset.height<1||asset.width>32768||asset.height>32768)throw new TypeError('Actual image dimensions are required');
  return {id:asset.id,label:text(asset.label??'','media.label'),src,alt:text(asset.alt,'media.alt'),
   width:asset.width,height:asset.height,sourceUrl:sourceURL(asset.sourceUrl),kind:'source'};
 });
}

function runtime(registry=[]){
 const context=vm.createContext({},{codeGeneration:{strings:false,wasm:false}});
 context.window=context;
 // A fresh context prevents a game's image registry or create state leaking into another call.
 context.__registry=JSON.stringify(registry);
 new vm.Script("window.CVA_LOCAL_MEDIA=JSON.parse(__registry);window.CVA_LOCAL_SCENE_ITEMS=Array.from({length:3},(_,i)=>({id:'empty-source-'+i,title:'',body:'',label:'',image:''}));").runInContext(context);
 for(const script of scripts)script.runInContext(context);
 return context;
}

const definitionContext=runtime();
export const cvaModuleDefinitions=Object.freeze(JSON.parse(JSON.stringify(definitionContext.CVA_MODULES.definitions.filter(value=>value.type!=='forma-pattern').map(({type,variants,fields})=>({type,variants,fields})))));

function approvedHTML(values,count,name){
 if(!Array.isArray(values)||values.length>count)throw new TypeError(name+' must align with the input item order');
 return values.map(value=>{
  if(value===undefined||value===null)return '';
  if(typeof value!=='string'||value.length>200000)throw new TypeError(name+' accepts internally generated HTML strings only');
  // Source quotations may contain words such as "onclick=" as escaped text. Only
  // actual markup tags are examined; never reject or rewrite quoted source text.
  for(const tag of value.match(/<[^>]+>/g)??[]){
   if(/^<\s*(?:script|iframe|object|embed|style|link)\b|\bon[a-z]+\s*=|(?:javascript|vbscript)\s*:/i.test(tag))throw new TypeError(name+' contains active HTML');
  }
  return value;
 });
}

// This scanner only locates containers emitted by the known canonical renderer. It never
// constructs a layout or parses supplied text: all supplied text has already been escaped.
function tree(html){
 const roots=[],stack=[],nodes=[];let match;
 const token=/<\/?([a-z][\w:-]*)(?:\s[^>]*?)?\s*\/?>/gi;
 while((match=token.exec(html))){
  const tag=match[1].toLowerCase(),closing=match[0][1]==='/';
  if(closing){
   const node=stack.pop();if(!node||node.tag!==tag)throw new Error('Canonical CVA HTML is unbalanced');
   node.closeStart=match.index;node.end=token.lastIndex;continue;
  }
  const attrs=match[0],node={tag,attrs,start:match.index,openEnd:token.lastIndex,closeStart:token.lastIndex,end:token.lastIndex,children:[],parent:stack.at(-1)??null};
  node.classes=new Set((attrs.match(/\bclass="([^"]*)"/)?.[1]??'').split(/\s+/));
  node.id=attrs.match(/\bid="([^"]*)"/)?.[1]??'';
  (node.parent?node.parent.children:roots).push(node);nodes.push(node);
  if(!voidTags.has(tag)&&!attrs.endsWith('/>'))stack.push(node);
 }
 if(stack.length)throw new Error('Canonical CVA HTML is incomplete');
 return {roots,nodes};
}

function inside(node,parent){return node.start>=parent.openEnd&&node.end<=parent.closeStart;}
function replaceRanges(html,ranges){
 const sorted=ranges.sort((a,b)=>b.start-a.start||b.end-a.end);let limit=html.length;
 for(const range of sorted){if(range.end>limit)throw new Error('CVA adapter ranges overlap');html=html.slice(0,range.start)+range.value+html.slice(range.end);limit=range.start;}
 return html;
}

function annotateItems(html,block,extras,titles,bodies){
 const count=block.props.items?.length??0;if(!count)return html;
 const {nodes}=tree(html),ranges=[];
 const titleFor=(node,index)=>{
  if(!titles[index])return;
  const descendants=nodes.filter(child=>inside(child,node));
  let title=descendants.find(child=>child.classes.has('sc-item-title')||child.classes.has('cva-item-title'));
  if(!title&&node.tag==='details'){
   const summary=descendants.find(child=>child.tag==='summary');
   title=descendants.find(child=>child.tag==='span'&&summary&&inside(child,summary)&&html.slice(child.openEnd,child.closeStart)===escape(block.props.items[index].title));
  }
  if(!title)throw new Error('Canonical CVA item title slot is missing');
  if(html.slice(title.openEnd,title.closeStart)!==escape(block.props.items[index].title))throw new Error('Canonical CVA title differs from the normalized item');
  ranges.push({start:title.openEnd,end:title.closeStart,value:titles[index]});
 };
 const itemRoot=(node,index)=>{
  ranges.push({start:node.openEnd-1,end:node.openEnd-1,value:' data-cva-item-index="'+index+'"'});
  titleFor(node,index);
  const descendants=nodes.filter(child=>inside(child,node));
  const body=descendants.find(child=>child.classes.has('sc-item-body')||child.classes.has('cva-item-body'));
  if(bodies[index]){
   if(!body||html.slice(body.openEnd,body.closeStart)!==escape(block.props.items[index].body))throw new Error('Canonical CVA body differs from the normalized item');
   ranges.push({start:body.openEnd,end:body.closeStart,value:bodies[index]});
  }
  if(!extras[index])return;
  const copy=descendants.find(child=>child.classes.has('sc-copy')||child.classes.has('cva-item-copy')||child.classes.has('cva-caption'));
  const where=body?(body.tag==='td'?body.closeStart:body.end):(copy?.closeStart??node.closeStart);
  ranges.push({start:where,end:where,value:'<div class="cva-item-extra" data-cva-item-extra="'+index+'">'+extras[index]+'</div>'});
 };
 if(block.type==='scene-composition'){
  for(let index=0;index<count;index++){
   const node=nodes.find(node=>node.id===block.id+'-scene-'+index);
   if(!node)throw new Error('Canonical scene item '+index+' is missing');
   itemRoot(node,index);
  }
 }else if(block.type==='comparison'&&block.variant==='table'){
  const columns=nodes.filter(node=>node.tag==='th'&&/\bscope="col"/.test(node.attrs)).slice(1);
  const cells=nodes.filter(node=>node.tag==='td');
  if(columns.length!==count||cells.length!==count*3)throw new Error('Canonical comparison table slots changed');
  for(let index=0;index<count;index++){
   const title=columns[index],body=cells[count*2+index];
   if(titles[index]){
    if(html.slice(title.openEnd,title.closeStart)!==escape(block.props.items[index].title))throw new Error('Comparison title is not preserved');
    ranges.push({start:title.openEnd,end:title.closeStart,value:titles[index]});
   }
   ranges.push({start:body.openEnd-1,end:body.openEnd-1,value:' data-cva-item-index="'+index+'"'});
   if(bodies[index]){
    if(html.slice(body.openEnd,body.closeStart)!==escape(block.props.items[index].body))throw new Error('Canonical comparison body differs from the normalized item');
    ranges.push({start:body.openEnd,end:body.closeStart,value:bodies[index]});
   }
   if(extras[index])ranges.push({start:body.closeStart,end:body.closeStart,value:'<div class="cva-item-extra" data-cva-item-extra="'+index+'">'+extras[index]+'</div>'});
  }
 }else{
  const roots=nodes.filter(node=>(['article','figure','details'].includes(node.tag)&&node.classes.has('cva-item'))
   ||node.tag==='li'&&(node.classes.has('cva-step')||node.classes.has('cva-node')));
  if(roots.length!==count)throw new Error('Canonical module item slots changed');
  roots.forEach(itemRoot);
 }
 return replaceRanges(html,ranges);
}

function annotateMedia(html,registry){
 if(!registry.length)return html;
 const {nodes}=tree(html),ranges=[];
 for(const figure of nodes.filter(node=>node.tag==='figure'&&node.classes.has('cva-media'))){
  const id=figure.attrs.match(/\bdata-media-id="([^"]*)"/)?.[1],asset=registry.find(asset=>asset.id===id);
  if(!asset)throw new Error('The renderer emitted unregistered media');
  const image=nodes.find(node=>node.tag==='img'&&inside(node,figure));
  if(!image||!image.attrs.includes('src="'+escape(asset.src)+'"')||!image.attrs.includes('alt="'+escape(asset.alt)+'"'))throw new Error('Media source or alternative text changed');
  ranges.push({start:image.openEnd-1,end:image.openEnd-1,value:' width="'+asset.width+'" height="'+asset.height+'"'});
  if(asset.sourceUrl){
   ranges.push({start:figure.openEnd-1,end:figure.openEnd-1,value:' data-source-url="'+escape(asset.sourceUrl)+'"'});
   const caption=nodes.find(node=>node.tag==='figcaption'&&inside(node,figure));
   const link='<a class="cva-image-source" href="'+escape(asset.sourceUrl)+'">이미지 출처</a>';
   ranges.push({start:caption?.closeStart??figure.closeStart,end:caption?.closeStart??figure.closeStart,
    value:caption?link:'<figcaption class="cva-caption cva-media-provenance">'+link+'</figcaption>'});
  }
 }
 return replaceRanges(html,ranges);
}

export function renderCvaModule({id,type,variant,profile='forma',orientation='vertical',props={},items,media=[],itemExtras=[],itemTitles=[],itemBodies=[]}={}){
 if(typeof id!=='string'||!idPattern.test(id))throw new Error('An explicit safe CVA module ID is required');
 if(type==='forma-pattern')throw new Error('Original Forma engines are outside the vendored authored subset');
 const registry=mediaRegistry(media),context=runtime(registry);
 plain(props,'props');
 const definition=cvaModuleDefinitions.find(value=>value.type===type);
 if(!definition)throw new Error('Unknown CVA module type');
 const fields=new Map(definition.fields.map(field=>[field.key,field]));
 if(Object.keys(props).some(key=>!fields.has(key)))throw new Error('Unknown actual CVA property');
 if(items!==undefined&&Object.hasOwn(props,'items'))throw new Error('Supply items in one place');
 const actual=Object.fromEntries(Object.entries(props).map(([key,value])=>[key,value??(fields.get(key).kind==='items'?[]:'')]));
 if(items!==undefined)actual.items=items;
 if(actual.items!==undefined){
  if(!Array.isArray(actual.items)||actual.items.length>24)throw new Error('Split module items into batches of at most 24');
  for(const entry of actual.items)plain(entry,'item');
 }
 const count=actual.items?.length??0,extras=approvedHTML(itemExtras,count,'itemExtras'),titles=approvedHTML(itemTitles,count,'itemTitles'),bodies=approvedHTML(itemBodies,count,'itemBodies');
 context.__input=JSON.stringify({id,type,variant,orientation,profile,actual});
 const result=new vm.Script(`
  const input=JSON.parse(__input);
  const definition=CVA_MODULES.definitions.find(value=>value.type===input.type);
  const block=CVA_MODULES.create(input.type,input.id);
  block.props=Object.fromEntries(definition.fields.map(field=>[field.key,field.kind==='items'?[]:'']));
  Object.assign(block.props,input.actual);
  block.variant=input.variant;block.orientation=input.orientation;
  const doc=CVA_MODULES.normalizeDocument({schema:'cva.page.v2',title:'',description:'',profile:input.profile,modules:[block]});
  ({doc,html:CVA_RENDERER.renderBlock(doc.modules[0],{profile:doc.profile,firstId:doc.modules[0].id,nextId:doc.modules[0].id})});
 `).runInContext(context);
 const doc=JSON.parse(JSON.stringify(result.doc)),block=doc.modules[0];
 let html=result.html.replace(/<h1\b/g,'<h2').replace(/<\/h1>/g,'</h2>');
 // Authoring hints describe the studio, so omit them from the reader fragment.
 html=html.replace(/<p class="(?:cva-empty|sc-empty|sc-image-empty|sc-fallback)">[^<]*<\/p>/g,'');
 if(block.type==='scene-composition'&&!block.props.relationLabel&&!block.props.caption)html=html.replace(/<footer class="sc-semantic-footer">[\s\S]*?<\/footer>/,'');
 else if(block.type==='scene-composition'&&!block.props.relationLabel)html=html.replace(/<p class="sc-relation-label">[\s\S]*?<\/p>/,'');
 html=annotateItems(html,block,extras,titles,bodies);
 html=annotateMedia(html,registry);
 const json=value=>JSON.stringify(value).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
 return '<div class="cva-page cva-reader-fragment" data-cva data-cva-profile="'+escape(doc.profile)+'">'+html+
  '<script type="application/json" data-cva-model data-pagefind-ignore>'+json(doc)+'</script>'+
  (registry.length?'<script type="application/json" data-cva-media data-pagefind-ignore>'+json(registry)+'</script>':'')+'</div>';
}
