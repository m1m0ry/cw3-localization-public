"""Package verified complete patch files with the offline install/cleanup entry point."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
from player_install import MACOS, target_identity, target_layout, validate_release_payload
ROOT=Path(__file__).resolve().parents[1]
PLAYER_SOURCES={'install.py':'tools/player_install.py','安装汉化.command':'player/安装汉化.command','安装汉化.cmd':'player/安装汉化.cmd','OFL.txt':'fonts/OFL.txt','LICENSE':'LICENSE','NOTICE.md':'NOTICE.md','字体设置.md':'docs/text-style.md'}
PLAYER_CONTROLS=set(PLAYER_SOURCES)|{'manifest.json','使用说明.txt'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def target_description(supported):
    return ('macOS native Steam ' if target_layout(supported)['target_id']==MACOS else 'Windows Steam ')+supported['version'].removesuffix(' Steam')+' / build '+supported['steam_build']+' / Unity '+supported['unity_version']

def supported_target(build,root=None):
    root=ROOT if root is None else Path(root)
    layout=target_layout(build)
    name='macos-target.json' if layout['target_id']==MACOS else 'supported-build.json'
    supported=json.loads((root/'resources'/name).read_text())
    if target_identity(build)!=target_identity(supported):raise ValueError('Build/profile target fingerprint mismatch')
    return supported

def instructions(supported,version,root=ROOT):
    if target_layout(supported)['target_id']!=MACOS:
        return (root/'player/使用说明-v12.txt').read_text().replace(' v12\n',' '+version+'\n',1)
    return ('CW3 简体中文补丁 '+version+'\n适用 '+target_description(supported)+'。\n\n'
            '1. 完全退出游戏，解压 CW3-Mac-'+version+'.zip，准备 Python 3.10+。\n'
            '2. 在 Steam 中右键游戏 → 管理 → 浏览本地文件，找到包含 CW3.app 的目录。\n'
            '3. 双击包内「安装汉化.command」，按提示选择该目录，再选「1 安装/重装汉化」。\n\n'
            '安装器负责将资源写入 CW3.app 并做必要的 ad-hoc 重签，保留用户词典、字体设置、自定义字体和存档。系统阻止启动时，确认来源后按系统提示手动允许。\n'
            '字体与字号设置及自定义字体目录见「字体设置.md」。\n'
            '恢复原版：运行安装脚本，选择「2 清理汉化程序」，再通过 Steam「验证游戏文件完整性」。Steam 不会自动删除额外注入的 DLL。\n'
            '\n自定义译文\n以下文件位于游戏目录的 CW3Localization 中：\n'
            '- zh-CN.default.json：随补丁更新的默认译文。\n'
            '- zh-CN.user.json：可选的自定义译文；有效条目优先于默认译文，安装时保留。\n'
            '- zh-CN.json：旧版词典，当前游戏不读取；自定义内容使用 zh-CN.user.json。\n'
            '从默认文件复制要修改的条目到用户文件，沿用 format、language、entries 格式，只保留自定义项。仅改 translation，保留 ID、原文、标签和占位符；退出游戏后修改，重启生效。\n'
            '文件哈希见 manifest.json，许可见 OFL.txt 与 CW3Localization/Serif-OFL.txt。\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--directory-only',action='store_true');a=p.parse_args()
    config=json.loads(Path(a.config).read_text());out=Path(a.output).resolve()
    assert out.is_relative_to((ROOT/'local-only').resolve()) and not out.exists(),'Choose a new local-only output directory'
    def loc(key):
        value=Path(config[key]);return value if value.is_absolute() else ROOT/value
    build=json.loads((loc('package')/'manifest.json').read_text());supported=supported_target(build)
    assert build['revision']=='independent-v12-candidate','Use the current runtime source build'
    assert not build.get('local_menu_font'),'User-supplied Zpix candidate is local-test-only; distribution is not authorized'
    registry_file=loc('build')/'CW3Localization/fonts.json'
    if registry_file.exists():
        from font_registry import load as load_fonts
        load_fonts(registry_file)
    assert not any(row['file']=='CW3Localization/text-style.json' for row in build.get('files',[])),'Rebuild without the retired settings template'
    validate_release_payload((row['file'] for row in build['files']),target_layout(build)['target_id'])
    out.mkdir(parents=True)
    for row in build['files']:
        name=row['file'];source=loc('build')/name
        assert sha(source)==row['after'] and source.stat().st_size==row['bytes'],name
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        assert sha(target)==row['after'],name
    from player_install import RUNTIME
    manifest=dict(format=2,name='CW3 简体中文补丁',version=build['patch_version'],runtime_files=sorted(RUNTIME & {r['file'] for r in build['files']}),exe_sha256=supported['exe_sha256'],target=target_description(supported),required_originals=build.get('required_originals',{}),files=build['files'])
    manifest.update(target_identity(supported))
    if 'controlled_fonts' in build:manifest['controlled_fonts']=build['controlled_fonts']
    for key in ('source_repo','source_commit','source_dirty','build_inputs_sha256'):
        if key in build:manifest[key]=build[key]
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    for dest,source in PLAYER_SOURCES.items():shutil.copy2(ROOT/source,out/dest)
    (out/'使用说明.txt').write_text(instructions(supported,manifest['version'],ROOT))
    assert {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}=={row['file'] for row in build['files']}|PLAYER_CONTROLS
    (out/'安装汉化.command').chmod(0o755)
    if not a.directory_only:
        archive=out.with_suffix(out.suffix+'.zip')
        assert not archive.exists(),'Keep existing packages'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for path in sorted(out.rglob('*'),key=lambda p:p.relative_to(out).as_posix()):
                if not path.is_file():continue
                name=path.relative_to(out).as_posix()
                # Filesystem mtime, timezone and permissions must not change the package.
                info=zipfile.ZipInfo(out.name+'/'+name,date_time=(1980,1,1,0,0,0))
                info.create_system=3
                info.external_attr=(0o100755 if name=='安装汉化.command' else 0o100644)<<16
                z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        print('Player ZIP:',archive,archive.stat().st_size,'bytes')
    print('Prepared',len(build['files']),'verified complete patch files')
if __name__=='__main__':main()
