import test from 'node:test';
import assert from 'node:assert/strict';
import {validateLayout} from './layout-qa.mjs';
const rect=(left,top,width,height)=>({left,top,width,height,right:left+width,bottom:top+height});
function fixture(){return {document:{scrollWidth:390,clientWidth:390},elements:[
 {id:'proof',role:'summary',rect:rect(16,100,358,44),parentRect:rect(16,100,358,100),computed:{marginInlineStart:0,listStyleType:'disclosure-closed',listStylePosition:'inside',beforeContent:'none',beforeDisplay:'none',afterContent:'none',afterDisplay:'none'}},
 {id:'speaker',role:'control',rect:rect(16,220,170,46),parentRect:rect(16,220,358,120),computed:{minWidth:128}},
 {id:'long-korean-source',role:'body',rect:rect(16,350,358,220),parentRect:rect(16,350,358,260)},
 {id:'row',role:'row',rect:rect(16,350,358,260),parentRect:rect(16,350,358,260)}]};}
const errors=s=>validateLayout(s).errors.map(e=>e.error);
test('contained reader geometry passes across disclosure states',()=>{const s=fixture();assert.equal(validateLayout(s).status,'PASS');s.elements[0].computed.listStyleType='disclosure-open';assert.equal(validateLayout(s).status,'PASS');});
test('negative framework margin and outside native marker are rejected',()=>{const s=fixture(),e=s.elements[0];e.rect=rect(8,100,366,44);e.computed.marginInlineStart=-8;e.computed.listStylePosition='outside';assert.ok(errors(s).includes('reader element exceeds containing box'));assert.ok(errors(s).includes('framework negative summary margin'));assert.ok(errors(s).includes('native disclosure marker missing or outside'));});
test('additional CSS arrow with native disclosure marker is rejected',()=>{const s=fixture();s.elements[0].computed.beforeContent='"›"';s.elements[0].computed.beforeDisplay='inline-block';assert.ok(errors(s).includes('duplicate disclosure pseudo arrow'));s.elements[0].computed.beforeContent='""';assert.ok(errors(s).includes('duplicate disclosure pseudo arrow'));});
test('narrow controls and long source overflow are rejected',()=>{const s=fixture();s.elements[1].rect=rect(16,220,400,32);s.elements[1].computed.minWidth=430;s.elements[2].rect=rect(16,350,410,220);s.document.scrollWidth=426;const e=errors(s);for(const error of ['document horizontal overflow','reader element exceeds containing box','interactive target height below 44px','control minimum width exceeds available box'])assert.ok(e.includes(error));});
test('missing measurements cannot establish layout success',()=>{assert.equal(validateLayout({}).status,'FAIL');const s=fixture();delete s.elements[0].computed.beforeContent;assert.ok(errors(s).includes('disclosure pseudo marker measurement missing'));s.elements[2].rect.width=NaN;assert.ok(errors(s).includes('element geometry missing'));});

test('grid child inherited Markdown margin is rejected by template invariant',()=>{const s=fixture();s.elements[1].expectedMarginTop=0;s.elements[1].computed.marginTop=18;assert.ok(errors(s).includes('framework block margin differs from template'));s.elements[1].computed.marginTop=0;assert.equal(validateLayout(s).status,'PASS');});
