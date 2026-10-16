"""Resolve one audited Mac binding overlay without changing the translation source.

The canonical dictionary and its locks retain the adopted Windows targets. Mac
coordinates are explicit, complete build inputs; a missing row never inherits a
Windows coordinate. The runtime still receives the same fixed translation IDs.
"""
from pathlib import Path
import argparse
import base64
import copy
import hashlib
import json
import struct
import xml.etree.ElementTree as ET

import translation_contract

ROOT = Path(__file__).resolve().parents[1]
MACOS = 'macos-steam-22453699'
PHYSICAL = {'managed', 'label', 'textmesh'}
SHARED = {'xml_text', 'crpl', 'crpl_display', 'crpl_conversation', 'crpl_output', 'render_map', 'label_display'}
sha = lambda data: hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(entries):
    if not __debug__:
        raise RuntimeError('CW3 binding checks require Python assertions (no -O)')
    locks_path = ROOT / 'translations/targets.lock.json'
    locks = translation_contract.read(locks_path)
    ids = [e['id'] for e in entries]
    require(len(ids) == len(set(ids)) and set(ids) == set(locks), 'Canonical binding ID set changed')
    for e in entries:
        payload = json.dumps({key: e[key] for key in ('id', 'source', 'target')}, ensure_ascii=False,
                             sort_keys=True, separators=(',', ':')).encode()
        require(sha(payload) == locks[e['id']], 'Canonical source/target changed: ' + e['id'])
    return locks, sha(locks_path.read_bytes())


def _inputs(original, profile):
    require(profile.get('id') == MACOS and profile.get('platform') == 2, 'Unknown Mac binding profile')
    for name, expected in profile['original_hashes'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == 'CW3_Data', 'Unsafe logical input path')
        require(sha((original / path).read_bytes()) == expected, 'Binding input hash mismatch: ' + name)


class _Resources:
    def __init__(self, original, platform):
        self.original, self.platform, self.files, self.docs = Path(original), platform, {}, {}

    def file(self, name):
        from unity15_metadata import read_unity15_metadata
        if name not in self.files:
            self.files[name] = read_unity15_metadata((self.original / name).read_bytes(), self.platform)[0]
        return self.files[name]

    def reference(self, name, file_id, object_id):
        f = self.file(name)
        if file_id:
            require(0 < file_id <= len(f.externals), 'Invalid component script reference')
            name = 'CW3_Data/' + f.externals[file_id - 1].path
        return self.file(name).objects[object_id]

    def path(self, name, game_object_id, seen=None):
        seen = set() if seen is None else seen
        require(game_object_id not in seen, 'Cyclic component hierarchy')
        seen.add(game_object_id)
        f = self.file(name)
        obj = f.objects[game_object_id]
        require(obj.type.name == 'GameObject', 'Component does not reference a GameObject')
        go = obj.parse_as_dict()
        transforms = [p['m_PathID'] for kind, p in go['m_Component'] if kind == 4]
        require(len(transforms) == 1, 'Ambiguous component Transform')
        transform = f.objects[transforms[0]].parse_as_dict()
        parent = transform['m_Father']['m_PathID']
        prefix = self.path(name, f.objects[parent].parse_as_dict()['m_GameObject']['m_PathID'], seen) + '/' if parent else ''
        return prefix + go['m_Name']

    def component(self, name, object_id, kind):
        obj = self.file(name).objects[object_id]
        raw = obj.get_raw_data()
        if kind == 'textmesh':
            require(obj.type.name == 'TextMesh', 'Expected TextMesh binding')
            data = obj.parse_as_dict()
            game_object_id, source, script = data['m_GameObject']['m_PathID'], data['m_Text'], 'TextMesh'
        else:
            require(kind == 'label' and obj.type.name == 'MonoBehaviour', 'Expected UILabel binding')
            require(len(raw) >= 96, 'Truncated UILabel binding')
            game_object_id = struct.unpack_from('<q', raw, 4)[0]
            script_file, script_id = struct.unpack_from('<iq', raw, 16)
            script_obj = self.reference(name, script_file, script_id)
            require(script_obj.type.name == 'MonoScript', 'Expected component MonoScript')
            script = script_obj.parse_as_dict()['m_ClassName']
            require(script == 'UILabel', 'Expected UILabel script identity')
            # Verified Unity 5.2 NGUI schema: MonoBehaviour header/name, 60 bytes
            # of UIWidget/font fields, then the length-prefixed mText string.
            # Each adopted object additionally retains its entire payload hash.
            name_size = struct.unpack_from('<i', raw, 28)[0]
            require(0 <= name_size <= len(raw) - 32, 'Invalid UILabel name size')
            at = ((32 + name_size + 3) & ~3) + 60
            require(at + 4 <= len(raw), 'Truncated UILabel text size')
            size = struct.unpack_from('<i', raw, at)[0]
            require(0 <= size <= len(raw) - at - 4, 'Invalid UILabel text size')
            source = raw[at + 4:at + 4 + size].decode('utf8')
        filename = Path(name).name
        scenes = {0: 'Splash', 1: 'MainMenu', 2: 'Gal', 3: 'Game', 4: 'Results', 5: 'Prelude', 6: 'Epilogue'}
        scene = scenes[int(filename[5:])] if filename.startswith('level') else 'Splash' if filename == 'mainData' else '*'
        if filename == 'sharedassets6.assets':
            scene = 'Epilogue'
        return dict(source=source, path=self.path(name, game_object_id), scene=scene,
                    script=script, object_sha256=sha(raw))

    def shared(self, entry):
        from resource_text import unpack_script, paths, scripts, display_calls
        target = entry['target']
        if target['kind'] in ('render_map', 'label_display'):
            return {}
        obj = self.file(target['file']).objects[target['object_id']]
        require(obj.type.name == 'TextAsset', 'Expected shared TextAsset')
        key = (target['file'], target['object_id'])
        if key not in self.docs:
            root = ET.fromstring(unpack_script(obj.parse_as_dict()['m_Script']))
            self.docs[key] = dict(paths(root))
        node = self.docs[key][target['xml_path']]
        if target['kind'] == 'xml_text':
            require(node.text == entry['source'], 'Shared XML source drift: ' + entry['id'])
        else:
            code = base64.b64decode(scripts(node.text)[target['script']], validate=True).decode('utf-16le')
            if target['kind'] == 'crpl_output':
                from script_outputs import output_definition
                output_definition(code, target, entry['source'])
            else:
                sites = {site.literal_index: site for site in display_calls(code, include_comments=True)}
                site = sites[target['literal_index']]
                require(site.source == entry['source'], 'Shared script source drift: ' + entry['id'])
                require(site.family == ('conversation' if target['kind'] == 'crpl_conversation' else 'show'), 'Shared script display family drift')
        return {'object_sha256': sha(obj.get_raw_data())}


