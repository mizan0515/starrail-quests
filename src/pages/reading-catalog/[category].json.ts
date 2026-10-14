import {catalog} from '../../lib/data';
export function getStaticPaths(){
 return [...new Set(catalog.map(d=>d.category))].map(category=>({params:{category},props:{rows:catalog.filter(d=>d.category===category)}}));
}
export function GET({props}){return new Response(JSON.stringify(props.rows),{headers:{'Content-Type':'application/json; charset=utf-8'}});}
