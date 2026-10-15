"""CW3 player installer. Python 3.10+ standard library; macOS/CrossOver and Windows.

No shell interpolation, registry changes, elevation, downloads, or game launch.
A complete package is reapplied after interruption; user data is never replaced.
"""
from pathlib import Path, PureWindowsPath
import argparse, csv, ctypes, hashlib, io, json, os, re, shutil, stat, subprocess, sys, tempfile, struct
PACKAGE=Path(__file__).resolve().parent
DEFAULT_DICTIONARY='CW3Localization/zh-CN.default.json'
LEGACY_DICTIONARY='CW3Localization/zh-CN.json'
USER_DICTIONARY='CW3Localization/zh-CN.user.json'
RUNTIME={DEFAULT_DICTIONARY}
USER_FILES={USER_DICTIONARY,'CW3Localization/text-style.json'}
EXTERNAL=USER_FILES|RUNTIME|{LEGACY_DICTIONARY,'CW3Localization/font.ttf','CW3Localization/serif.ttf','CW3Localization/OFL.txt','CW3Localization/Serif-OFL.txt','CW3Localization/fonts.json','CW3Localization/Runtime/CW3ExternalRuntime.dll'}
PAYLOAD={'CW3_Data/Managed/Assembly-CSharp.dll','CW3_Data/Managed/CW3Rendering.dll','CW3_Data/Managed/CW3Runtime.dll','CW3_Data/level2','CW3_Data/level3','CW3_Data/mainData','CW3_Data/sharedassets0.assets','CW3_Data/sharedassets2.assets'}|(EXTERNAL-USER_FILES-{LEGACY_DICTIONARY})
# SHA256 of translations/zh-CN.json, read from these immutable public commits.
OFFICIAL_LEGACY_DICTIONARIES={
    '2991d0527bfee047b7913396478394e8a9936080d4921f5108c55b6a4e098ee7', # 9eaec151cfba9a6c27a949e5389dfcf70e65ae74
    '433eab06596e9e8c137985796b2a34fbdf1efffbe7f29f699b0d2f15d43ccb25', # eac358661245172c0555075d1e373bd3304b28f4
    '1cbeeb7f0574297b82ecb8efc72dbf1d5c6c6f50878cc1f4539d20a9d37dcabb', # a4100573e68ed3e277f8ebd20c3194e40fec20a6
}
ADDED='CW3Localization/Runtime/CW3ExternalRuntime.dll'
# Only injected files belong to cleanup. Steam owns its original DLL/assets.
INJECTED={'CW3_Data/Managed/'+name for name in ('CW3Rendering.dll','CW3Runtime.dll','CW3Debug.dll','CW3Display.dll')}|(EXTERNAL-USER_FILES-{LEGACY_DICTIONARY})
WINDOWS='windows-steam-22453699'
MACOS='macos-steam-22453699'
TARGETS={
    WINDOWS:dict(platform=5,data_dir='CW3_Data',executable='CW3.exe'),
    MACOS:dict(platform=2,data_dir='CW3.app/Contents/Resources/Data',executable='CW3.app/Contents/MacOS/CW3'),
}
# macOS may update provenance during an in-place write. Its presence and all
# other xattrs/modes remain protected; no security attribute is removed.
SYSTEM_XATTR='com.apple.provenance'

def _darwin_xattr(operation,path,name=None):
    # Homebrew Python may omit os.*xattr; read the same metadata via libSystem.
    libc=ctypes.CDLL(None,use_errno=True)
    location=os.fsencode(path);attribute=os.fsencode(name) if name is not None else None
    if operation=='list':
        call=libc.listxattr;call.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
        arguments=(location,)
    else:
        call=libc.getxattr;call.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]
        arguments=(location,attribute)
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

def target_layout(manifest):
    target_id=manifest.get('target_id')
    if target_id not in TARGETS:raise ValueError('补丁必须声明受支持的目标')
    expected=TARGETS[target_id]
    if any(manifest.get(k)!=v for k,v in expected.items()):raise ValueError('补丁目标与平台/目录不一致')
    return dict(target_id=target_id,**expected)

