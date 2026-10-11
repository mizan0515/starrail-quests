import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export function publicationIntegration(base){
 return {name:'starrail-publication',hooks:{'astro:build:done':({dir})=>{
  // The full local gate validates the unmodified renderer first, then runs
  // the same optimizer and checks the actual published original passages.
  if(process.env.STARRAIL_VALIDATE_UNOPTIMIZED==='1')return;
  const result=spawnSync('python',['-B','-X','utf8','tools/optimize_publication.py','--root',fileURLToPath(dir),'--base',base],{cwd:fileURLToPath(new URL('../',import.meta.url)),stdio:'inherit',windowsHide:true});
  if(result.error)throw result.error;
  if(result.status!==0)throw Error('Publication size or exact UI reconstruction failed');
 }}};
}
