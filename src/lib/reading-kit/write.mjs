import {mkdir,writeFile} from 'node:fs/promises';import path from 'node:path';
export async function writeReadingGraph(graph,directory){
 await mkdir(path.join(directory,'sources'),{recursive:true});const shards=Array.from({length:16},()=>[]);const sources=graph.sources.map((source,i)=>{const shard=i%16;shards[shard].push(source);return {id:source.id,title:source.title,kind:source.kind,url:source.url,blockCount:source.blocks.length,blockIndex:'sources/'+shard.toString(16)+'.json'};});
 for(const [i,records] of shards.entries())await writeFile(path.join(directory,'sources',i.toString(16)+'.json'),JSON.stringify({schema:graph.schema,game:graph.game,sources:records}));
 await writeFile(path.join(directory,'graph.json'),JSON.stringify({...graph,sources}));
}
