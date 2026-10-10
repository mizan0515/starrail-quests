import test from 'node:test';import assert from 'node:assert/strict';
import {validateStrikeRanges,escapeSourceRun} from './source-strikes.mjs';
test('semantic strike across annotated runs preserves all Korean text and escaping',()=>{
 const text='첫 줄 <기록> 다음 줄',ranges=[[4,8]];validateStrikeRanges(text,ranges);
 assert.equal(escapeSourceRun('첫 줄 <기',0,ranges)+escapeSourceRun('록> 다음 줄',6,ranges),'첫 줄 <s>&lt;기</s><s>록&gt;</s> 다음 줄');
 assert.equal(escapeSourceRun('무삭제 & 원문',0,[]),'무삭제 &amp; 원문');
});
test('source interval offsets use code points and keep supplementary characters',()=>{
 const text='😀기록&끝';validateStrikeRanges(text,[[1,3]]);assert.equal(escapeSourceRun(text,0,[[1,3]]),'😀<s>기록</s>&amp;끝');
});
test('unsafe and overlapping intervals fail; source markup always escapes',()=>{
 for(const ranges of [[[0,100]],[[2,1]],[[0,2],[1,3]],[[0.1,2]]])assert.throws(()=>validateStrikeRanges('기록문',ranges));
 assert.equal(escapeSourceRun('<script>alert(1)</script>',0,[[0,8]]),'<s>&lt;script&gt;</s>alert(1)&lt;/script&gt;');
});
