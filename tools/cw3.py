"""Offline, hash-locked reversible CW3 patch packaging. Python standard library only."""
from pathlib import Path
import argparse,base64,gzip,hashlib,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def safe(root,name):
 p=Path(name);assert not p.is_absolute() and '..' not in p.parts and (p.parts[0]=='CW3_Data' or p.as_posix() in {'CW3Localization/zh-CN.json','CW3Localization/font.ttf','CW3Localization/OFL.txt'}),name
 target=root/p;assert target.resolve().is_relative_to(root.resolve());return target
def encode(old,new):
 # Fixed anchors find shifted content; copied bytes are validated again by final SHA.
 index={old[i:i+64]:i for i in range(0,len(old)-63,64)};ops=[];pos=literal=0
 while pos+64<=len(new):
  offset=index.get(new[pos:pos+64])
  if offset is None:pos+=4;continue
  if pos>literal:ops.append(['data',base64.b64encode(new[literal:pos]).decode()])
  size=64
  while offset+size+1024<=len(old) and pos+size+1024<=len(new) and old[offset+size:offset+size+1024]==new[pos+size:pos+size+1024]:size+=1024
  while offset+size<len(old) and pos+size<len(new) and old[offset+size]==new[pos+size]:size+=1
  ops.append(['copy',offset,size]);pos+=size;literal=pos
 if literal<len(new):ops.append(['data',base64.b64encode(new[literal:]).decode()])
 return ops
def decode(old,ops):
 chunks=[]
 for op in ops:
  if op[0]=='copy':
   _,start,n=op;assert start>=0 and n>=0 and start+n<=len(old);chunks.append(old[start:start+n])
  else:assert op[0]=='data';chunks.append(base64.b64decode(op[1],validate=True))
 return b''.join(chunks)
def idle(config):
 pattern=config.get('process_pattern','[C]W3[.]exe|[/]CW3[.]app/Contents/MacOS/Menu Helper')
 r=subprocess.run(['pgrep','-fl',pattern],capture_output=True,text=True)
 assert r.returncode==1,'Exit CW3 before changing files: '+r.stdout+r.stderr
p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'config.local.json'));sub=p.add_subparsers(dest='action',required=True)
e=sub.add_parser('export');e.add_argument('--original',required=True);e.add_argument('--modified',required=True);e.add_argument('--inventory',required=True);e.add_argument('--package',required=True)
for name in ['build','verify','install','restore']:sub.add_parser(name)
a=p.parse_args()
if a.action=='export':
 original=Path(a.original);modified=Path(a.modified);inv=read(a.inventory);out=Path(a.package);assert not out.exists();out.mkdir(parents=True);rows=[]
 for i,(name,target_hash) in enumerate(inv['hashes'].items()):
  src=safe(original,name);dst=safe(modified,name);old=src.read_bytes() if src.exists() else b'';new=dst.read_bytes();assert sha(new)==target_hash,name
  if src.exists() and old==new:continue
  ops=encode(old,new);assert decode(old,ops)==new
  blob=gzip.compress(json.dumps(ops,separators=(',',':')).encode(),mtime=0);filename=str(i)+'.delta.gz';(out/filename).write_bytes(blob)
  rows.append({'file':name,'before':sha(old) if src.exists() else None,'after':sha(new),'delta':filename,'delta_sha256':sha(blob),'bytes':len(new)})
 save(out/'manifest.json',{'format':1,'revision':'open-font-v11','steam_build':'22453699','version':'2.12 Steam','files':rows});print('Exported',len(rows),'reversible file deltas');sys.exit()
c=read(a.config)
def location(k):
 value=Path(c[k]);return value if value.is_absolute() else ROOT/value
G=location('game');P=location('package');O=location('original');B=location('build');M=read(P/'manifest.json');assert M['format']==1
if a.action=='build':
 assert not B.exists(),'Build directory already exists; keep verified outputs or choose another config path'
 for f in M['files']:
  source=safe(O,f['file']);old=source.read_bytes() if source.exists() else b'';assert (sha(old) if source.exists() else None)==f['before'],f['file']
  delta=P/f['delta'];assert delta.parent==P and sha(delta.read_bytes())==f['delta_sha256'];new=decode(old,json.loads(gzip.decompress(delta.read_bytes())));assert sha(new)==f['after'];dst=safe(B,f['file']);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(new)
 print('Built and hash-verified',len(M['files']),'files');sys.exit()
def check_required_originals():
 for name,expected in M.get('required_originals',{}).items():
  target=safe(G,name);assert target.is_file() and sha(target.read_bytes())==expected,'Restore the previous patch before installing: '+name
if a.action=='verify':
 check_required_originals()
 for f in M['files']:assert sha(safe(G,f['file']).read_bytes())==f['after'],f['file']
 assert not (G/'CW3_Data/Managed/CW3Debug.dll').exists(),'Optional debug is enabled'
 print('Verified',len(M['files']),'patched files; debug disabled');sys.exit()
if a.action=='install':check_required_originals()
idle(c);assert not (G/'CW3_Data/Managed/CW3Debug.dll').exists(),'Disable debug first';install=a.action=='install';changed=[]
for f in M['files']:
 target=safe(G,f['file']);expected=f['before'] if install else f['after'];assert (sha(target.read_bytes()) if target.exists() else None)==expected,f['file']
 for root,key in [(O,'before'),(B,'after')]:
  if f[key] is not None:assert sha(safe(root,f['file']).read_bytes())==f[key],f['file']
def put(data,target):
 target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_name(target.name+'.cw3-tmp');assert not tmp.exists();tmp.write_bytes(data);assert sha(tmp.read_bytes())==sha(data);os.replace(tmp,target)
try:
 for f in M['files']:
  target=safe(G,f['file']);key='after' if install else 'before'
  if f[key] is None:target.unlink()
  else:put(safe(B if install else O,f['file']).read_bytes(),target)
  changed.append(f)
except BaseException:
 for f in reversed(changed):
  target=safe(G,f['file']);key='before' if install else 'after'
  if f[key] is None:target.unlink(missing_ok=True)
  else:put(safe(O if install else B,f['file']).read_bytes(),target)
 raise
print('Installed' if install else 'Restored original',len(changed),'files')
