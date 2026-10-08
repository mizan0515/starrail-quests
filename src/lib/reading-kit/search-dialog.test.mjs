import test from 'node:test';
import assert from 'node:assert/strict';
import {searchClickAction} from './search-dialog.mjs';

test('search controls keep the dialog open, including detached pagination controls', () => {
  const frame = {}, button = {tagName: 'BUTTON'}, form = {tagName: 'FORM'};
  assert.equal(searchClickAction([button, form, frame], frame), 'control');
  assert.equal(searchClickAction([{tagName: 'INPUT'}, frame], frame), 'control');
  assert.equal(searchClickAction([{tagName: 'SPAN'}, button, frame], frame), 'control');
});
test('only an actual link in the dialog propagation path ends search', () => {
  const frame = {}, link = {tagName: 'A', hasAttribute: key => key === 'href'};
  assert.equal(searchClickAction([{tagName: 'MARK'}, link, frame], frame), 'navigate');
  assert.equal(searchClickAction([{tagName: 'A', hasAttribute: () => false}, frame], frame), 'control');
  assert.equal(searchClickAction([link, {}], frame), 'outside');
});
