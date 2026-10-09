"""Cross-language regression: consume the real C# report/collector output via CLI."""
from pathlib import Path
import copy, json, subprocess, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import candidates

def main():
    snapshot, out = map(Path, sys.argv[1:])
    dictionary = candidates.read(candidates.ROOT/'translations/zh-CN.json')
    run = lambda *args: subprocess.run([sys.executable, str(candidates.ROOT/'tools/candidates.py'), *map(str,args)], check=True, capture_output=True, text=True)
    review_path = out/'message-review.json'
    run('export', snapshot, '--output', review_path)
    review = candidates.read(review_path)
    assert {r['reason'] for r in review['candidates']} == {'unknown_resource','unknown_message_list','message_list_mismatch','unbound_target','ambiguous_target','missing_translation','bound_source_mismatch','unknown_id'}
    missing = next(r for r in review['candidates'] if r['reason']=='missing_translation')
    assert missing['review']=='translation' and '\r\n' in missing['source']
    assert all(r['review']=='binding' and r['target_hint'] is None for r in review['candidates'] if r is not missing)
    entry = next(e for e in dictionary['entries'] if e['id']==missing['id'])
    missing.update(approved=True, translation=entry['translation']+'测试')
    candidates.write_new(out/'approved.json', review)
    run('merge', out/'approved.json', '--output', out/'merged.json')
    expected=copy.deepcopy(dictionary)
    next(e for e in expected['entries'] if e['id']==missing['id'])['translation']=missing['translation']
    assert candidates.read(out/'merged.json')==expected
    for row in review['candidates']:
        if row is missing: continue
        row.update(approved=True, translation='测试')
        try: candidates.merge(review, dictionary)
        except ValueError: pass
        else: raise AssertionError('Unsafe status merged: '+row['reason'])
        row['approved']=False
    print('PASS C# formal statuses/CRLF -> actual collector snapshot -> Python CLI export -> guarded merge; every unbound status rejected.')

if __name__=='__main__':main()
