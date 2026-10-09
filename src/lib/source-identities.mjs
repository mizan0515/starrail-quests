// Reader labels are separate from the preserved table's missing name field.
export function applySourceIdentities(dataset, identities = []) {
  const byId = new Map();
  for (const identity of identities) {
    if (byId.has(identity.id)) throw Error('Duplicate source identity: ' + identity.id);
    const entry = dataset.entries.find(e => e.id === identity.id);
    const stories = entry?.stories.filter(s => s.story_id === identity.storyId) || [];
    const story = stories[0];
    if (!entry || entry.axis !== 'person' || entry.source !== 'StoryAtlas' ||
        entry.nameVerified || stories.length !== 1 ||
        typeof identity.name !== 'string' || !identity.name.trim() ||
        !Number.isSafeInteger(identity.storyId) || identity.storyId < 1 ||
        typeof identity.hash !== 'string' || !/^\d+$/.test(identity.hash) ||
        typeof identity.quote !== 'string' || String(story.hash) !== identity.hash ||
        !identity.quote.startsWith(identity.name + ',') || !story.text.includes(identity.quote)) {
      throw Error('Unverified source identity: ' + identity.id);
    }
    byId.set(identity.id, identity);
  }
  return {...dataset, entries: dataset.entries.map(entry => {
    const identity = byId.get(entry.id);
    return identity ? {...entry, sourceName: entry.name, name: identity.name,
      nameVerified: true, nameEvidence: identity, group: '본문에 이름이 명시된 기록'} : entry;
  })};
}
