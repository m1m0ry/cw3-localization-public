"""The two audited CW3 layouts; build artifacts retain logical CW3_Data paths."""
from pathlib import Path
import hashlib
import json
from player_install import target_layout

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = 'windows-steam-22453699'
MACOS = 'macos-steam-22453699'


def load(config):
    if not __debug__:
        raise RuntimeError('Build verification requires Python assertions; do not use -O')
    ident = config.get('target_id')
    if ident not in (WINDOWS,MACOS):raise ValueError('Explicit CW3 target_id required: '+str(ident))
    name='macos-target.json' if ident==MACOS else 'supported-build.json'
    target=json.loads((ROOT/'resources'/name).read_text())
    if ident==WINDOWS:target.update(json.loads((ROOT/'resources/layout.json').read_text()))
    if target_layout(target)['target_id']!=ident:raise ValueError('Target profile identity changed')
    return dict(target,id=ident)


def installed(game, logical, target):
    path = Path(logical)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'CW3_Data':
        raise ValueError('Expected a logical Data input: ' + str(logical))
    return Path(game) / target['data_dir'] / path.relative_to('CW3_Data')


def verify_inputs(original, target):
    for name, expected in target['original_hashes'].items():
        path = Path(original) / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Original input fingerprint mismatch: ' + name)


def manifest_fields(target):
    return {key: target[key] for key in ('target_id', 'platform', 'data_dir', 'executable', 'exe_sha256')}
