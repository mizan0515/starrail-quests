// Individual readers select their comparison explicitly. A broad essay topic
// alone does not establish that every comparison belongs in that reader.
export function atlasComparison(atlas, node, topic) {
  if (!node) {
    const comparison = atlas.comparisons[topic];
    if (!comparison) throw Error('Unknown comparison topic: ' + topic);
    return comparison;
  }
  if (node.comparison) {
    if (node.comparisonTopic) throw Error('Ambiguous comparison scope: ' + node.id);
    return node.comparison;
  }
  const comparison = node.comparisonTopic && atlas.comparisons[node.comparisonTopic];
  if (!comparison) throw Error('Unspecified comparison scope: ' + node.id);
  return comparison;
}

export function comparisonReaderNode(atlas, node, topic) {
  if (node) return node;
  const owner = atlas.nodes.find(n => n.comparisonTopic === topic);
  if (!owner) throw Error('No explicit topic comparison owner: ' + topic);
  return owner;
}
