import {createReadingKit,escapeHtml as E} from './reading-kit/render.mjs';

// Keep the canonical CVA card renderer and its 24-item batching. The cursor
// follows the complete rendered order, rather than each batch's local index.
export function renderDirectoryGroup(items,group,scope,axis=''){
 const ids=new Set();
 for(const item of items){
  if(!item.id||ids.has(item.id)||!item.name||!item.url)throw Error('Invalid directory subject '+item.id);
  ids.add(item.id);
 }
 let cursor=0;
 const html=createReadingKit().directory(items).replace(/<article\b[^>]*data-cva-item-index="\d+"[^>]*>/g,opening=>{
  const item=items[cursor++];
  if(!item)throw Error('Directory renderer emitted extra subjects');
  return opening.slice(0,-1)+` data-directory-entry="${E(item.id)}" data-directory-axis="${E(item.axis||'')}" data-directory-group="${E(group)}" data-directory-search="${E([item.name,item.kind,item.searchText||item.summary].join(' '))}"${axis&&axis!==item.axis?' hidden':''}>`;
 });
 if(cursor!==items.length)throw Error('Directory renderer omitted subjects');
 // Every title gets an addressable anchor for both explicit return and Back.
 let title=0;
 return html.replace(/<a data-reading-link href=/g,()=>`<a id="${E(scope+'-entry-'+items[title++].id)}" data-reading-link href=`).replaceAll('<h3 class="cva-item-title">','<h4 class="cva-item-title">').replaceAll('</h3>','</h4>');
}
