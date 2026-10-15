"""Package verified complete patch files with the offline install/restore entry point."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
from player_install import MACOS, WINDOWS, target_identity, target_layout
ROOT=Path(__file__).resolve().parents[1]
PLAYER_SOURCES={'install.py':'tools/player_install.py','安装或恢复.command':'player/安装或恢复.command','安装或恢复.cmd':'player/安装或恢复.cmd','OFL.txt':'fonts/OFL.txt','LICENSE':'LICENSE','NOTICE.md':'NOTICE.md','字体设置.md':'docs/text-style.md'}
PLAYER_CONTROLS=set(PLAYER_SOURCES)|{'manifest.json','使用说明.txt'}
# Independent of generated manifests: only these fixed-target patch files may
# ship. A self-consistent manifest must not authorize debug modules or logs.
RELEASE_PAYLOAD={
    'CW3_Data/Managed/Assembly-CSharp.dll','CW3_Data/Managed/CW3Rendering.dll','CW3_Data/Managed/CW3Runtime.dll',
    'CW3_Data/level2','CW3_Data/level3','CW3_Data/mainData','CW3_Data/sharedassets0.assets','CW3_Data/sharedassets2.assets',
    'CW3Localization/zh-CN.json','CW3Localization/font.ttf','CW3Localization/serif.ttf','CW3Localization/Runtime/CW3ExternalRuntime.dll',
    'CW3Localization/OFL.txt','CW3Localization/Serif-OFL.txt','CW3Localization/fonts.json'}
def validate_release_payload(names,target_id=None):
    names=list(names);unexpected=set(names)-RELEASE_PAYLOAD
    if unexpected:raise ValueError('Unexpected release payload: '+', '.join(sorted(unexpected)))
    external='CW3Localization/Runtime/CW3ExternalRuntime.dll'
    if target_id==MACOS and external not in names:raise ValueError('Native Mac package lacks the fixed external runtime')
    if target_id==WINDOWS and external in names:raise ValueError('Windows package cannot contain the native external runtime')
    if not names or len(names)!=len(set(names)):raise ValueError('Empty or duplicate release payload')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def target_description(supported):
    return ('macOS native Steam ' if target_layout(supported)['target_id']==MACOS else 'Windows Steam ')+supported['version'].removesuffix(' Steam')+' / build '+supported['steam_build']+' / Unity '+supported['unity_version']

def supported_target(build):
    layout=target_layout(build)
    name='macos-target.json' if layout['target_id']==MACOS else 'supported-build.json'
    supported=json.loads((ROOT/'resources'/name).read_text())
    if target_layout(supported)!=layout:raise ValueError('Build/profile target mismatch')
    if layout['target_id']==MACOS and target_identity(build)!=target_identity(supported):raise ValueError('Build/profile executable fingerprint mismatch')
    return supported

def instructions(supported,version,root=ROOT):
    if target_layout(supported)['target_id']!=MACOS:
        return (root/'player/使用说明-v12.txt').read_text().replace(' v12\n',' '+version+'\n',1)
    return ('CW3 简体中文补丁 '+version+'\n适用 '+target_description(supported)+'。\n\n'
            '这是原生 Mac 桥接候选；已验证 Steam 启动、包外运行时载入、2232 条译文、四角色保存与取消、即时字号及重启切换字体。菜单、字体设置和自然播放的序章有脚本截图证据；完整教程对话和真实鼠标命中仍待验收。\n'
            'Steam CW3.app 带封印签名，通用「安装或恢复.command」仍会拒绝修改。已安装且经 ad-hoc 重签的旧候选，可在完全退出游戏后用源码工作区 tools/macos_adhoc_update.py 核验并更新：它保留上一版和签名快照，只有包内变化才做最小重签；仅外置运行时、登记表或词典变化时不执行签名命令。不要手工合并覆盖、清除属性或调整系统安全设置；新签名可能需要在系统设置中再次放行。\n'
            '包内 CW3_Data 是逻辑路径，由安装器映射到 CW3.app/Contents/Resources/Data；不要手工合并覆盖。\n'
            '安装器核对目标指纹，保存文件字节、权限和扩展属性记录。macOS 可能自动更新 com.apple.provenance 的值；此值会记录但不会伪造。其存在性、quarantine 和其他扩展属性仍严格校验。保留游戏目录的 .cw3-zh-backup，恢复使用同一入口。\n'
            '安装器不修改签名策略或存档，不删除 quarantine。签名更新入口只重签 CW3.app。\n\n'
            'CW3Localization 与 CW3.app 同级，包含词典、受控字体和固定位置的 CW3ExternalRuntime.dll；配置、状态与缓存由运行时写到 persistentDataPath/CW3Localization。包内 CW3Runtime.dll 是固定桥接层；必要 Unity 资源、显示调用补丁和渲染辅助仍在包内。外置 DLL 以当前游戏用户权限执行，须仅在受信任的本机用户目录更新。桥接层限制路径、所有者、链接及其他用户的写权限；加载失败时回退原文并显示失败提示。\n'
            '正文、标题/角色名、界面和状态值均可独立配置；字号保存后即时生效，字体切换重启生效。默认 sans、100%；用户已有 Zpix 的原生加载、菜单显示和固定离屏缺字回退已验证，用户字体不随包提供。\n'
            '译文只改 zh-CN.json 的 translation，保留 ID、原文、标签和占位符。退出游戏后更新，重启生效。\n'
            '文件哈希见 manifest.json，字体许可见 OFL.txt 和 CW3Localization/Serif-OFL.txt。\n')
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
        assert set(load_fonts(registry_file)['fonts'])=={'sans','serif'},'Imported user fonts are local-only; never package their bytes'
    assert not any(row['file']=='CW3Localization/text-style.json' for row in build.get('files',[])),'Rebuild without the retired settings template'
    validate_release_payload((row['file'] for row in build['files']),target_layout(build)['target_id'])
    out.mkdir(parents=True)
    for row in build['files']:
        name=row['file'];source=loc('build')/name
        assert sha(source)==row['after'] and source.stat().st_size==row['bytes'],name
        if row['before']:assert sha(loc('original')/name)==row['before'],name
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
    (out/'安装或恢复.command').chmod(0o755)
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
                info.external_attr=(0o100755 if name=='安装或恢复.command' else 0o100644)<<16
                z.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        print('Player ZIP:',archive,archive.stat().st_size,'bytes')
    print('Prepared',len(build['files']),'verified complete patch files')
if __name__=='__main__':main()
