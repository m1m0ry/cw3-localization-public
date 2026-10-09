"""CW3 player installer. Python 3.10+ standard library; macOS/CrossOver and Windows.

No shell interpolation, registry changes, elevation, downloads, or game launch.
A complete original backup and journal exist before the first game-file write.
"""
from pathlib import Path, PureWindowsPath
import argparse, csv, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, uuid
PACKAGE=Path(__file__).resolve().parent
BACKUP='.cw3-zh-backup'
RUNTIME={'CW3Localization/zh-CN.json','CW3Localization/font.ttf'}
EXTERNAL=RUNTIME|{'CW3Localization/OFL.txt'}
def digest(path):
    if not path.exists():return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf8'))
def put_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
def safe(root,name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or (p.parts[0]!='CW3_Data' and p.as_posix() not in EXTERNAL):raise ValueError('补丁中存在不安全路径')
    target=root/p
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('游戏文件链接指向所选目录之外')
    return target

def library_paths(text):
    # Steam libraryfolders.vdf: current "path" records and legacy numeric strings.
    result=[]
    for key,value in re.findall(r'"([^"\n]+)"\s*"((?:\\.|[^"\\])*)"',text):
        if key=='path' or key.isdigit():
            value=value.replace('\\\\','\\').replace('\\"','"')
            if value.startswith('/') or re.match(r'^[A-Za-z]:[\\/]',value):result.append(value)
    return result

def bottle_path(path,bottle):
    p=PureWindowsPath(path)
    if not p.drive:return Path(path)
    drive=p.drive[0].lower();base=bottle/'drive_c' if drive=='c' else bottle/'dosdevices'/(drive+':')
    return base.joinpath(*p.parts[1:])

def discover():
    roots=[];bottles={};candidates=[Path.cwd(),PACKAGE.parent]
    if sys.platform=='win32':
        import winreg
        for hive,key,field in [(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Valve\Steam','InstallPath')]:
            try:
                with winreg.OpenKey(hive,key) as handle:roots.append(Path(winreg.QueryValueEx(handle,field)[0]))
            except OSError:pass
        for name in ('ProgramFiles(x86)','ProgramFiles'):
            if os.environ.get(name):roots.append(Path(os.environ[name])/'Steam')
    elif sys.platform=='darwin':
        for base in (Path.home()/'Library/Application Support/CrossOver/Bottles',Path.home()/'Library/Application Support/CrossOver Preview/Bottles'):
            if base.exists():
                for bottle in base.iterdir():
                    for folder in ('Program Files (x86)','Program Files'):
                        root=bottle/'drive_c'/folder/'Steam';roots.append(root);bottles[root]=bottle
    for root in roots:
        libraries=[root];vdf=root/'steamapps/libraryfolders.vdf'
        if vdf.is_file():
            for value in library_paths(vdf.read_text(encoding='utf8',errors='replace')):
                libraries.append(bottle_path(value,bottles[root]) if root in bottles else Path(value))
        candidates += [p/'steamapps/common/Creeper World 3' for p in libraries]
    unique={}
    for p in candidates:
        if (p/'CW3.exe').is_file() and (p/'CW3_Data').is_dir():unique[os.path.normcase(str(p.resolve()))]=p.resolve()
    return list(unique.values())

def choose_game():
    candidates=discover()
    for i,p in enumerate(candidates,1):print(f'{i}. {p}')
    print('选择编号，或粘贴包含 CW3.exe 与 CW3_Data 的游戏目录。自定义 Steam 库/CrossOver bottle 可直接指定。')
    value=input('游戏目录：').strip().strip('"').strip("'")
    if value.isdigit() and 1<=int(value)<=len(candidates):return candidates[int(value)-1]
    return Path(value).expanduser()

def idle():
    if sys.platform=='win32':
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq CW3.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True)
        running=any(row and row[0].lower()=='cw3.exe' for row in csv.reader(io.StringIO(result.stdout)))
    elif sys.platform=='darwin':
        result=subprocess.run(['pgrep','-fl',r'[C]W3[.]exe|[/]CW3[.]app/Contents/MacOS/Menu Helper'],capture_output=True,text=True)
        if result.returncode not in (0,1):raise RuntimeError('无法检查 CW3 进程，请退出游戏后重试')
        running=result.returncode==0
    else:raise RuntimeError('此安装入口仅支持 Windows 或 macOS 上的 CrossOver Windows 版')
    if running:raise RuntimeError('请先完全退出 CW3（包括其他 bottle 中的 CW3），再安装或恢复')

def ensure_writable(game,rows,required):
    if shutil.disk_usage(game).free<required:raise RuntimeError(f'空间不足：本操作需要约 {required//1048576+1} MiB 可用空间')
    for f in rows:
        target=safe(game,f['file'])
        if target.exists() and not os.access(target,os.W_OK):raise RuntimeError('游戏文件不可写，请检查该安装目录的权限：'+str(target))
    for folder in {game}|{safe(game,f['file']).parent for f in rows}:
        if not folder.is_dir():
            if folder==game/'CW3Localization' and all(f['before'] is None for f in rows if f['file'].startswith('CW3Localization/')):folder=game
            else:raise RuntimeError('目录布局不完整：'+str(folder))
        try:
            fd,name=tempfile.mkstemp(prefix='.cw3-write-check-',dir=folder);os.close(fd);Path(name).unlink()
        except OSError as e:raise RuntimeError('目录不可写。请选择有写入权限的游戏目录；安装器不会自动提权：'+str(folder)) from e

def backup_info(game):
    folder=game/BACKUP
    if folder.is_symlink():raise RuntimeError('备份目录不能是符号链接')
    if not folder.exists():return None
    if not (folder/'state.json').is_file():raise RuntimeError('发现不完整备份目录，请保留它并人工检查')
    state=read(folder/'state.json')
    if os.path.normcase(state['install_root'])!=os.path.normcase(str(game.resolve())):raise RuntimeError('备份属于另一安装位置；拒绝跨目录恢复')
    for f in state['files']:
        if digest(safe(folder/'original',f['file']))!=f['before']:raise RuntimeError('原版备份校验失败：'+f['file'])
    return state

def required_originals_match(game,manifest):
    return all(digest(safe(game,name))==expected for name,expected in manifest.get('required_originals',{}).items())

def check_required_originals(game,manifest):
    if not required_originals_match(game,manifest):
        raise RuntimeError('未覆盖的资源不是原版；请先使用旧补丁的恢复入口还原原版，再安装本包')

def status(game,manifest,state):
    rows=manifest['files'];now={f['file']:digest(safe(game,f['file'])) for f in rows}
    if state and (game/BACKUP/'journal.json').exists():return 'interrupted'
    if not required_originals_match(game,manifest):return 'unknown'
    if all(now[f['file']]==f['after'] for f in rows):return 'installed' if state else 'unmanaged'
    if state and all(digest(safe(game,f['file']))==f['after'] for f in state['files']):return 'upgrade'
    runtime=set(manifest.get('runtime_files',[])) & RUNTIME
    if state and runtime and {f['file'] for f in state['files']}=={f['file'] for f in rows} and all(f['before'] is None for f in state['files'] if f['file'] in runtime) and all(digest(safe(game,f['file']))==f['after'] for f in state['files'] if f['file'] not in runtime):return 'customized'
    if all(now[f['file']]==f['before'] for f in rows):return 'original'
    legacy=manifest.get('legacy_hashes',{})
    if all(now[f['file']]==legacy.get(f['file']) for f in rows):return 'legacy'
    return 'unknown'

def atomic_copy(source,target):
    temp=target.with_name(target.name+'.cw3-install-tmp')
    if temp.exists():raise RuntimeError('存在未完成的临时文件，请先保留并检查：'+str(temp))
    try:
        shutil.copyfile(source,temp)
        if digest(source)!=digest(temp):raise RuntimeError('写入校验失败')
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)

def preserve_runtime_updates(game,state,manifest):
    # Only the two introduced display-data files are mutable; assemblies/resources stay hash-locked.
    if status(game,manifest,state)!='customized':return state
    idle();rows=[dict(f) for f in state['files']];history=game/BACKUP/'runtime-updates'
    for f in rows:
        if f['file'] not in RUNTIME:continue
        source=safe(game,f['file']);current=digest(source)
        if current==f['after']:continue
        if source.exists():
            if source.stat().st_size>50000000:raise RuntimeError('外部文件过大，请先人工保留并检查')
            if history.is_symlink():raise RuntimeError('外部文件备份目录不能是符号链接')
            history.mkdir(exist_ok=True);saved=history/(current+'-'+source.name)
            if not saved.exists():atomic_copy(source,saved)
            if digest(saved)!=current:raise RuntimeError('外部译文/字体备份校验失败')
        f['after']=current;f['bytes']=source.stat().st_size if source.exists() else 0
    updated=dict(state,files=rows);put_json(game/BACKUP/'state.json',updated);return updated

def restore(game,state):
    if not state:raise RuntimeError('没有属于此安装目录的原版备份；不能猜测恢复文件')
    rows=state['files'];folder=game/BACKUP;journal=read(folder/'journal.json') if (folder/'journal.json').exists() else None
    allowed={f['file']:{f['before'],f['after']} for f in rows}
    if journal:
        for f in journal['files']:allowed[f['file']].add(f['after'])
    for f in rows:
        if digest(safe(game,f['file'])) not in allowed[f['file']]:raise RuntimeError('文件已被其他程序修改，拒绝覆盖：'+f['file'])
    idle();ensure_writable(game,rows,max(f['bytes'] for f in rows)+10485760)
    if journal:
        for f in rows:
            temporary=safe(game,f['file']).with_name(Path(f['file']).name+'.cw3-install-tmp')
            if temporary.is_symlink():raise RuntimeError('恢复临时文件是符号链接，拒绝处理')
            temporary.unlink(missing_ok=True)
    put_json(folder/'journal.json',{'action':'restore','files':journal['files'] if journal else rows})
    for f in rows:
        target=safe(game,f['file'])
        if f['before'] is None:target.unlink(missing_ok=True)
        else:atomic_copy(safe(folder/'original',f['file']),target)
    if any(digest(safe(game,f['file']))!=f['before'] for f in rows):raise RuntimeError('恢复后校验失败；原备份保留')
    (folder/'journal.json').unlink();print('已恢复原版。备份保留，存档未改动。')

def install(game,manifest,state,package=PACKAGE):
    check_required_originals(game,manifest)
    rows=manifest['files'];current=status(game,manifest,state)
    if current=='installed':print('此版本已经安装，全部文件校验通过。');return
    if current=='customized':print('基础补丁已安装；检测到外部词典/字体更新，保留当前文件。');return
    if current in ('legacy','unmanaged'):raise RuntimeError('检测到已安装的汉化，但不由本安装器备份管理。无需重复安装；若要更换版本，请先用旧恢复入口还原原版。')
    if current=='interrupted':raise RuntimeError('检测到中断的安装/恢复，请先选择恢复原版，再安装')
    if current not in ('original','upgrade'):raise RuntimeError('版本不匹配或文件已被修改；未写入游戏文件')
    if state and {f['file']:f['before'] for f in state['files']}!={f['file']:f['before'] for f in rows}:raise RuntimeError('不支持跨版本升级。请先用旧入口恢复原版并另存旧备份目录，再安装本包')
    idle();required=sum(f['bytes'] for f in rows)+max(f['bytes'] for f in rows)+10485760
    if not state:required+=sum(safe(game,f['file']).stat().st_size for f in rows if f['before'])
    ensure_writable(game,rows,required)
    staging=Path(tempfile.mkdtemp(prefix='.cw3-zh-stage-',dir=game));folder=game/BACKUP
    try:
        # Construct and verify every output before any game-file mutation.
        source=folder/'original' if state else game
        for f in rows:
            payload=safe(package,f['file'])
            if digest(payload)!=f['after'] or payload.stat().st_size!=f['bytes']:raise RuntimeError('安装包损坏：'+f['file'])
            original=safe(source,f['file'])
            if f['before'] and digest(original)!=f['before']:raise RuntimeError('原版不匹配：'+f['file'])
            target=safe(staging,f['file']);target.parent.mkdir(parents=True,exist_ok=True);atomic_copy(payload,target)
            if digest(target)!=f['after']:raise RuntimeError('补丁输出校验失败：'+f['file'])
        if not state:
            preparing=staging/'backup';preparing.mkdir();state={'format':1,'install_root':str(game.resolve()),'version':manifest['version'],'files':rows}
            for f in rows:
                if f['before']:
                    dst=safe(preparing/'original',f['file']);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(game,f['file']),dst)
                    if digest(dst)!=f['before']:raise RuntimeError('备份写入校验失败')
            put_json(preparing/'state.json',state);os.replace(preparing,folder)
        # Recheck after the potentially slow build/backup stage.
        idle();check_required_originals(game,manifest);expected={f['file']:(f['before'] if current=='original' else f['after']) for f in state['files']}
        if any(digest(safe(game,n))!=h for n,h in expected.items()):raise RuntimeError('准备期间游戏文件发生变化；已取消')
        put_json(folder/'journal.json',{'action':'install','files':rows})
        try:
            for f in rows:
                target=safe(game,f['file']);target.parent.mkdir(parents=True,exist_ok=True);atomic_copy(safe(staging,f['file']),target)
            if any(digest(safe(game,f['file']))!=f['after'] for f in rows):raise RuntimeError('安装后校验失败')
            check_required_originals(game,manifest)
            state=dict(state,version=manifest['version'],files=rows);put_json(folder/'state.json',state);(folder/'journal.json').unlink()
        except BaseException:
            print('写入中断，正在从已验证备份恢复原版。');restore(game,state);raise
        print('安装完成，'+str(len(rows))+' 个文件校验通过。现在可以从 Steam 启动游戏。')
    finally:shutil.rmtree(staging)

