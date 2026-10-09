/** Search matching only; the displayed query keeps the reader's original spelling. */
export const normalizeDirectoryText = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/gu, ' ').trim();

const defaultPageSize = value => Number.isSafeInteger(value) && value > 0 ? value : 24;
const positiveLimit = (value, fallback) => {
  const text = String(value ?? '');
  if (!/^[1-9]\d*$/u.test(text)) return fallback;
  const number = Number(text);
  return Number.isSafeInteger(number) ? number : fallback;
};

/** Group existence and the available item count belong to the consuming directory. */
export function readDirectoryState(search, options = {}) {
  const {axis = '', axes = [], queryKey = 'q', groupKey = 'group', limitKey = 'limit', axisKey = '', defaultLimit = 24} = options;
  const params = new URLSearchParams(search);
  const requestedAxis = axisKey ? params.get(axisKey) : null;
  return {
    axis: requestedAxis !== null && axes.includes(requestedAxis) ? requestedAxis : axis,
    query: queryKey ? (params.get(queryKey) || '').trim() : '',
    group: groupKey ? (params.get(groupKey) || '').trim() : '',
    limit: positiveLimit(limitKey ? params.get(limitKey) : null, defaultPageSize(defaultLimit)),
  };
}

/** Return a new URL, retaining unrelated directory state, return URLs and the anchor. */
export function writeDirectoryState(url, state, options = {}) {
  const {queryKey = 'q', groupKey = 'group', limitKey = 'limit', axisKey = '', defaultLimit = 24} = options;
  const next = new URL(url.href);
  const put = (key, value) => {
    if (!key) return;
    if (value) next.searchParams.set(key, value);
    else next.searchParams.delete(key);
  };
  put(queryKey, String(state.query ?? '').trim());
  put(groupKey, String(state.group ?? '').trim());
  put(axisKey, String(state.axis ?? ''));
  const limit = positiveLimit(state.limit, defaultPageSize(defaultLimit));
  put(limitKey, limit === defaultPageSize(defaultLimit) ? '' : String(limit));
  return next;
}
