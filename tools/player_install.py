"""CW3 player installer. Python 3.10+ standard library; macOS/CrossOver and Windows.

No shell interpolation, registry changes, elevation, downloads, or game launch.
A complete original backup and journal exist before the first game-file write.
"""
from pathlib import Path, PureWindowsPath
import argparse, csv, ctypes, hashlib, io, json, os, re, shutil, stat, subprocess, sys, tempfile
PACKAGE=Path(__file__).resolve().parent
BACKUP='.cw3-zh-backup'
RUNTIME={'CW3Localization/zh-CN.json'}
# Settings belong to the user, never to a new package. The exact legacy path
# remains readable while old backups transition to packages without a template.
SETTINGS={'CW3Localization/text-style.json'}
MUTABLE=RUNTIME|SETTINGS
EXTERNAL=MUTABLE|{'CW3Localization/font.ttf','CW3Localization/serif.ttf','CW3Localization/OFL.txt','CW3Localization/Serif-OFL.txt','CW3Localization/fonts.json','CW3Localization/Runtime/CW3ExternalRuntime.dll'}
WINDOWS='windows-steam-22453699'
MACOS='macos-steam-22453699'
TARGETS={
    WINDOWS:dict(platform=5,data_dir='CW3_Data',executable='CW3.exe'),
    MACOS:dict(platform=2,data_dir='CW3.app/Contents/Resources/Data',executable='CW3.app/Contents/MacOS/CW3'),
}
IDENTITY=('target_id','platform','data_dir','executable','exe_sha256')
# macOS changed this value during an authorized in-place write to CW3's
# Assembly-CSharp.dll. Its original and observed values stay in the backup
# record, but ordinary copying/writing cannot restore the original value.
# Presence is still required; quarantine and every other xattr stay exact.
SYSTEM_XATTR='com.apple.provenance'

def _darwin_xattr(operation,path,name=None,value=None):
    # Homebrew's Python on macOS may omit os.*xattr. Use libSystem directly
    # rather than dropping metadata from a backup or clearing quarantine.
    libc=ctypes.CDLL(None,use_errno=True)
    location=os.fsencode(path);attribute=os.fsencode(name) if name is not None else None
    if operation=='list':
        call=libc.listxattr;call.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
        arguments=(location,)
    elif operation=='get':
        call=libc.getxattr;call.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]
        arguments=(location,attribute)
    else:
        call=libc.setxattr;call.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]
        payload=ctypes.create_string_buffer(value,max(len(value),1))
        call.restype=ctypes.c_int
        if call(location,attribute,payload,len(value),0,0)<0:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()),str(path))
        return
    call.restype=ctypes.c_ssize_t
    size=call(*arguments,None,0,*((0,0) if operation=='get' else (0,)))
    if size<0:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()),str(path))
    buffer=ctypes.create_string_buffer(max(size,1))
    actual=call(*arguments,buffer,size,*((0,0) if operation=='get' else (0,)))
    if actual<0:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()),str(path))
    data=buffer.raw[:actual]
    return [os.fsdecode(part) for part in data.split(b'\0') if part] if operation=='list' else data

def list_xattrs(path):
    if hasattr(os,'listxattr'):return os.listxattr(path)
    if sys.platform=='darwin':return _darwin_xattr('list',path)
    raise RuntimeError('此环境无法读取文件扩展属性')

def get_xattr(path,name):
    if hasattr(os,'getxattr'):return os.getxattr(path,name)
    if sys.platform=='darwin':return _darwin_xattr('get',path,name)
    raise RuntimeError('此环境无法读取文件扩展属性')

def set_xattr(path,name,value):
    if hasattr(os,'setxattr'):return os.setxattr(path,name,value)
    if sys.platform=='darwin':return _darwin_xattr('set',path,name,value)
    raise RuntimeError('此环境无法写入文件扩展属性')

def target_layout(manifest=None):
    manifest=manifest or {};target_id=manifest.get('target_id',WINDOWS)
    if target_id not in TARGETS:raise ValueError('不支持的补丁目标')
    expected=TARGETS[target_id]
    # Only the old Windows manifest may omit target fields. Partial or mixed
    # target records cannot select a different filesystem layout.
    explicit='target_id' in manifest or any(k in manifest for k in expected)
    if explicit and (manifest.get('target_id')!=target_id or any(manifest.get(k)!=v for k,v in expected.items())):
        raise ValueError('补丁目标与平台/目录不一致')
    return dict(target_id=target_id,**expected)