def resolve(entries, original, profile):
    """Resolve explicit coordinates within the caller's hash-verified original snapshot."""
    locks, lock_hash = _canonical(entries)
    if profile.get('platform') == 5:
        require(profile.get('id') == 'windows-steam-22453699', 'Unknown Windows binding profile')
        return copy.deepcopy(entries)
    original = Path(original)
    require(profile.get('id') == MACOS and profile.get('platform') == 2, 'Unknown Mac binding profile')
    overlay = translation_contract.read(ROOT / 'resources/macos-bindings.json')
    require(overlay.get('format') == 1 and overlay.get('profile') == MACOS and overlay.get('platform') == 2, 'Mac binding overlay identity mismatch')
    require(overlay.get('canonical_lock_sha256') == lock_hash, 'Mac binding canonical lock mismatch')
    require(overlay.get('original_hashes') == profile['original_hashes'], 'Mac binding input profile mismatch')
    rows = overlay['entries']
    require(set(rows) == set(locks), 'Mac binding overlay must cover every canonical ID')
    resources = _Resources(original, 2)
    resolved, physical, display_keys = [], set(), set()
    for entry in entries:
        ident, kind = entry['id'], entry['target']['kind']
        row = rows[ident]
        require(row.get('canonical_sha256') == locks[ident] and row.get('source_sha256') == sha(entry['source'].encode()), 'Mac binding source lock mismatch: ' + ident)
        require(kind in PHYSICAL | SHARED, 'Unknown translation target kind')
        result = copy.deepcopy(entry)
        if kind in PHYSICAL:
            require(row.get('binding') == 'physical' and 'target' in row, 'Missing explicit physical Mac binding: ' + ident)
            target = row['target']
            require(target.get('kind') == kind, 'Mac binding kind mismatch: ' + ident)
            if kind == 'managed':
                require(set(target) == {'kind', 'method_token', 'instruction_index', 'method', 'anchor_sha256'}, 'Invalid managed binding fields')
                require(type(target['method_token']) is int and target['method_token'] > 0 and type(target['instruction_index']) is int and target['instruction_index'] >= 0, 'Mac managed coordinates must be pristine')
                require(isinstance(target['method'], str) and target['method'] and isinstance(target['anchor_sha256'], str) and len(target['anchor_sha256']) == 64 and all(c in '0123456789abcdef' for c in target['anchor_sha256']), 'Missing managed method/IL anchor')
                key = (kind, target['method_token'], target['instruction_index'])
            else:
                require(set(target) == {'kind', 'file', 'object_id'} and target['file'] == entry['target']['file'] and type(target['object_id']) is int, 'Invalid component binding fields')
                anchor = resources.component(target['file'], target['object_id'], kind)
                require(anchor['source'] == entry['source'] and anchor == row.get('anchor'), 'Mac component anchor drift: ' + ident)
                display_key = (kind, anchor['scene'], anchor['path'], anchor['source'])
                require(display_key not in display_keys, 'Duplicate component display identity: ' + ident)
                display_keys.add(display_key)
                key = (kind, target['file'], target['object_id'])
            require(key not in physical, 'Duplicate physical Mac binding: ' + ident)
            physical.add(key)
            result['target'] = copy.deepcopy(target)
        else:
            require(row.get('binding') == 'shared' and 'target' not in row, 'Missing explicit shared Mac binding: ' + ident)
            require(resources.shared(entry) == row.get('anchor'), 'Shared resource anchor drift: ' + ident)
        resolved.append(result)
    return resolved


