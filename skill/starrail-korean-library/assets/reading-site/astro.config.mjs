import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const base=process.env.SITE_BASE || '/';
// Starlight adds the configured base to sidebar links itself.
const link=(path)=>`/${path}`;
export default defineConfig({
  site:'https://mizan0515.github.io',base,trailingSlash:'never',
  build:{format:'file'},
  vite:{ssr:{external:['satteri']}},
  integrations:[starlight({
    title:'스타레일 · 별의 기록',description:'스타레일 한국어 임무와 설정을 맥락으로 연결한 자료집',
    defaultLocale:'root',locales:{root:{label:'한국어',lang:'ko'}},
    customCss:['./src/styles/library.css'],
    tableOfContents:{minHeadingLevel:2,maxHeadingLevel:2},
    sidebar:[
      {label:'자료집',items:[{label:'이야기 찾아보기',link:link('index.html')},{label:'설정집 · 연결해서 읽기',link:link('설정집.html')}]},
      {label:'임무 종류',items:[['main','개척 임무'],['continuance','개척 후문'],['companion','동행 임무'],['adventure','모험 임무'],['daily','일일 임무']].map(([k,label])=>({label,link:link(`quests/${k}.html`)}))},
      {label:'설정의 연결',items:[['paths-and-factions','에이언즈와 파벌'],['xianzhou-immortality','선주 · 영생과 마각'],['borisin-and-foxians','보리인과 여우족'],['belobog-preservation','벨로보그 · 보존의 의미'],['penacony-memory','페나코니 · 꿈과 기록'],['amphoreus-myth-and-life','앰포리어스 · 신화와 일상'],['herta-life-and-knowledge','헤르타 · 생명과 지식']].map(([k,label])=>({label,link:link(`설정/${k}.html`)}))},
      {label:'읽기 안내',items:[{label:'수록 범위와 출처',link:link('자료안내.html')}]}
    ],
    components:{Footer:'./src/components/Footer.astro'},
    pagination:false,lastUpdated:false
  })]
});
