import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const directory=path.dirname(fileURLToPath(import.meta.url));
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
for(const [name,expected] of Object.entries(manifest.files)){
 const actual=createHash('sha256').update(fs.readFileSync(path.join(directory,name),'utf8').replace(/\r\n/g,'\n')).digest('hex');
 if(actual!==expected)throw Error('Shared reading template differs: '+name);
}
console.log(JSON.stringify({sharedReadingKit:'PASS',version:manifest.version,files:Object.keys(manifest.files).length}));