def target_identity(manifest):
    result=target_layout(manifest)
    result['exe_sha256']=manifest.get('exe_sha256')
    if result['target_id']==MACOS and not re.fullmatch(r'[0-9a-f]{64}',result['exe_sha256'] or ''):
        raise ValueError('原生目标缺少可执行文件指纹')
    return result

def confined(root,name):
    target=root/name
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('游戏文件链接指向所选目录之外')
    return target

def installed_path(game,name,manifest=None):
    # Package and backup paths remain logical CW3_Data paths. This is the only
    # conversion to the selected installation; it never consults the host OS.
    safe(game,name);layout=target_layout(manifest)
    relative=Path(layout['data_dir']).joinpath(*Path(name).parts[1:]) if name.startswith('CW3_Data/') else Path(name)
    target=confined(game,relative)
    if layout['target_id']==MACOS:
        cursor=target
        while cursor!=game:
            if cursor.is_symlink():raise ValueError('原生游戏路径不能包含符号链接')
            cursor=cursor.parent
    return target

def check_game_identity(game,manifest):
    identity=target_identity(manifest)
    executable=confined(game,identity['executable']);data=confined(game,identity['data_dir'])
    if not executable.is_file() or not data.is_dir():raise RuntimeError('所选目录不包含补丁目标的游戏布局')
    if digest(executable)!=identity['exe_sha256']:
        if identity['target_id']==MACOS and (game/'CW3.app/Contents/_CodeSignature/CodeResources').exists():
            raise RuntimeError('原生签名后的可执行文件与原版指纹不同；此入口不更新已重签的包。请使用经过核验的 macos_adhoc_update.py 更新或恢复先前候选。')
        raise RuntimeError('游戏可执行文件版本不匹配；未写入游戏文件')
    if identity['target_id']==MACOS:
        if executable.is_symlink() or any(p.is_symlink() for p in executable.parents if p!=game and p.is_relative_to(game)):
            raise ValueError('原生游戏路径不能包含符号链接')
    return identity

def metadata(path):
    if not path.exists():return None
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise RuntimeError('元数据保护只支持普通文件：'+str(path))
    return dict(mode=stat.S_IMODE(info.st_mode),xattrs={name:get_xattr(path,name).hex() for name in sorted(list_xattrs(path))})

def recoverable_metadata_matches(actual,expected):
    if not isinstance(actual,dict) or not isinstance(expected,dict):return False
    if actual.get('mode')!=expected.get('mode'):return False
    current,recorded=actual.get('xattrs'),expected.get('xattrs')
    if not isinstance(current,dict) or not isinstance(recorded,dict):return False
    if (SYSTEM_XATTR in current)!=(SYSTEM_XATTR in recorded):return False
    return {k:v for k,v in current.items() if k!=SYSTEM_XATTR}=={k:v for k,v in recorded.items() if k!=SYSTEM_XATTR}

def apply_metadata(path,expected):
    # Work only on an owned temporary file. Never strip an attribute (including
    # quarantine) or change system policy to make a copy pass verification.
    if not isinstance(expected,dict) or set(expected)!={'mode','xattrs'} or type(expected['mode']) is not int or expected['mode']&~0o777:
        raise RuntimeError('无效或不支持的文件元数据')
    if not isinstance(expected['xattrs'],dict):raise RuntimeError('无效文件扩展属性')
    path.chmod(expected['mode'])
    present=set(list_xattrs(path))
    for name,value in expected['xattrs'].items():
        if name not in present or get_xattr(path,name).hex()!=value:
            set_xattr(path,name,bytes.fromhex(value))
    if metadata(path)!=expected:raise RuntimeError('无法完整保留文件权限/扩展属性；未替换目标文件')

def row_matches(game,row,side,manifest):
    path=installed_path(game,row['file'],manifest)
    if digest(path)!=row[side]:return False
    if row[side] is None:return True
    if target_layout(manifest)['target_id']!=MACOS or side+'_metadata' not in row:return True
    # During a first install a newly created file has no known system-assigned
    # attributes until its final directory entry exists. Its bytes remain fixed.
    return side=='after' and row['before'] is None and row['after_metadata'] is None or recoverable_metadata_matches(metadata(path),row[side+'_metadata'])