def target_identity(manifest):
    result=target_layout(manifest)
    result['exe_sha256']=manifest.get('exe_sha256')
    if not re.fullmatch(r'[0-9a-f]{64}',result['exe_sha256'] or ''):
        raise ValueError('目标缺少可执行文件指纹')
    return result

def confined(root,name):
    target=root/name
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('文件路径超出所选目录')
    cursor=target
    while cursor!=root:
        if cursor.is_symlink() or cursor.exists() and getattr(cursor.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError('补丁路径不能包含链接')
        cursor=cursor.parent
    return target

def installed_path(game,name,manifest):
    safe(game,name);layout=target_layout(manifest)
    relative=Path(layout['data_dir']).joinpath(*Path(name).parts[1:]) if name.startswith('CW3_Data/') else Path(name)
    return confined(game,relative)

# The fixed Steam build has two Intel slices. Ignore only signature sizes and
# __LINKEDIT sizes changed by codesign; every code byte and slice identity stays locked.
FINGERPRINTS={WINDOWS:'e738a7ee12e2eafb48366e84f8cd089c4433d2a2223954f3642a1c71ce80e456',MACOS:'67e5badb2cc8cc8a5a58974af9d8de1d8f4ebca051d63a0f4939e51c68176564'}
MAC_CODE='3e74586350fa2c483ba0e44525547d43d3e439b3f398566c15c8038e0b62f089'

def mac_code_hash(path):
    if path.stat().st_size>60000000:raise ValueError('Mac 可执行文件大小无效')
    raw=path.read_bytes();result=hashlib.sha256()
    if len(raw)<48 or raw[:8]!=bytes.fromhex('cafebabe00000002'):raise ValueError('非目标 Mac 可执行文件')
    for i,cpu_expected in enumerate((7,0x1000007)):
        cpu,sub,start,length,align=struct.unpack_from('>5I',raw,8+20*i)
        if cpu!=cpu_expected or start<48 or start>=len(raw):raise ValueError('Mac 架构范围无效')
        data=bytearray(raw[start:min(start+length,len(raw))]);wide=cpu==0x1000007;at=32 if wide else 28
        if data[:4]!=(bytes.fromhex('cffaedfe') if wide else bytes.fromhex('cefaedfe')) or len(data)<at or struct.unpack_from('<I',data,12)[0]!=2:raise ValueError('Mac 架构头无效')
        count,size=struct.unpack_from('<2I',data,16);limit=at+size;end=None
        if limit>len(data):raise ValueError('Mac 加载命令范围无效')
        for _ in range(count):
            if at+8>limit:raise ValueError('Mac 加载命令不完整')
            command,length=struct.unpack_from('<2I',data,at)
            if length<8 or at+length>limit:raise ValueError('Mac 加载命令长度无效')
            if command==(0x19 if wide else 1) and length>=(72 if wide else 56) and data[at+8:at+24].rstrip(b'\0')==b'__LINKEDIT':
                for offset in ((32,48) if wide else (28,36)):struct.pack_into('<Q' if wide else '<I',data,at+offset,0)
            if command==0x1d:
                if length!=16 or end is not None:raise ValueError('Mac 签名命令无效')
                end=struct.unpack_from('<I',data,at+8)[0];struct.pack_into('<I',data,at+12,0)
            at+=length
        if at!=limit or end is None or not limit<=end<=len(data):raise ValueError('Mac 代码范围无效')
        result.update(struct.pack('>2I',cpu,sub));result.update(data[:end])
    return result.hexdigest()

def check_game_identity(game,manifest):
    identity=target_identity(manifest);exe=confined(game,identity['executable']);data=confined(game,identity['data_dir'])
    if not exe.is_file() or not data.is_dir():raise RuntimeError('所选目录不包含目标游戏')
    if identity['exe_sha256']!=FINGERPRINTS[identity['target_id']]:raise ValueError('补丁目标指纹无效')
    if digest(exe)!=identity['exe_sha256'] and not (identity['target_id']==MACOS and mac_code_hash(exe)==MAC_CODE):
        raise RuntimeError('游戏版本不匹配；请通过 Steam 验证后重试')
    return identity

def metadata(path):
    if not path.exists():return None
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise RuntimeError('元数据保护只支持普通文件：'+str(path))
    return dict(mode=stat.S_IMODE(info.st_mode),xattrs={name:get_xattr(path,name).hex() for name in sorted(list_xattrs(path))})

def metadata_matches(actual,expected):
    if not isinstance(actual,dict) or not isinstance(expected,dict):return False
    if actual.get('mode')!=expected.get('mode'):return False
    current,recorded=actual.get('xattrs'),expected.get('xattrs')
    if not isinstance(current,dict) or not isinstance(recorded,dict):return False
    if (SYSTEM_XATTR in current)!=(SYSTEM_XATTR in recorded):return False
    return {k:v for k,v in current.items() if k!=SYSTEM_XATTR}=={k:v for k,v in recorded.items() if k!=SYSTEM_XATTR}

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

def discover(manifest):
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

def choose_game(manifest):
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
    if running:raise RuntimeError('请先完全退出 CW3（包括其他 bottle 中的 CW3），再安装或清理')

def ensure_writable(game,rows,required,manifest):
    if shutil.disk_usage(game).free<required:raise RuntimeError(f'空间不足：本操作需要约 {required//1048576+1} MiB 可用空间')
    folders={game}
    for f in rows:
        target=installed_path(game,f['file'],manifest)
        if target.is_file() and target.stat().st_nlink!=1:raise RuntimeError('受控程序文件存在硬链接：'+str(target))
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

def atomic_copy(source,target):
    # Own an exclusive file in the destination directory; fixed temp names can
    # be pre-existing files or dangling links, and are never ours to overwrite.
    fd,name=tempfile.mkstemp(prefix='.'+target.name+'-',suffix='.cw3-install-tmp',dir=target.parent);temp=Path(name)
    try:
        with os.fdopen(fd,'wb') as output,source.open('rb') as input_:
            shutil.copyfileobj(input_,output);output.flush();os.fsync(output.fileno())
        if digest(source)!=digest(temp):raise RuntimeError('写入校验失败')
        os.replace(temp,target)
        sync_directory(target.parent)
    finally:temp.unlink(missing_ok=True)

def write_existing(source,target,expected_metadata):
    # Preserve the existing inode, mode and xattrs on native macOS.
    if not metadata_matches(metadata(target),expected_metadata):raise RuntimeError('目标文件元数据已变化：'+str(target))
    with source.open('rb') as input_,target.open('r+b') as output:
        info=os.fstat(output.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise RuntimeError('受控程序文件存在硬链接或类型变化：'+str(target))
        output.seek(0);shutil.copyfileobj(input_,output);output.truncate();output.flush();os.fsync(output.fileno())
    if digest(target)!=digest(source) or not metadata_matches(metadata(target),expected_metadata):
        raise RuntimeError('原生文件原位写入校验失败：'+str(target))

def validate_release_payload(names,target_id):
    if target_id not in TARGETS:raise ValueError('不支持的补丁目标')
    names=list(names);expected=PAYLOAD if target_id==MACOS else PAYLOAD-{ADDED}
    unexpected=set(names)-expected
    if unexpected:raise ValueError('Unexpected release payload: '+', '.join(sorted(unexpected)))
    if set(names)!=expected or len(names)!=len(set(names)):raise ValueError('Incomplete or duplicate release payload; missing: '+', '.join(sorted(expected-set(names))))

def validate_manifest(manifest):
    layout=target_identity(manifest);rows=manifest.get('files',[])
    if manifest.get('format')!=2 or not isinstance(rows,list) or not rows:raise ValueError('需要完整文件包')
    validate_release_payload((r['file'] for r in rows),layout['target_id'])
    for row in rows:
        if not re.fullmatch('[0-9a-f]{64}',row.get('after','')) or type(row.get('bytes')) is not int or not 0<=row['bytes']<=250000000:raise ValueError('安装包哈希或大小无效')
    return rows

def check_legacy_dictionary(game,manifest):
    legacy=installed_path(game,LEGACY_DICTIONARY,manifest)
    if legacy.exists() and digest(legacy) not in OFFICIAL_LEGACY_DICTIONARIES:
        raise RuntimeError('旧 zh-CN.json 含未知内容；本次安装未改动游戏。请将自定义 entries 移至 zh-CN.user.json，另存并移走旧 zh-CN.json 后重试；不要覆盖已有用户词典')

def check_required_originals(game,manifest):
    for name,expected in manifest.get('required_originals',{}).items():
        if not name.startswith('CW3_Data/') or digest(installed_path(game,name,manifest))!=expected:
            raise RuntimeError('未覆盖的游戏文件版本不匹配；先清理汉化程序，再通过 Steam 验证完整性：'+name)

def signing(game):
    app=confined(game,'CW3.app');confined(game,'CW3.app/Contents/_CodeSignature/CodeResources')
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True,capture_output=True,text=True,timeout=60)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True,text=True,timeout=60)

