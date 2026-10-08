/** Keep search controls inside the dialog; only result links finish the search. */
export function searchClickAction(path, frame) {
  if (!path.includes(frame)) return 'outside';
  return path.some(node => node?.tagName === 'A' && node.hasAttribute?.('href')) ? 'navigate' : 'control';
}

export function installSearchDialog(root) {
  if (!root || root.dataset.readingSearch) return;
  const frame = root.querySelector('.dialog-frame');
  const dialog = root.querySelector('dialog');
  const opener = root.querySelector('[data-open-modal]');
  const closer = root.querySelector('[data-close-modal]');
  if (!frame || !dialog || !opener || !closer) return;
  root.dataset.readingSearch = 'true';
  frame.dataset.readingTemplate = 'search-dialog';
  closer.textContent = '닫기';
  closer.setAttribute('aria-label', '검색 닫기');
  opener.setAttribute('aria-label', '검색');
  frame.addEventListener('click', event => {
    const path = event.composedPath();
    const action = searchClickAction(path, frame);
    if (action === 'outside') return;
    // Pagefind can update its DOM before the window-level outside-click listener runs.
    // The original propagation path identifies the control even after an update.
    if (action === 'navigate') dialog.close();
    if (path.some(node => node?.classList?.contains('pagefind-ui__search-clear'))) root.querySelector('.pagefind-ui__search-input')?.focus();
    event.stopPropagation();
  });
  dialog.addEventListener('close', () => {
    if (document.activeElement === document.body || frame.contains(document.activeElement)) opener.focus({preventScroll: true});
  });
}
