"""Small full-package fixtures, never a copy of a game installation."""
from pathlib import Path
import base64,hashlib,json,struct,os,ctypes
import player_install as player
sha=lambda data:hashlib.sha256(data).hexdigest()

def macho(signature=b'ORIGINAL',code=b'UNCHANGED CODE'):
    slices=[]
    for wide,cpu in ((False,7),(True,0x1000007)):
        size=72 if wide else 56;header=32 if wide else 28;end=header+size+16+len(code)
        segment=struct.pack('<II16s'+('4Q' if wide else '4I')+'4I',0x19 if wide else 1,size,b'__LINKEDIT',0,end+len(signature),end,len(signature),0,0,0,0)
        data=struct.pack('<7I',0xfeedfacf if wide else 0xfeedface,cpu,3,2,2,size+16,0)+(bytes(4) if wide else b'')
        slices.append(data+segment+struct.pack('<4I',0x1d,16,end,len(signature))+code+signature)
    first=48;second=first+len(slices[0])
    return struct.pack('>2I',0xcafebabe,2)+struct.pack('>5I',7,3,first,len(slices[0]),0)+struct.pack('>5I',0x1000007,3,second,len(slices[1]),0)+b''.join(slices)

def registry():
    face=lambda file:dict(file=file,sha256='0'*64,family='Fixture',coverage=base64.b64encode(bytes(8192)).decode(),pixel_size=0,probe_char=65,probe_advance=20)
    return dict(format=1,runtime_sha256='0'*64,resources={n:'0'*64 for n in ('CW3_Data/mainData','CW3_Data/sharedassets0.assets')},fonts={'sans':face('font.ttf'),'serif':face('serif.ttf')})

def fixture(root,native=False,version='one'):
    game=root/'game';package=root/('package-'+version);package.mkdir()
    target=player.MACOS if native else player.WINDOWS
    manifest=dict(format=2,version=version,target_id=target,**player.TARGETS[target],exe_sha256=sha(macho() if native else b'EXE'),files=[])
    exe=game/manifest['executable'];exe.parent.mkdir(parents=True,exist_ok=True);exe.write_bytes(macho() if native else b'EXE')
    names=player.PAYLOAD if native else player.PAYLOAD-{player.ADDED}
    for name in sorted(names):
        content=json.dumps(registry()).encode() if name=='CW3Localization/fonts.json' else (version+':'+name).encode()
        source=package/name;source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(content)
        original=None if name in player.INJECTED or name in player.RUNTIME else ('ORIGINAL:'+name).encode()
        if original is not None:
            path=player.installed_path(game,name,manifest);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(original)
        manifest['files'].append(dict(file=name,before=None if original is None else sha(original),after=sha(content),bytes=len(content)))
    anchor=game/manifest['data_dir']/'anchor';anchor.write_bytes(b'VERSION')
    manifest['required_originals']={'CW3_Data/anchor':sha(b'VERSION')}
    (package/'manifest.json').write_text(json.dumps(manifest))
    (game/'save.sentinel').write_bytes(b'USER SAVE')
    return game,package,manifest

def snapshot(root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

def set_xattr(path,name,value):
    if hasattr(os,'setxattr'):return os.setxattr(path,name,value)
    libc=ctypes.CDLL(None,use_errno=True);call=libc.setxattr
    call.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int];call.restype=ctypes.c_int
    payload=ctypes.create_string_buffer(value,max(len(value),1))
    if call(os.fsencode(path),os.fsencode(name),payload,len(value),0,0)<0:raise OSError(ctypes.get_errno(),os.strerror(ctypes.get_errno()),str(path))
