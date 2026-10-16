"""Build and verify the optional debug module against a prepared CW3 candidate."""
from pathlib import Path
from mono_tools import MonoTools
import game_target
import argparse,json,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--debug',action='store_true',required=True);p.add_argument('--output');a=p.parse_args();c=json.loads(Path(a.config).read_text())
m=MonoTools(c);path=m.location;win=m.win;run=m.run
target=game_target.load(c);game_target.verify_inputs(path('original'),target,['CW3_Data/Managed/'+n for n in ('mscorlib.dll','UnityEngine.dll','System.Xml.dll')])
G=path('original')/'CW3_Data/Managed';out=Path(a.output) if a.output else ROOT/'local-only/debug';out.mkdir(parents=True,exist_ok=True);shutil.copy2(m.cecil,out/'Mono.Cecil.dll')
def compile(name,library=False):
 flags=[]
 if library:flags+=['-target:library','-nostdlib','-r:'+win(G/'mscorlib.dll'),'-r:'+win(G/'UnityEngine.dll')]
 else:flags+=['-r:'+win(m.cecil),'-r:System.Core']
 flags+=['-r:'+win(G/'System.Xml.dll')]
 files=[ROOT/'src/debug'/(name+'.cs')]
 if name=='Verify':files.append(ROOT/'src/verification/AssemblyStructure.cs')
 return m.compile(out,name+'.dll' if library else 'debug-'+name+'.exe',files,flags)
def exe(name,*args):run(compile(name),[win(x) for x in args])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=path('build')/'CW3_Data/Managed/Assembly-CSharp.dll';helper=compile('CW3Debug',True);dest=out/'Assembly-CSharp.debug.dll';exe('Inject',source,helper,G,dest);exe('Verify',source,dest)
(out/'manifest.json').write_text(json.dumps({'base':str(source.relative_to(ROOT)),'base_sha256':sha(source),'debug_sha256':sha(dest),'helper_sha256':sha(helper)},indent=2)+'\n')