def digest(path):
    if not path.exists():return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def sync_directory(path):
    if sys.platform=='win32':return
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def read(path):return json.loads(path.read_text(encoding='utf8'))
def put_json(path,data):
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent);temp=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf8') as output:
            output.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n');output.flush();os.fsync(output.fileno())
        os.replace(temp,path);sync_directory(path.parent)
    finally:temp.unlink(missing_ok=True)
def safe(root,name):
    p=Path(name)
    if not isinstance(name,str) or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or not p.parts or (p.parts[0]!='CW3_Data' and p.as_posix() not in EXTERNAL):raise ValueError('补丁中存在不安全路径')
    return confined(root,p)

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

def discover(manifest=None):
    layout=target_layout(manifest)
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
        roots.append(Path.home()/'Library/Application Support/Steam')
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
        if (p/layout['executable']).is_file() and (p/layout['data_dir']).is_dir():unique[os.path.normcase(str(p.resolve()))]=p.resolve()
    return list(unique.values())

def choose_game(manifest=None):
    layout=target_layout(manifest);candidates=discover(manifest)
    for i,p in enumerate(candidates,1):print(f'{i}. {p}')
    print('选择编号，或粘贴包含 '+layout['executable']+' 的游戏目录。')
    value=input('游戏目录：').strip().strip('"').strip("'")
    if value.isdigit() and 1<=int(value)<=len(candidates):return candidates[int(value)-1]
    return Path(value).expanduser()

def idle():
    if sys.platform=='win32':
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq CW3.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True)
        running=any(row and row[0].lower()=='cw3.exe' for row in csv.reader(io.StringIO(result.stdout)))
    elif sys.platform=='darwin':
        result=subprocess.run(['pgrep','-fl',r'[C]W3[.]exe|[/]CW3[.]app/Contents/MacOS/(CW3|Menu Helper)( |$)'],capture_output=True,text=True)
        if result.returncode not in (0,1):raise RuntimeError('无法检查 CW3 进程，请退出游戏后重试')
        running=result.returncode==0
    else:raise RuntimeError('此安装入口仅支持 Windows 或 macOS')
    if running:raise RuntimeError('请先完全退出 CW3（包括其他 bottle 中的 CW3），再安装或恢复')

def ensure_writable(game,rows,required,manifest=None):
    if shutil.disk_usage(game).free<required:raise RuntimeError(f'空间不足：本操作需要约 {required//1048576+1} MiB 可用空间')
    folders={game}
    for f in rows:
        target=installed_path(game,f['file'],manifest)
        if target.exists() and not os.access(target,os.W_OK):raise RuntimeError('游戏文件不可写，请检查该安装目录的权限：'+str(target))
        folder=target.parent
        if not folder.is_dir():
            if f['file'] not in EXTERNAL or f['before'] is not None:raise RuntimeError('目录布局不完整：'+str(folder))
            # Only a manifest-declared new sidecar may create directories. Test
            # its nearest existing parent now; creation follows full staging.
            while not folder.exists():
                if folder.is_symlink():raise RuntimeError('新增目录路径不能是符号链接：'+str(folder))
                folder=folder.parent
            if not folder.is_dir():raise RuntimeError('目录布局不完整：'+str(folder))
        folders.add(folder)
    for folder in folders:
        try:
            fd,name=tempfile.mkstemp(prefix='.cw3-write-check-',dir=folder);os.close(fd);Path(name).unlink()
        except OSError as e:raise RuntimeError('目录不可写。请选择有写入权限的游戏目录；安装器不会自动提权：'+str(folder)) from e

