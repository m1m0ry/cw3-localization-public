"""Adopted dictionary checks shared by builds and offline updates."""
from pathlib import Path
import hashlib, json, re

def loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def integer(value):
        number = int(value)
        if not -(2**31) <= number < 2**31:
            raise ValueError('JSON integer exceeds runtime Int32 range')
        return number
    def unsupported(value):
        raise ValueError('Runtime JSON supports only Int32 numbers: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                      parse_float=unsupported, parse_constant=unsupported)

def read(path):
    path = Path(path)
    if path.stat().st_size > 4_000_000:
        raise ValueError('Dictionary exceeds runtime 4 MB limit')
    return loads(path.read_text(encoding='utf8'))

def check(doc, locks, codepoints):
    assert type(doc['format']) is int and doc['format'] == 1 and doc['language'] == 'zh-CN'
    entries = doc['entries']
    assert len({e['id'] for e in entries}) == len(entries), 'Duplicate ID'
    assert {e['id'] for e in entries} == set(locks), 'Dictionary must retain the fixed target set'
    cps = set(codepoints)
    tokens = [r'\{\d+(?:[^{}]*)\}|%(?:\d+\$)?[sdif]', r'\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]']
    for e in entries:
        assert set(e) == {'id','source','context','translation','target'}, e['id']
        assert all(isinstance(e[k], str) and e[k] for k in ('id','source','context','translation')), e['id']
        payload = json.dumps({k:e[k] for k in ('id','source','target')}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(payload).hexdigest() == locks[e['id']], 'Immutable target/source changed: ' + e['id']
        for rx in tokens:
            assert re.findall(rx, e['source']) == re.findall(rx, e['translation']), 'Placeholder/tag mismatch or order changed: ' + e['id']
        if e['target']['kind'] == 'crpl':
            assert not any(c in e['translation'].replace('\\n', '') for c in '\"\r\n\\'), 'Unsafe CRPL literal: ' + e['id']
        missing = {c for c in e['translation'] if ord(c) not in cps and not c.isspace()}
        assert not missing, f"Font subset needs maintainer update: {e['id']} {''.join(sorted(missing))}"
    return entries
