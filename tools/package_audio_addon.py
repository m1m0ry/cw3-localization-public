"""Build a separate optional overlay from a verified localized player package.

Developer-only tool. Players copy one supplied file; the main patch is unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSET = 'CW3_Data/sharedassets2.assets'
sha = lambda data: hashlib.sha256(data).hexdigest()


def baseline(player, manifest, spec, supported):
    """Refuse an original, altered, or unsupported resource before writing output."""
    if manifest.get('format') != 2 or not manifest.get('version'):
        raise ValueError('Expected a versioned localized player package')
    if manifest.get('exe_sha256') != supported['exe_sha256']:
        raise ValueError('Unsupported executable version')
    rows = [r for r in manifest['files'] if r['file'] == ASSET]
    if len(rows) != 1 or rows[0]['after'] != spec['baseline_sha256']:
        raise ValueError('Unsupported localized resource; rebuild the matching addon')
    raw = (player / ASSET).read_bytes()
    if sha(raw) != spec['baseline_sha256'] or len(raw) != rows[0]['bytes']:
        raise ValueError('Localized resource hash/size mismatch')
    return raw


def package(player, out):
    import workflow
    player, out = Path(player).resolve(), Path(out).resolve()
    if not out.is_relative_to((ROOT / 'local-only').resolve()) or out.exists() or any(out.with_name(out.name + '-' + action + '.zip').exists() for action in ('启用', '停用')):
        raise ValueError('Choose a new local-only output directory and ZIP name')
    spec = json.loads((ROOT / 'resources/audio-startup-addon.json').read_text())
    supported = json.loads((ROOT / 'resources/supported-build.json').read_text())
    manifest = json.loads((player / 'manifest.json').read_text())
    raw = baseline(player, manifest, spec, supported)
    accelerated = workflow.resource(raw, [], spec['edits'], None)
    if sha(accelerated) != spec['enabled_sha256']:
        raise ValueError('Unexpected accelerated resource output')
    # Full hashes bind both files, including existing NGUI repairs. Never restore
    # from the original game input, which would erase localized resource repairs.
    files = {}
    for directory, data in [('启用', accelerated), ('停用', raw)]:
        name = directory + '/' + ASSET
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = dict(sha256=sha(data), bytes=len(data))
    record = dict(format=1, name='CW3 可选启动加速覆盖包',
                  patch_version=manifest['version'], target=manifest['target'],
                  exe_sha256=manifest['exe_sha256'],
                  base_manifest_sha256=sha((player / 'manifest.json').read_bytes()),
                  files=files)
    for key in ('source_repo', 'source_commit', 'source_dirty'):
        if key in manifest:
            record[key] = manifest[key]
    (out / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    (out / '使用说明.txt').write_text(
        'CW3 可选启动加速覆盖包 — ' + manifest['version'] + '\n\n'
        '仅用于配套版本的 Windows Steam 2.12 / build 22453699 汉化。汉化本体默认不启用此优化。\n\n'
        '启用：退出游戏，将启用包内的“CW3_Data/sharedassets2.assets”复制到游戏的 CW3_Data 内，覆盖同名文件。\n'
        '停用：退出游戏，将停用包内的“CW3_Data/sharedassets2.assets”复制到同一位置，覆盖同名文件。不要删除游戏中的该文件。\n'
        '只替换这个文件，并保留停用包供恢复。\n'
        '升级、重装或恢复汉化前，先用本包“停用”文件恢复，再执行汉化安装器。启用期间安装器会拒绝未知资源。\n'
        '不要用旧版附加包覆盖新版汉化，不适用于其他改过此资源的补丁或原生 Mac 版。\n\n'
        '停用文件保留配套汉化的字体关联，不修改外置字体、字体配置或存档。\n'
        '出现首次音效延迟或战斗音频问题时停用。配套版本及文件校验值见 manifest.json。\n', encoding='utf-8')
    for action in ('启用', '停用'):
        archive = out.with_name(out.name + '-' + action + '.zip')
        package_record = dict(record, action=action,
                              expected_before_sha256=spec['baseline_sha256' if action == '启用' else 'enabled_sha256'],
                              files={ASSET: files[action + '/' + ASSET]})
        entries = {ASSET: (out / action / ASSET).read_bytes(),
                   '使用说明.txt': ('本包操作：' + action + '\n\n' + (out / '使用说明.txt').read_text()).encode('utf-8'),
                   'manifest.json': (json.dumps(package_record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(entries.items()):
                info = zipfile.ZipInfo(out.name + '-' + action + '/' + name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, data)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--player-package', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    package(args.player_package, args.output)
    print('Prepared optional enable/disable overlay:', args.output)


if __name__ == '__main__':
    main()
