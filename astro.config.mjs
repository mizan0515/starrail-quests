import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import {canonicalPageUrl} from './src/lib/seo.mjs';
import {buildReadingGraph} from './tools/build_reading_graph.mjs';
await buildReadingGraph();

const base=process.env.SITE_BASE || '/starrail-quests';
const aliases=JSON.parse(fs.readFileSync(new URL('./data/aliases.json',import.meta.url),'utf8'));
const sitemapPage=(url)=>{
  const pathname=decodeURIComponent(new URL(url).pathname);
  const relative=pathname.slice(base.replace(/\/$/,'').length).replace(/^\//,'').replace(/\.html$/,'');
  return !relative.startsWith('alias/') && relative!=='시작' && !['404','500'].includes(relative) && !(relative.startsWith('문서/') && Object.hasOwn(aliases,relative.slice('문서/'.length)));
};
// Starlight adds the configured base to sidebar links itself.
const link=(path)=>`/${path}`;
export default defineConfig({
  site:'https://mizan0515.github.io',base,trailingSlash:'never',
  build:{format:'file'},
  vite:{ssr:{external:['satteri']}},
  integrations:[sitemap({filter:sitemapPage,serialize:item=>({...item,url:canonicalPageUrl(item.url)})}),starlight({
    title:'스타레일 · 별의 기록',description:'스타레일 한국어 임무와 설정을 맥락으로 연결한 자료집',
    defaultLocale:'root',locales:{root:{label:'한국어',lang:'ko'}},
    customCss:['./src/styles/library.css','./src/styles/context.css','./src/styles/complete-library.css','./src/styles/reading-system.css','./src/lib/reading-kit/reading.css','./src/styles/universe.css','./src/styles/mission-reader.css','./src/lib/reading-kit/reader.css','./src/lib/reading-kit/search-dialog.css','./src/lib/reading-kit/cva.css'],
    tableOfContents:{minHeadingLevel:2,maxHeadingLevel:2},
    sidebar:[
      {label:'자료집',items:[{label:'이야기 찾아보기',link:link('index.html')},{label:'설정집 · 연결해서 읽기',link:link('설정집.html')}]},
      {label:'설정을 읽는 관점',items:[{label:'지역 · 역사와 사건',link:link('관점/region.html')},{label:'인물 · 행적과 관계',link:link('관점/person.html')},{label:'세계관 · 법칙과 사례',link:link('관점/concept.html')},{label:'에이언즈 · 운명의 길',link:link('관점/aeon.html')}]},
      {label:'임무 종류',items:[['main','개척 임무'],['continuance','개척 후문'],['companion','동행 임무'],['adventure','모험 임무'],['daily','일일 임무']].map(([k,label])=>({label,link:link(`quests/${k}.html`)}))},
      {label:'버전으로 찾기',items:[{label:'버전별 임무 전체',link:link('versions/index.html')},...['4.5','4.4','4.3','4.2','4.1','4.0'].map(v=>({label:v+' 버전',link:link(`versions/${v}.html`)})),{label:'3.x · 2.x',collapsed:true,items:[...['3.8','3.7','3.6','3.5','3.4','3.3','3.2','3.1','3.0','2.7'].map(v=>({label:v+' 버전',link:link(`versions/${v}.html`)})),{label:'2.6 및 이전 · 미확인',link:link('versions/early.html')}]}]},
      {label:'설정의 연결',collapsed:true,items:[['paths-and-factions','에이언즈와 파벌'],['xianzhou-immortality','선주 · 영생과 마각'],['borisin-and-foxians','보리인과 여우족'],['belobog-preservation','벨로보그 · 보존의 의미'],['penacony-memory','페나코니 · 꿈과 기록'],['amphoreus-myth-and-life','앰포리어스 · 신화와 일상'],['herta-life-and-knowledge','헤르타 · 생명과 지식']].map(([k,label])=>({label,link:link(`설정/${k}.html`)}))},
      {label:'읽기 안내',items:[{label:'수록 범위와 출처',link:link('자료안내.html')}]}
    ],
    components:{Sidebar:'./src/components/Sidebar.astro',Footer:'./src/components/Footer.astro',Search:'./src/components/Search.astro',Head:'./src/components/Head.astro'},
    pagination:false,lastUpdated:false
  })]
});
