"""Local candidate review export/merge. Never creates bindings or calls a service."""
from pathlib import Path
import argparse, copy, hashlib, json, re
from translation_contract import loads
ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('source', 'kind', 'scene', 'context', 'reason', 'id')
REASONS = {'missing_translation', 'bound_source_mismatch', 'unknown_id', 'unbound_source', 'unbound_context', 'unbound_script_literal', 'unknown_resource', 'unknown_message_list', 'unbound_target', 'ambiguous_target', 'message_list_mismatch'}

def read(path):
    path = Path(path)
    if path.stat().st_size > 4_000_000:
        raise ValueError('Input exceeds 4 MB')
    return loads(path.read_text(encoding='utf8'))

def write_new(path, value):
    with Path(path).open('x', encoding='utf8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')

def key(row):
    return hashlib.sha256('\0'.join(row[field] for field in FIELDS).encode()).hexdigest()

def source_matches(row, entry):
    source = row['source']
    if row['kind'] == 'xml_message' and entry['target']['kind'] == 'xml_text':
        source = source.replace('\r\n', '\n')
    return entry['source'] == source

def export(paths, dictionary):
    entries = {e['id']: e for e in dictionary['entries']}
    observations = {}
    for path in paths:
        doc = read(path)
        if doc.get('format') != 1 or not isinstance(doc.get('session'), str) or len(doc['session']) != 32 or len(doc.get('candidates', [])) > 256:
            raise ValueError('Not a bounded runtime snapshot')
        for row in doc['candidates']:
            if any(not isinstance(row.get(f), str) for f in FIELDS) or len(row['source']) > 1024 or row['reason'] not in REASONS or key(row) != row.get('key') or type(row.get('count')) is not int or not 0 < row['count'] <= 2**31-1:
                raise ValueError('Invalid candidate')
            ident = (row['key'], doc['session'])
            # Re-exporting later snapshots of the same run must not double-count.
            previous = observations.get(ident)
            if previous is None or row['count'] > previous['count']:
                observations[ident] = row
    merged = {}
    for (ident, session), row in observations.items():
        if ident not in merged:
            e = entries.get(row['id'])
            bound = row['reason'] == 'missing_translation' and e is not None and source_matches(row, e)
            merged[ident] = dict(row, count=0, sessions=0, review='translation' if bound else 'binding', target_hint=e['target'] if bound else None, approved=False, translation='')
        merged[ident]['count'] += row['count']
        merged[ident]['sessions'] += 1
    return {'format': 1, 'kind': 'cw3-candidate-review', 'candidates': sorted(merged.values(), key=lambda r: (-r['count'], r['key']))}

def merge(review, dictionary):
    if review.get('format') != 1 or review.get('kind') != 'cw3-candidate-review':
        raise ValueError('Not a review export')
    result = copy.deepcopy(dictionary)
    entries = {e['id']: e for e in result['entries']}
    locks = read(ROOT / 'translations/targets.lock.json')
    if set(entries) != set(locks) or len(entries) != len(result['entries']):
        raise ValueError('Dictionary must retain the fixed target set')
    for e in entries.values():
        payload = json.dumps({f: e[f] for f in ('id', 'source', 'target')}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        if hashlib.sha256(payload).hexdigest() != locks[e['id']]:
            raise ValueError('Source/target lock mismatch')
    chosen = set()
    for row in review['candidates']:
        if row.get('approved') is not True:
            continue
        e = entries.get(row.get('id'))
        if row.get('reason') != 'missing_translation' or e is None or not source_matches(row, e) or row.get('key') != key(row):
            raise ValueError('Unbound/mismatched candidates need audited bindings; cannot merge')
        value = row.get('translation')
        if not isinstance(value, str) or not value.strip() or len(value) > 4096 or e['id'] in chosen:
            raise ValueError('Empty, oversized or duplicate approved translation')
        for pattern in (r'\{\d+(?:[^{}]*)\}|%(?:\d+\$)?[sdif]', r'\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]'):
            if re.findall(pattern, e['source']) != re.findall(pattern, value):
                raise ValueError('Placeholder/tag order mismatch')
        if e['target']['kind'] == 'crpl' and any(c in value.replace('\\n', '') for c in '\"\r\n\\'):
            raise ValueError('Unsafe CRPL translation')
        e['translation'] = value
        chosen.add(e['id'])
    return result, len(chosen)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    a = sub.add_parser('export'); a.add_argument('snapshots', nargs='+')
    b = sub.add_parser('merge'); b.add_argument('review')
    for p in (a, b):
        p.add_argument('--dictionary', default=str(ROOT / 'translations/zh-CN.json'))
        p.add_argument('--output', required=True, help='New local review/dictionary file; existing files are never overwritten')
    args = parser.parse_args()
    dictionary = read(args.dictionary)
    if args.action == 'export':
        result = export(args.snapshots, dictionary)
        print(len(result['candidates']), 'deduplicated observations; candidates require manual review')
    else:
        result, count = merge(read(args.review), dictionary)
        print(count, 'approved existing translations merged; validate font coverage before adoption')
    write_new(args.output, result)
if __name__ == '__main__':
    main()
