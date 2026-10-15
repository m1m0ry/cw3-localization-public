"""The two audited CW3 layouts; build artifacts retain logical CW3_Data paths."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = 'windows-steam-22453699'
MACOS = 'macos-steam-22453699'


def load(config):
    if not __debug__:
        raise RuntimeError('Build verification requires Python assertions; do not use -O')
    ident = config.get('target_id', WINDOWS)
    if ident == MACOS:
        target = json.loads((ROOT / 'resources/macos-target.json').read_text())
        if target['id'] != MACOS or target['platform'] != 2:
            raise ValueError('Mac target profile identity changed')
        return target
    if ident != WINDOWS:
        raise ValueError('Unknown CW3 target: ' + str(ident))
    supported = json.loads((ROOT / 'resources/supported-build.json').read_text())
    layout = json.loads((ROOT / 'resources/layout.json').read_text())
    return dict(supported, **layout, id=WINDOWS, target_id=WINDOWS, platform=5,
                data_dir='CW3_Data', executable='CW3.exe')


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