def main():
    if not __debug__:raise RuntimeError('请勿以 Python 优化模式运行安装器')
    if sys.version_info<(3,10):raise RuntimeError('需要 Python 3.10 或更新版本（无需其他 Python 包）')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--game');p.add_argument('--action',choices=('install','restore','status'));a=p.parse_args();manifest=read(PACKAGE/'manifest.json')
    if manifest.get('format')!=2:raise RuntimeError('此入口需要完整文件包；旧差分包请使用其自带恢复入口')
    game=(Path(a.game).expanduser() if a.game else choose_game()).resolve()
    if not (game/'CW3.exe').is_file() or not (game/'CW3_Data').is_dir():raise RuntimeError('请选择包含 CW3.exe 和 CW3_Data 的 Windows 游戏目录；不支持原生 Mac 版')
    if digest(game/'CW3.exe')!=manifest['exe_sha256']:raise RuntimeError('CW3.exe 版本不匹配；仅支持 '+manifest['target'])
    state=backup_info(game);current=status(game,manifest,state);print('目录：',game);print('状态：',current)
    action=a.action
    if not action:
        value=input('1 安装/更新汉化   2 恢复原版   其他键退出：').strip();action={'1':'install','2':'restore'}.get(value)
    if action=='install':install(game,manifest,state)
    elif action=='restore':restore(game,preserve_runtime_updates(game,state,manifest) if state else state)
    elif action=='status':print('仅检查，未写入游戏。')
if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as error:print('\n未完成：'+str(error));sys.exit(1)
