"""Verify the publisher boundary without removing local validation inputs."""
import json,re,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else 'dist').resolve()
graph=root/'reading-data/graph.json'
if not graph.is_file():raise SystemExit('Full local validation graph is missing')
data=json.loads(graph.read_text(encoding='utf8'))
for source in data['sources']:
 if not (root/'reading-data'/source['blockIndex']).is_file():raise SystemExit('Local source block index missing: '+source['id'])
errors=[]
whole=json.loads((root/'reading-catalog.json').read_text(encoding='utf8'))
categories={row['category'] for row in whole}
for category in categories:
 rows=json.loads((root/'reading-catalog'/(category+'.json')).read_text(encoding='utf8'))
 if rows!=[row for row in whole if row['category']==category]:errors.append('Catalog partition differs: '+category)
for file in root.rglob('*'):
 if file.suffix not in {'.html','.js','.mjs'}:continue
 text=file.read_text(encoding='utf8')
 # Both static attributes and literal fetch/import endpoints must remain independent.
 if re.search(r"""(?:href|src)\s*=\s*["'][^"']*(?:^|/)reading-data/|(?:fetch|import)\s*\(\s*["'][^"']*reading-data/""",text):
  errors.append(file.relative_to(root).as_posix())
result={'status':'FAIL' if errors else 'PASS','catalogEntries':len(whole),'catalogCategories':len(categories),'localSources':len(data['sources']),'localFullGraphRetained':True,'readerDependenciesOnExcludedData':errors}
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(bool(errors))
