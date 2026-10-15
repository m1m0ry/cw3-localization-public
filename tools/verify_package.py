"""Verify a player ZIP; optionally exercise reinstall/cleanup on an isolated fixture."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

from package_player import PLAYER_CONTROLS, PLAYER_SOURCES, instructions, supported_target, target_description, validate_release_payload
from player_install import MACOS, RUNTIME, atomic_copy, installed_path, target_identity, target_layout

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_name(name, directory=False):
    require(isinstance(name, str) and name, 'Empty or invalid package path')
    require('\\' not in name and not PureWindowsPath(name).is_absolute(), 'Unsafe package path: ' + name)
    path = name[:-1] if directory and name.endswith('/') else name
    parts = path.split('/')
    require(all(part and part not in ('.', '..') and not part.endswith((' ', '.'))
                and not any(c in part for c in ':<>|?*')
                and not any(ord(c) < 32 for c in part)
                and not PureWindowsPath(part).is_reserved() for part in parts),
            'Unsafe package path: ' + name)
    return path


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def inspect_zip(archive, build, supported, exe):
    require(isinstance(build, dict), 'Invalid build manifest')
    require(build.get('format') == 1 and build.get('revision') == 'independent-v12-candidate',
            'Expected the current independent build manifest')
    require(build.get('steam_build') == supported['steam_build'] and build.get('version') == supported['version'],
            'Build target differs from the supported game')
    require(target_layout(build) == target_layout(supported), 'Build/profile platform mismatch')
    if target_layout(supported)['target_id'] == MACOS:
        require(target_identity(build) == target_identity(supported), 'Build/profile target fingerprint mismatch')
    infos = archive.infolist()
    require(infos, 'Empty package ZIP')
    names = [safe_name(info.orig_filename, info.is_dir()) for info in infos]
    require(len({name.casefold() for name in names}) == len(names), 'Duplicate or Windows-conflicting ZIP paths')
    require(all(stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR) for info in infos),
            'ZIP contains a link or special file')
    roots = {name.split('/')[0] for name in names}
    require(len(roots) == 1, 'ZIP must contain one package root')
    root = roots.pop()
    require(all(info.is_dir() or '/' in name for info, name in zip(infos, names)),
            'ZIP contains a file outside the package root')
    files = {name[len(root) + 1:]: info for info, name in zip(infos, names) if not info.is_dir()}
    require('manifest.json' in files, 'Missing player manifest')
    player = json.loads(archive.read(files['manifest.json']))
    require(isinstance(player, dict), 'Invalid player manifest')
    require(player.get('format') == 2 and isinstance(player.get('version'), str) and player['version']
            and player['version'] == build.get('patch_version'),
            'Player/build version mismatch')
    target = target_description(supported)
    require(player.get('target') == target and player.get('exe_sha256') == supported['exe_sha256'],
            'Player target or executable hash mismatch')
    require(target_identity(player) == target_identity(supported), 'Player platform or install layout mismatch')
    if exe is not None:
        require(sha(exe) == player['exe_sha256'], 'Installed '+target_layout(player)['executable']+' does not match the package target')
    for key in ('required_originals', 'controlled_fonts'):
        require(player.get(key, {}) == build.get(key, {}), 'Player/build metadata mismatch: ' + key)
    for key in ('source_repo', 'source_commit', 'source_dirty', 'build_inputs_sha256'):
        require((key in player) == (key in build) and player.get(key) == build.get(key),
                'Player/build provenance mismatch: ' + key)
    if 'source_commit' in player:
        require(isinstance(player['source_commit'], str) and re.fullmatch(r'[0-9a-f]{40}', player['source_commit']),
                'Invalid source commit SHA')
    if 'source_dirty' in player:
        require(isinstance(player['source_dirty'], bool), 'Invalid source_dirty flag')
    if 'build_inputs_sha256' in player:
        require(valid_hash(player['build_inputs_sha256']), 'Invalid build-input hash')
    rows = build.get('files')
    require(isinstance(rows, list) and rows and player.get('files') == rows, 'Player/build payload manifest mismatch')
    payload = set()
    for row in rows:
        require(isinstance(row, dict) and {'file', 'before', 'after', 'bytes'} <= row.keys(), 'Invalid payload row')
        name = safe_name(row.get('file'))
        require(name.casefold() not in {p.casefold() for p in payload}, 'Duplicate payload path: ' + name)
        require(name not in PLAYER_CONTROLS, 'Payload overlaps a package control file: ' + name)
        require(row.get('before') is None or valid_hash(row['before']), 'Invalid original hash: ' + name)
        require(valid_hash(row.get('after')) and type(row.get('bytes')) is int and row['bytes'] >= 0,
                'Invalid payload hash or size: ' + name)
        payload.add(name)
    validate_release_payload(payload,target_layout(supported)['target_id'])
    require(set(files) == payload | set(PLAYER_CONTROLS),
            'ZIP file list differs from payload and player controls; missing=' + str(sorted((payload | set(PLAYER_CONTROLS)) - set(files)))
            + ', extra=' + str(sorted(set(files) - (payload | set(PLAYER_CONTROLS)))))
    allowed_dirs = {root}
    for name in files:
        allowed_dirs.update(str(parent) for parent in PurePosixPath(root + '/' + name).parents if str(parent) != '.')
    require(all(not info.is_dir() or name in allowed_dirs for info, name in zip(infos, names)),
            'ZIP contains an unexpected directory')
    require(player.get('runtime_files') == sorted(RUNTIME & payload), 'Runtime-file list differs from packaged payload')
    originals = player.get('required_originals', {})
    require(isinstance(originals, dict), 'Invalid required-original manifest')
    for name, expected in originals.items():
        require(safe_name(name).startswith('CW3_Data/'), 'Required original is outside game data: ' + name)
        require(name not in payload and valid_hash(expected), 'Invalid required original: ' + name)
    controlled = player.get('controlled_fonts', {})
    require(isinstance(controlled, dict), 'Invalid controlled-font metadata')
    if controlled:
        bundled_fonts = {'sans': 'CW3Localization/font.ttf', 'serif': 'CW3Localization/serif.ttf'}
        hashes = {row['file']: row['after'] for row in rows}
        require(set(controlled) == set(bundled_fonts) and all(hashes.get(name) == controlled[family] for family, name in bundled_fonts.items()),
                'Controlled-font metadata differs from bundled font hashes')
    for row in rows:
        info = files[row['file']]
        require(info.file_size == row['bytes'], 'ZIP payload size mismatch: ' + row['file'])
        digest = hashlib.sha256()
        with archive.open(info) as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        require(digest.hexdigest() == row['after'], 'ZIP payload hash mismatch: ' + row['file'])
    # Control scripts and licenses must be the current packaging sources, not merely valid ZIP entries.
    for name, source in PLAYER_SOURCES.items():
        require(archive.read(files[name]) == (ROOT / source).read_bytes(), 'Player control differs from packaging source: ' + name)
    expected_instructions = instructions(supported, player['version'], ROOT)
    require(archive.read(files['使用说明.txt']).decode('utf8').replace('\r\n', '\n') == expected_instructions,
            'Player instructions differ from the versioned packaging source')
    return root, player


def exercise_fixture(archive, root, player, original, exe):
    with tempfile.TemporaryDirectory(prefix='cw3-package-gate-') as folder:
        tmp = Path(folder)
        archive.extractall(tmp / 'package')
        package = tmp / 'package' / root
        game = tmp / 'game'
        game.mkdir()
        layout = target_layout(player)
        executable = game / layout['executable']
        executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, executable)
        (game / layout['data_dir']).mkdir(parents=True, exist_ok=True)
        originals = {row['file']: row['before'] for row in player['files'] if row['before']}
        originals.update(player.get('required_originals', {}))
        for name, expected in originals.items():
            source = original / name
            require(sha(source) == expected, 'Original fixture hash mismatch: ' + name)
            target = installed_path(game, name, player)
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(source, target)
        sentinel = game / 'fixture-save.dat'
        sentinel.write_bytes(b'UNCHANGED SAVE SENTINEL')
        def run(action):
            # This sandbox cannot enumerate host processes. The fixture is
            # isolated; exercise the shipped entry point with only its idle
            # boundary replaced. The process matcher has a separate test.
            entry = ('import sys,unittest.mock as mock\n'
                     'sys.path.insert(0,sys.argv[1])\n'
                     'import install\n'
                     'sys.argv=["install.py","--game",sys.argv[2],"--action",sys.argv[3]]\n'
                     'with mock.patch.object(install,"idle"),mock.patch.object(install,"signing"),mock.patch.object(install.subprocess,"run",return_value=mock.Mock(returncode=0)):install.main()\n')
            subprocess.run([sys.executable, '-c', entry, str(package), str(game), action], check=True, timeout=180)
        run('install')
        require(all(sha(installed_path(game, row['file'], player)) == row['after'] for row in player['files']), 'Fixture installation hash mismatch')
        run('install')
        require(all(sha(installed_path(game, row['file'], player)) == row['after'] for row in player['files']), 'Fixture reinstallation hash mismatch')
        run('clean')
        from player_install import INJECTED
        require(all(not installed_path(game,name,player).exists() for name in INJECTED), 'Injected program remains after cleanup')
        require(all(sha(installed_path(game, name, player)) == expected for name, expected in player.get('required_originals',{}).items()), 'Untouched original changed in fixture')
        # Steam, rather than this installer, restores the patched original assets.
        require(sha(executable) == player['exe_sha256'], 'Fixture executable changed')
        require(sentinel.read_bytes() == b'UNCHANGED SAVE SENTINEL', 'Fixture save sentinel changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--inspect-only', action='store_true', help='Read the ZIP; verify a target executable when available, with no extraction or installation')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    def loc(key):
        path = Path(config[key])
        return path if path.is_absolute() else ROOT / path
    build = json.loads((loc('package') / 'manifest.json').read_text())
    supported = supported_target(build)
    package = Path(args.package)
    exe = loc('game') / target_layout(supported)['executable']
    # Locked build inputs need no executable; installed-game and fixture checks still require it.
    checked_exe = None if args.inspect_only and not exe.is_file() else exe
    with zipfile.ZipFile(package) as archive:
        root, player = inspect_zip(archive, build, supported, checked_exe)
        if not args.inspect_only:
            exercise_fixture(archive, root, player, loc('original'), exe)
    print('ZIP SHA256:', sha(package))
    print('PASS ZIP integrity:', len(player['files']), 'payload files +', len(PLAYER_CONTROLS), 'player controls;', player['version'])
    print('Supported target executable SHA256:', player['exe_sha256'])
    print('Actual executable hash verified.' if checked_exe is not None else 'Actual executable unavailable; only the package target metadata was checked.')
    if 'source_commit' in player:
        print('Source commit:', player['source_commit'], '; source_dirty:', player.get('source_dirty'))
    if args.inspect_only:
        print('Read-only inspection complete; no extraction, game copy or install/cleanup performed.')
    else:
        print('PASS shipped CLI install/cleanup and every fixture hash; installed game untouched.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        sys.exit('FAIL package verification: ' + str(error))