def backup_info(game,manifest=None):
    folder=game/BACKUP
    if folder.is_symlink():raise RuntimeError('备份目录不能是符号链接')
    if not folder.exists():return None
    if not (folder/'state.json').is_file():raise RuntimeError('发现不完整备份目录，请保留它并人工检查')
    state=read(folder/'state.json')
    if os.path.normcase(state['install_root'])!=os.path.normcase(str(game.resolve())):raise RuntimeError('备份属于另一安装位置；拒绝跨目录恢复')
    identity=target_identity(state)
    if manifest and identity!=target_identity(manifest):
        # Existing Windows backups predate executable and layout identity.
        if identity['target_id']!=WINDOWS or 'target_id' in state or target_layout(manifest)['target_id']!=WINDOWS:
            raise RuntimeError('备份属于另一补丁目标；拒绝跨平台恢复')
    if identity['target_id']==MACOS:check_game_identity(game,state)
    for f in state['files']:
        original=safe(folder/'original',f['file'])
        if digest(original)!=f['before']:raise RuntimeError('原版备份校验失败：'+f['file'])
        if identity['target_id']==MACOS and not {'before_metadata','after_metadata'}<=f.keys():
            raise RuntimeError('原版备份元数据记录缺失：'+f['file'])
    return state

def required_originals_match(game,manifest):
    return all(digest(installed_path(game,name,manifest))==expected for name,expected in manifest.get('required_originals',{}).items())

def check_required_originals(game,manifest):
    if not required_originals_match(game,manifest):
        raise RuntimeError('未覆盖的资源不是原版；请先使用旧补丁的恢复入口还原原版，再安装本包')

def status(game,manifest,state):
    rows=manifest['files'];now={f['file']:digest(installed_path(game,f['file'],manifest)) for f in rows}
    if state and (game/BACKUP/'journal.json').exists():return 'interrupted'
    if not required_originals_match(game,manifest):return 'unknown'
    if state and target_layout(manifest)['target_id']==MACOS:
        for f in state['files']:
            if f['file'] not in MUTABLE and not any(row_matches(game,f,side,state) for side in ('before','after')):return 'unknown'
    if all(now[f['file']]==f['after'] for f in rows) and (not state or target_layout(manifest)['target_id']!=MACOS or all(row_matches(game,f,'after',state) for f in state['files'])):
        if state and any(f['file'] in SETTINGS for f in state['files']):return 'upgrade'
        return 'installed' if state else 'unmanaged'
    if state and all(row_matches(game,f,'after',state) for f in state['files']):return 'upgrade'
    if state and all(f['before'] is None for f in state['files'] if f['file'] in MUTABLE) and all(row_matches(game,f,'after',state) for f in state['files'] if f['file'] not in MUTABLE):return 'customized'
    if all(now[f['file']]==f['before'] for f in rows) and (not state or target_layout(manifest)['target_id']!=MACOS or all(row_matches(game,f,'before',state) for f in state['files'])):return 'original'
    return 'unknown'

def atomic_copy(source,target,expected_metadata=None):
    # Own an exclusive file in the destination directory; fixed temp names can
    # be pre-existing files or dangling links, and are never ours to overwrite.
    fd,name=tempfile.mkstemp(prefix='.'+target.name+'-',suffix='.cw3-install-tmp',dir=target.parent);temp=Path(name)
    try:
        with os.fdopen(fd,'wb') as output,source.open('rb') as input_:
            shutil.copyfileobj(input_,output);output.flush();os.fsync(output.fileno())
        if digest(source)!=digest(temp):raise RuntimeError('写入校验失败')
        if expected_metadata is not None:apply_metadata(temp,expected_metadata)
        os.replace(temp,target);sync_directory(target.parent)
    finally:temp.unlink(missing_ok=True)

def write_existing(source,target,expected_metadata):
    # Keep the inode and journal each write. macOS may update provenance even
    # in place; all other attributes, the mode and the exact bytes are guarded.
    if not recoverable_metadata_matches(metadata(target),expected_metadata):raise RuntimeError('目标文件可恢复元数据已变化：'+str(target))
    with source.open('rb') as input_,target.open('r+b') as output:
        output.seek(0);shutil.copyfileobj(input_,output);output.truncate();output.flush();os.fsync(output.fileno())
    if digest(target)!=digest(source) or not recoverable_metadata_matches(metadata(target),expected_metadata):
        raise RuntimeError('原生文件原位写入校验失败：'+str(target))

def journal_progress(folder,game,state,action,rows,name=None):
    record=journal_record(game,state,action,rows)
    if name is not None:record['in_progress']=name
    put_json(folder/'journal.json',record)