def extract(entries, windows, original, profile, managed_rows):
    """Maintainer extraction only; normal builds never derive replacement coordinates."""
    locks, lock_hash = _canonical(entries)
    _inputs(Path(original), profile)
    win, mac = _Resources(windows, 5), _Resources(original, 2)
    managed = {}
    for line in managed_rows.splitlines():
        ident, token, index, method, fingerprint, source = line.split('\t')
        require(ident not in managed, 'Duplicate managed extraction ID')
        managed[ident] = (dict(kind='managed', method_token=int(token), instruction_index=int(index),
                              method=base64.b64decode(method, validate=True).decode(), anchor_sha256=fingerprint),
                          base64.b64decode(source, validate=True).decode())
    expected = {e['id'] for e in entries if e['target']['kind'] == 'managed'}
    require(set(managed) == expected, 'Managed extraction ID coverage mismatch')
    indexes, rows = {}, {}
    for entry in entries:
        ident, target = entry['id'], entry['target']
        kind = target['kind']
        row = dict(canonical_sha256=locks[ident], source_sha256=sha(entry['source'].encode()), binding='physical' if kind in PHYSICAL else 'shared')
        if kind == 'managed':
            row['target'], source = managed[ident]
            require(source == entry['source'], 'Managed extraction source drift')
        elif kind in ('label', 'textmesh'):
            old = win.component(target['file'], target['object_id'], kind)
            require(old['source'] == entry['source'], 'Canonical component source drift: ' + ident)
            key = (target['file'], kind)
            if key not in indexes:
                index = {}
                for oid, obj in mac.file(target['file']).objects.items():
                    if obj.type.name != ('MonoBehaviour' if kind == 'label' else 'TextMesh'):
                        continue
                    if kind == 'label':
                        raw = obj.get_raw_data()
                        if len(raw) < 28:
                            continue
                        file_id, script_id = struct.unpack_from('<iq', raw, 16)
                        if mac.reference(target['file'], file_id, script_id).parse_as_dict()['m_ClassName'] != 'UILabel':
                            continue
                    anchor = mac.component(target['file'], oid, kind)
                    index.setdefault((anchor['scene'], anchor['path'], anchor['source']), []).append((oid, anchor))
                indexes[key] = index
            matches = indexes[key].get((old['scene'], old['path'], old['source']), [])
            require(len(matches) == 1, 'Ambiguous Mac component: ' + ident)
            oid, row['anchor'] = matches[0]
            row['target'] = dict(kind=kind, file=target['file'], object_id=oid)
        else:
            require(kind in SHARED, 'Unknown canonical target kind')
            row['anchor'] = mac.shared(entry)
            require(row['anchor'] == win.shared(entry), 'Shared resource bytes differ: ' + ident)
        rows[ident] = row
    return dict(format=1, profile=MACOS, platform=2, canonical_lock_sha256=lock_hash,
                original_hashes=profile['original_hashes'], entries=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract a reviewed Mac overlay from locked originals and Cecil binding rows; never installs.')
    parser.add_argument('--windows', required=True)
    parser.add_argument('--original', required=True)
    parser.add_argument('--managed', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    doc = translation_contract.read(ROOT / 'translations/zh-CN.json')
    profile = json.loads((ROOT / 'resources/macos-target.json').read_text())
    overlay = extract(doc['entries'], args.windows, args.original, profile, Path(args.managed).read_text())
    with Path(args.output).open('x', encoding='utf8') as output:
        json.dump(overlay, output, ensure_ascii=False, indent=2)
        output.write('\n')
