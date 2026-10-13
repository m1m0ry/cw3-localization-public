"""Real runtime output-template observations remain reviewable translations."""
from pathlib import Path
import copy,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import candidates
snapshot,out=map(Path,sys.argv[1:]);dictionary=candidates.read(candidates.ROOT/'translations/zh-CN.json')
review=candidates.export([snapshot],dictionary)
expected={e['id']:e for e in dictionary['entries'] if e['target']['kind']=='crpl_output'}
assert {r['id'] for r in review['candidates']}==set(expected)
for row in review['candidates']:
    entry=expected[row['id']]
    assert row['review']=='translation' and row['target_hint']==entry['target'] and row['count']==2
    row.update(approved=True,translation=entry['translation']+'测试')
merged,count=candidates.merge(review,dictionary);assert count==len(expected)
for before,after in zip(dictionary['entries'],merged['entries']):
    assert after==dict(before,translation=before['translation']+'测试') if before['id'] in expected else after==before
# A number-expanded source cannot silently become an adopted template.
bad=copy.deepcopy(review);row=next(r for r in bad['candidates'] if '{0}' in r['source']);row['source']=row['source'].replace('{0}','12.5');row['key']=candidates.key(row)
try:candidates.merge(bad,dictionary)
except ValueError:pass
else:raise AssertionError('Expanded output must require binding review')
print('PASS actual CRPL snapshot -> template review and exact approved merge; expanded source rejected')