def preserve_runtime_updates(game,state,manifest):
    # Only whitelisted display-data files are mutable; assemblies/resources stay hash-locked.
    if status(game,manifest,state) not in ('customized','upgrade'):return state
    idle();rows=[dict(f) for f in state['files']];history=game/BACKUP/'runtime-updates'
    for f in rows:
        if f['file'] not in MUTABLE:continue
        source=installed_path(game,f['file'],state);current=digest(source)
        if current==f['after'] and row_matches(game,f,'after',state):continue
        if source.exists():
            if source.stat().st_size>50000000:raise RuntimeError('外部文件过大，请先人工保留并检查')
            if history.is_symlink():raise RuntimeError('外部文件备份目录不能是符号链接')
            history.mkdir(exist_ok=True);saved=history/(current+'-'+source.name)
            if not saved.exists():atomic_copy(source,saved)
            if digest(saved)!=current:raise RuntimeError('外部译文/设置备份校验失败')
        f['after']=current;f['bytes']=source.stat().st_size if source.exists() else 0
        if target_layout(state)['target_id']==MACOS:f['after_metadata']=metadata(source)
    if rows==state['files']:return state
    updated=dict(state,files=rows);put_json(game/BACKUP/'state.json',updated);return updated

def journal_record(game,state,action,rows):
    result=dict(action=action,files=rows)
    if target_layout(state)['target_id']==MACOS:
        result.update(target_identity(state));result['install_root']=str(game.resolve())
    return result

def restore(game,state):
    if not state:raise RuntimeError('没有属于此安装目录的原版备份；不能猜测恢复文件')
    if state.get('install_root')!=str(game.resolve()):raise RuntimeError('备份属于另一安装位置；拒绝跨目录恢复')
    native=target_layout(state)['target_id']==MACOS
    if native:check_game_identity(game,state)
    rows=state['files'];folder=game/BACKUP;journal=read(folder/'journal.json') if (folder/'journal.json').exists() else None
    if journal:
        if {f['file'] for f in journal['files']}-SETTINGS!={f['file'] for f in rows}-SETTINGS:raise RuntimeError('恢复日志文件清单不匹配')
        if native and (target_identity(journal)!=target_identity(state) or journal.get('install_root')!=str(game.resolve())):
            raise RuntimeError('恢复日志属于另一安装目标')
        if journal.get('in_progress') is not None and journal['in_progress'] not in {f['file'] for f in rows if f['before'] is not None}:
            raise RuntimeError('恢复日志中的进行中文件无效')
    pending={f['file']:f for f in journal['files']} if journal else {}
    for f in rows:
        if f['file'] in SETTINGS:continue
        candidates=[(f,'before'),(f,'after')]+([(pending[f['file']],'after')] if f['file'] in pending else [])
        if native and any(side+'_metadata' not in row for row,side in candidates):raise RuntimeError('恢复记录缺少文件元数据')
        partial=native and journal and journal.get('in_progress')==f['file'] and f['before'] is not None and recoverable_metadata_matches(metadata(installed_path(game,f['file'],state)),f['before_metadata'])
        if not partial and not any(row_matches(game,row,side,state) for row,side in candidates):raise RuntimeError('文件已被其他程序修改，拒绝覆盖：'+f['file'])
        original=safe(folder/'original',f['file'])
        if digest(original)!=f['before']:raise RuntimeError('原版备份校验失败：'+f['file'])
    if native and all(row_matches(game,f,'before',state) for f in rows if f['file'] not in SETTINGS):
        # A prior interrupted recovery may already have restored every byte.
        # Rewriting those inodes would needlessly change system provenance.
        idle();check_game_identity(game,state)
        if not all(row_matches(game,f,'before',state) for f in rows if f['file'] not in SETTINGS):
            raise RuntimeError('恢复结清期间游戏文件发生变化；已取消')
        if journal:(folder/'journal.json').unlink();sync_directory(folder)
        if any(f['before'] is not None and metadata(installed_path(game,f['file'],state))!=f['before_metadata'] for f in rows):
            print('原版字节、权限及可恢复扩展属性已核对；系统管理的 provenance 值可能变化。备份保留，存档未改动。')
        else:print('原版文件已核对。备份保留，存档未改动。')
        return
    idle();ensure_writable(game,rows,max(f['bytes'] for f in rows)+10485760,state)
    staging=Path(tempfile.mkdtemp(prefix='.cw3-zh-restore-',dir=game))
    try:
        # Capture every current byte/metadata pair before the first change.
        observed={f['file']:(digest(installed_path(game,f['file'],state)),metadata(installed_path(game,f['file'],state)) if native else None) for f in rows if f['file'] not in SETTINGS}
        for f in rows:
            if f['before'] is None or f['file'] in SETTINGS:continue
            target=safe(staging,f['file']);target.parent.mkdir(parents=True,exist_ok=True)
            atomic_copy(safe(folder/'original',f['file']),target)
        idle()
        if native:check_game_identity(game,state)
        for name,(before,meta) in observed.items():
            target=installed_path(game,name,state)
            if digest(target)!=before or native and metadata(target)!=meta:raise RuntimeError('恢复准备期间游戏文件发生变化；已取消')
        pending_name=journal.get('in_progress') if journal else None
        work=sorted(rows,key=lambda f:f['file']!=pending_name) if pending_name else rows
        # Retain an interrupted in-place write marker until that file is
        # restored; otherwise a second crash could strand its partial bytes.
        journal_progress(folder,game,state,'restore',journal['files'] if journal else rows,pending_name)
        for f in work:
            if f['file'] in SETTINGS:continue
            target=installed_path(game,f['file'],state)
            if f['before'] is None:target.unlink(missing_ok=True)
            elif native:
                journal_progress(folder,game,state,'restore',journal['files'] if journal else rows,f['file'])
                write_existing(safe(staging,f['file']),target,f['before_metadata'])
                journal_progress(folder,game,state,'restore',journal['files'] if journal else rows)
            else:atomic_copy(safe(staging,f['file']),target)
        if any(not row_matches(game,f,'before',state) for f in rows if f['file'] not in SETTINGS):raise RuntimeError('恢复后校验失败；原备份保留')
        (folder/'journal.json').unlink()
        if native and any(f['before'] is not None and metadata(installed_path(game,f['file'],state))!=f['before_metadata'] for f in rows):
            print('原版字节、权限及可恢复扩展属性已恢复；系统管理的 provenance 值可能变化。备份保留，存档未改动。')
        else:print('已恢复原版。备份保留，存档未改动。')
    finally:shutil.rmtree(staging)