def install(game,manifest,package=PACKAGE):
    rows=validate_manifest(manifest);idle();identity=check_game_identity(game,manifest)
    check_required_originals(game,manifest);check_legacy_dictionary(game,manifest);native=identity['target_id']==MACOS
    stale=INJECTED-{r['file'] for r in rows}
    for name in stale:
        target=installed_path(game,name,manifest)
        if target.exists() and not target.is_file():raise RuntimeError('旧程序路径不是普通文件：'+name)
    ensure_writable(game,rows,sum(r['bytes'] for r in rows)+10485760,manifest)
    # Stage and hash the entire package before touching the installation.
    with tempfile.TemporaryDirectory(prefix='cw3-install-') as directory:
        stage=Path(directory)
        for row in rows:
            source=safe(package,row['file'])
            if digest(source)!=row['after'] or source.stat().st_size!=row['bytes']:raise RuntimeError('安装包损坏：'+row['file'])
            target=safe(stage,row['file']);target.parent.mkdir(parents=True,exist_ok=True);atomic_copy(source,target)
        idle();check_game_identity(game,manifest);check_required_originals(game,manifest);check_legacy_dictionary(game,manifest)
        bundle_changed=False
        for row in rows:
            name=row['file'];target=installed_path(game,name,manifest)
            if digest(target)==row['after']:continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if native and target.exists():write_existing(safe(stage,name),target,metadata(target))
            else:atomic_copy(safe(stage,name),target)
            if digest(target)!=row['after']:raise RuntimeError('安装后校验失败：'+name)
            bundle_changed|=native and name.startswith('CW3_Data/')
        for name in stale:
            target=installed_path(game,name,manifest)
            if target.exists():target.unlink();bundle_changed|=native and name.startswith('CW3_Data/')
        if native:
            valid=subprocess.run(['codesign','--verify','--deep','--strict',str(game/'CW3.app')],capture_output=True,text=True,timeout=60).returncode==0
            if bundle_changed or not valid:signing(game)
    print('安装完成。默认译文已更新；用户覆盖词典、字体设置、自定义字体和旧备份均保留。')

