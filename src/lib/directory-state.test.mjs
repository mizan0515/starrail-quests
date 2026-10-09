import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeDirectoryText, readDirectoryState, writeDirectoryState} from './directory-state.mjs';

const explorerKeys = {axis: 'concept', axes: ['region', 'person', 'concept', 'aeon'], axisKey: 'view', queryKey: 'find', groupKey: 'group', limitKey: 'entityLimit', defaultLimit: 24};
const itemKeys = {queryKey: 'item', groupKey: 'collection', limitKey: 'itemLimit', defaultLimit: 24};
const dialogueKeys = {queryKey: 'dialogueQuery', groupKey: 'dialogueSpeaker', limitKey: 'dialogueLimit', defaultLimit: 24};

test('matching normalizes Korean composition, full-width text, case and whitespace without changing a displayed query', () => {
  const query = '  헤르타　ＡＢＣ\n  기억  ';
  assert.equal(normalizeDirectoryText(query), '헤르타 abc 기억');
  const state = readDirectoryState('?find=' + encodeURIComponent(query), explorerKeys);
  assert.equal(state.query, query.trim());
  assert.deepEqual(normalizeDirectoryText(state.query).split(' '), ['헤르타', 'abc', '기억']);
  assert.equal(normalizeDirectoryText(null), '');
});

test('an unknown or empty axis cannot widen a fixed concept directory to all axes', () => {
  for (const view of ['bogus', '', 'PERSON', ' person ']) {
    const state = readDirectoryState('?view=' + encodeURIComponent(view), explorerKeys);
    assert.equal(state.axis, 'concept');
  }
  assert.equal(readDirectoryState('?view=person', explorerKeys).axis, 'person');
  assert.equal(readDirectoryState('?view=person', itemKeys).axis, '');
  const allKeys = {...explorerKeys, axis: '', axes: ['', ...explorerKeys.axes]};
  assert.equal(readDirectoryState('?view=', allKeys).axis, '');
});

test('malformed, fractional, unsafe and zero limits use the directory default', () => {
  for (const value of ['', '0', '-24', '24.5', '1e3', '0x30', 'Infinity', 'NaN', '024', '48rows', ' 48 ', '9007199254740992']) {
    assert.equal(readDirectoryState('?entityLimit=' + encodeURIComponent(value), explorerKeys).limit, 24, value);
  }
  assert.equal(readDirectoryState('?entityLimit=1', explorerKeys).limit, 1);
  assert.equal(readDirectoryState('?entityLimit=72', explorerKeys).limit, 72);
  assert.equal(readDirectoryState('', {defaultLimit: 12}).limit, 12);
  assert.equal(readDirectoryState('', {defaultLimit: 0}).limit, 24);
});

test('48 and 72 visible results survive leaving a filtered directory and returning to its saved URL', () => {
  const entries = Array.from({length: 80}, (_, i) => ({id: 'source-' + i, text: '헤르타 기록 ' + i}));
  for (const limit of [48, 72]) {
    const selected = entries[limit - 1];
    const original = new URL('https://example.test/settings.html?from=%2Fquest.html#atlas');
    const saved = writeDirectoryState(original, {axis: 'concept', query: '헤르타 기록', group: 'herta', limit}, explorerKeys);
    const restored = readDirectoryState(saved.search, explorerKeys);
    const tokens = normalizeDirectoryText(restored.query).split(' ');
    const visible = entries.filter(entry => tokens.every(token => normalizeDirectoryText(entry.text).includes(token))).slice(0, restored.limit);
    assert.equal(visible.length, limit);
    assert.equal(visible.at(-1).id, selected.id);
    assert.equal(restored.group, 'herta');
    assert.equal(saved.hash, '#atlas');
    assert.equal(saved.searchParams.get('from'), '/quest.html');
    assert.equal(original.searchParams.has('entityLimit'), false);
  }
});

test('independent explorer, item, dialogue and universe keys preserve one another on a shared page', () => {
  let url = new URL('https://example.test/library.html#source-a');
  url = writeDirectoryState(url, {axis: 'person', query: '아브', group: 'people', limit: 48}, explorerKeys);
  url = writeDirectoryState(url, {query: '세계', group: 'curios', limit: 72}, itemKeys);
  url = writeDirectoryState(url, {query: '실험', group: '헤르타', limit: 48}, dialogueKeys);
  const universeKeys = {queryKey: 'textQuery', groupKey: 'textKind', limitKey: 'textLimit', defaultLimit: 12};
  url = writeDirectoryState(url, {query: '질서', group: 'formula', limit: 36}, universeKeys);
  assert.deepEqual(readDirectoryState(url.search, explorerKeys), {axis: 'person', query: '아브', group: 'people', limit: 48});
  assert.deepEqual(readDirectoryState(url.search, itemKeys), {axis: '', query: '세계', group: 'curios', limit: 72});
  assert.deepEqual(readDirectoryState(url.search, dialogueKeys), {axis: '', query: '실험', group: '헤르타', limit: 48});
  assert.deepEqual(readDirectoryState(url.search, universeKeys), {axis: '', query: '질서', group: 'formula', limit: 36});
  assert.equal(url.hash, '#source-a');
});

test('reset removes only its own empty filters and default limit, retaining the axis and adjacent directory', () => {
  const original = new URL('https://example.test/library.html?view=person&find=old&group=people&entityLimit=72&item=기물&itemLimit=48#people');
  const reset = writeDirectoryState(original, {axis: 'person', query: ' \n ', group: '', limit: 24}, explorerKeys);
  assert.equal(reset.searchParams.get('view'), 'person');
  for (const key of ['find', 'group', 'entityLimit']) assert.equal(reset.searchParams.has(key), false);
  assert.equal(reset.searchParams.get('item'), '기물');
  assert.equal(reset.searchParams.get('itemLimit'), '48');
  assert.equal(original.searchParams.get('entityLimit'), '72');
  assert.equal(reset.hash, '#people');
});

test('reserved characters in literal original names round-trip as URL data', () => {
  const query = '「지니어스」 & <기억> # 100% +';
  const url = writeDirectoryState(new URL('https://example.test/?retained=yes'), {query, group: 'A/B?C', limit: 36}, {defaultLimit: 12});
  assert.equal(readDirectoryState(url.search, {defaultLimit: 12}).query, query);
  assert.equal(readDirectoryState(url.search, {defaultLimit: 12}).group, 'A/B?C');
  assert.equal(url.searchParams.get('retained'), 'yes');
});

test('semantic group validation and total-count clamping remain with the consuming directory', () => {
  const state = readDirectoryState('?view=person&group=retired-group&entityLimit=999', explorerKeys);
  assert.equal(state.axis, 'person');
  assert.equal(state.group, 'retired-group');
  assert.equal(state.limit, 999);
  const availableGroups = new Set(['characters', 'introductions']);
  const corrected = {...state, group: availableGroups.has(state.group) ? state.group : '', limit: Math.min(state.limit, 88)};
  assert.deepEqual(readDirectoryState(writeDirectoryState(new URL('https://example.test/people.html'), corrected, explorerKeys).search, explorerKeys), {axis: 'person', query: '', group: '', limit: 88});
});