def install(game,manifest,state,package=PACKAGE):
    native=target_layout(manifest)['target_id']==MACOS
    if native:
        check_game_identity(game,manifest)
        # This generic installer cannot retain a valid sealed signature after
        # changing Data. Signed candidates use the separately guarded local
        # updater; a bundle change may require another macOS launch approval.
        if (game/'CW3.app/Contents/_CodeSignature/CodeResources').exists():
            raise RuntimeError('原生 CW3.app 含封印签名；此通用入口拒绝修改。已签名候选使用 macos_adhoc_update.py 核验更新；包内变化才重签。')
    if state:
        if state.get('install_root')!=str(game.resolve()):raise RuntimeError('备份属于另一安装位置；拒绝跨目录安装')
        if native and target_identity(state)!=target_identity(manifest) or not native and target_layout(state)['target_id']!=WINDOWS:
            raise RuntimeError('备份属于另一补丁目标；拒绝跨平台安装')
    check_required_originals(game,manifest)
    rows=[dict(f) for f in manifest['files']]
    if any(f['file'] in SETTINGS for f in rows):raise RuntimeError('此包包含旧设置模板，请使用新版完整包')
    current=status(game,manifest,state)
    if current=='installed':print('此版本已经安装，全部文件校验通过。');return
    if current=='unmanaged':raise RuntimeError('检测到已安装的汉化，但不由本安装器备份管理。无需重复安装；若要更换版本，请先用旧恢复入口还原原版。')
    if current=='interrupted':raise RuntimeError('检测到中断的安装/恢复，请先选择恢复原版，再安装')
    if current not in ('original','upgrade','customized'):raise RuntimeError('版本不匹配或文件已被修改；未写入游戏文件')
    if state and (any(f['before'] is not None for f in state['files'] if f['file'] in SETTINGS) or {f['file']:f['before'] for f in state['files'] if f['file'] not in SETTINGS}!={f['file']:f['before'] for f in rows}):raise RuntimeError('不支持跨版本升级。请先用旧入口恢复原版并另存旧备份目录，再安装本包')
    if state:state=preserve_runtime_updates(game,state,manifest)
    if native:
        previous={f['file']:f for f in state['files']} if state else {}
        for f in rows:
            f['before_metadata']=previous[f['file']]['before_metadata'] if state else metadata(installed_path(game,f['file'],manifest))
            # Existing files retain their inode and metadata; newly created
            # files receive system attributes only at their final location.
            f['after_metadata']=f['before_metadata'] if f['before'] else None
    idle();required=sum(f['bytes'] for f in rows)+max(f['bytes'] for f in rows)+10485760
    if not state:required+=sum(installed_path(game,f['file'],manifest).stat().st_size for f in rows if f['before'])
    ensure_writable(game,rows,required,manifest)
    observed={f['file']:(digest(installed_path(game,f['file'],manifest)),metadata(installed_path(game,f['file'],manifest)) if native else None) for f in rows}
    staging=Path(tempfile.mkdtemp(prefix='.cw3-zh-stage-',dir=game));folder=game/BACKUP
    try:
        # Construct and verify every output before any game-file mutation.
        for f in rows:
            payload=safe(package,f['file'])
            if digest(payload)!=f['after'] or payload.stat().st_size!=f['bytes']:raise RuntimeError('安装包损坏：'+f['file'])
            original=safe(folder/'original',f['file']) if state else installed_path(game,f['file'],manifest)
            if f['before'] and (digest(original)!=f['before'] or native and not state and metadata(original)!=f['before_metadata']):raise RuntimeError('原版不匹配：'+f['file'])
            target=safe(staging,f['file']);target.parent.mkdir(parents=True,exist_ok=True)
            atomic_copy(payload,target)
            if digest(target)!=f['after']:raise RuntimeError('补丁输出校验失败：'+f['file'])
        if not state:
            preparing=staging/'backup';preparing.mkdir();state={'format':1,'install_root':str(game.resolve()),'version':manifest['version'],'files':rows}
            if native or 'target_id' in manifest:state.update(target_identity(manifest))
            for f in rows:
                if f['before']:
                    dst=safe(preparing/'original',f['file']);dst.parent.mkdir(parents=True,exist_ok=True)
                    atomic_copy(installed_path(game,f['file'],manifest),dst)
                    if digest(dst)!=f['before']:raise RuntimeError('备份写入校验失败')
            put_json(preparing/'state.json',state);os.replace(preparing,folder);sync_directory(game)
        # Recheck both bytes and metadata after the potentially slow stage.
        idle();check_required_originals(game,manifest)
        if native:check_game_identity(game,manifest)
        for name,(before,meta) in observed.items():
            target=installed_path(game,name,manifest)
            if digest(target)!=before or native and metadata(target)!=meta:raise RuntimeError('准备期间游戏文件发生变化；已取消')
        journal_progress(folder,game,state,'install',rows)
        try:
            for f in rows:
                target=installed_path(game,f['file'],manifest);target.parent.mkdir(parents=True,exist_ok=True)
                if native and f['before'] is not None:
                    journal_progress(folder,game,state,'install',rows,f['file'])
                    write_existing(safe(staging,f['file']),target,f['before_metadata'])
                    f['after_metadata']=metadata(target)
                    journal_progress(folder,game,state,'install',rows)
                else:atomic_copy(safe(staging,f['file']),target)
                if native and f['before'] is None:f['after_metadata']=metadata(target)
            if any(not row_matches(game,f,'after',manifest) for f in rows):raise RuntimeError('安装后校验失败')
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
    game=(Path(a.game).expanduser() if a.game else choose_game(manifest)).resolve()
    check_game_identity(game,manifest)
    state=backup_info(game,manifest);current=status(game,manifest,state);print('目录：',game);print('状态：',current)
    action=a.action
    if not action:
        value=input('1 安装/更新汉化   2 恢复原版   其他键退出：').strip();action={'1':'install','2':'restore'}.get(value)
    if action=='install':install(game,manifest,state)
    elif action=='restore':
        restore(game,preserve_runtime_updates(game,state,manifest) if state else state)
    elif action=='status':print('仅检查，未写入游戏。')
if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as error:print('\n未完成：'+str(error));sys.exit(1)
