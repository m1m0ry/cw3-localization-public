"""Build and verify the optional debug module against a prepared CW3 candidate."""
from pathlib import Path
from mono_tools import MonoTools
import argparse,json,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--debug',action='store_true',required=True);p.add_argument('--output');a=p.parse_args();c=json.loads(Path(a.config).read_text())
# Debug has always used this configured wine-mono compiler and Cecil, including
# when release/test builds select native Mono. Keep that toolchain unchanged.
m=MonoTools({k:v for k,v in c.items() if k not in ('mono_runtime','mono_compiler','cecil')});path=m.location;win=m.win;run=m.run
G=path('game')/'CW3_Data/Managed';out=Path(a.output) if a.output else ROOT/'local-only/debug';out.mkdir(parents=True,exist_ok=True);shutil.copy2(m.cecil,out/'Mono.Cecil.dll')
def compile(name,library=False):
 flags=[]
 if library:flags+=['-target:library','-nostdlib','-r:'+win(G/'mscorlib.dll'),'-r:'+win(G/'UnityEngine.dll')]
 else:flags+=['-r:'+win(m.cecil),'-r:System.Core']
 flags+=['-r:'+win(G/'System.Xml.dll')]
 return m.compile(out,name+'.dll' if library else 'debug-'+name+'.exe',[ROOT/'src/debug'/(name+'.cs')],flags)
def exe(name,*args):run(compile(name),[win(x) for x in args])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=path('build')/'CW3_Data/Managed/Assembly-CSharp.dll';helper=compile('CW3Debug',True);dest=out/'Assembly-CSharp.debug.dll';exe('Inject',source,helper,G,dest);empty=out/'empty.tsv';empty.write_text('');exe('Verify',source,dest,empty)
(out/'manifest.json').write_text(json.dumps({'base':str(source.relative_to(ROOT)),'base_sha256':sha(source),'debug_sha256':sha(dest),'helper_sha256':sha(helper)},indent=2)+'\n')