def clean(game,manifest):
    idle();check_game_identity(game,manifest)
    targets=[installed_path(game,name,manifest) for name in sorted(INJECTED)]
    if any(p.exists() and not p.is_file() for p in targets):raise RuntimeError('汉化程序路径不是普通文件')
    for target in targets:
        if target.exists():target.unlink()
    print('已清理额外汉化程序。现在通过 Steam「验证游戏文件完整性」恢复原版；完成前请勿启动。词典、用户配置、自定义字体与旧备份已保留。')

def main():
    if not __debug__:raise RuntimeError('请勿以 Python 优化模式运行安装器')
    if sys.version_info<(3,10):raise RuntimeError('需要 Python 3.10 或更新版本')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--game');parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--action',choices=('install','clean'));args=parser.parse_args()
    package=args.package.resolve(strict=True);manifest=read(package/'manifest.json');validate_manifest(manifest)
    game=(Path(args.game).expanduser() if args.game else choose_game(manifest)).resolve()
    action=args.action
    if action is None:action={'1':'install','2':'clean'}.get(input('1 安装/重装汉化   2 清理汉化程序后交给 Steam 恢复   其他键退出：').strip())
    if action=='install':install(game,manifest,package)
    elif action=='clean':clean(game,manifest)
if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as error:print('未完成：'+str(error)+'。安装中断可重新运行同一完整包；不会自动回滚。');sys.exit(1)
