/** Shared HTML boundaries; game adapters retain source text and identifiers. */
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kinds=new Set(['dialogue','choice','gap','branch','original']);
export function readerAttributes({variant='dialogue',className='',id='',label=''}={}){
 return {class:['rw-reader','not-content','cva-page','cva-reader-frame',className].filter(Boolean).join(' '),'data-cva':true,'data-cva-profile':'forma','data-reading-template':'reader','data-reading-variant':variant,...(id?{id}:{}),...(label?{'aria-label':label}:{})};
}
export function rowAttributes(kind='original'){
 if(!kinds.has(kind))throw Error('Unknown source row kind: '+kind);
 return {class:'rw-source-row','data-reading-template':'row','data-reading-kind':kind};
}
export function disclosureAttributes({className='',id='',open=false,attributes={}}={}){
 for(const key of Object.keys(attributes))if(!/^(?:data-[a-z-]+|aria-[a-z-]+)$/.test(key))throw Error('Unsupported disclosure attribute');
 return {...attributes,class:['rw-disclosure','not-content',className].filter(Boolean).join(' '),'data-reading-template':'disclosure',...(id?{id}:{}),...(open?{open:true}:{})};
}
export function htmlAttributes(attributes){return Object.entries(attributes).map(([k,v])=>v===true?k:`${k}="${escape(v)}"`).join(' ');}
export function readerFrame(body,options={}){return `<div ${htmlAttributes(readerAttributes(options))}>${body}</div>`;}
export function readerDisclosure(summary,body,options={}){return `<details ${htmlAttributes(disclosureAttributes(options))}><summary>${escape(summary)}</summary>${body}</details>`;}
export function sourceLinkAttributes({className='',id='',reading=false,variant='cta'}={}){
 if(typeof reading!=='boolean'||!['cta','inline'].includes(variant))throw Error('Invalid source link options');
 return {class:['rw-source-link',className].filter(Boolean).join(' '),'data-reading-template':'source-link','data-source-link-variant':variant,...(id?{id}:{}),...(reading?{'data-reading-link':true}:{})};
}
export function sourceLink(url,label,options={}){
 const value=String(url);
 if(!/^(?:https?:\/\/|\/(?!\/)|#)/.test(value)||/[\u0000-\u0020\\]/.test(value))throw Error('Unsupported source URL');
 if(options.reading&&!/^(?:\/(?!\/)|#)/.test(value))throw Error('Reading source link must be local');
 return `<a href="${escape(value)}" ${htmlAttributes(sourceLinkAttributes(options))}>${escape(label)}</a>`;
}
