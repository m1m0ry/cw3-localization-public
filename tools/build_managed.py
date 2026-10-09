"""Rebuild owned C# helpers and audited IL edits from the user's original CW3 DLL."""
from pathlib import Path
import argparse,json,subprocess,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--debug',action='store_true');p.add_argument('--generated');p.add_argument('--output');a=p.parse_args();c=json.loads(Path(a.config).read_text())
def path(k):
 x=Path(c[k]);return x if x.is_absolute() else ROOT/x
CX=path('crossover');MONO=CX/'share/wine/mono'/c['mono_version'];CECIL=MONO/'lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll';G=path('game')/'CW3_Data/Managed';out=Path(a.output) if a.output else ROOT/'local-only'/('debug' if a.debug else 'managed-build');out.mkdir(parents=True,exist_ok=True);shutil.copy2(CECIL,out/'Mono.Cecil.dll')
def win(x):return 'Z:'+str(x.resolve()).replace('/','\\')
def run(exe,args):
 r=subprocess.run([str(CX/'bin/wine'),'--bottle',c.get('bottle','Steam'),'--no-update','--no-gui',str(exe)]+args,capture_output=True,text=True,timeout=60);print(r.stdout+r.stderr);r.check_returncode()
def compile(folder,name,library=False):
 flags=['-nologo']
 if library:flags+=['-target:library','-nostdlib','-r:'+win(G/'mscorlib.dll'),'-r:'+win(G/'UnityEngine.dll')]
 else:flags+=['-r:'+win(CECIL),'-r:System.Core']
 dest=out/(folder+'-'+name+('.dll' if library else '.exe'))
 if library:dest=out/(name+'.dll')
 run(MONO/'lib/mono/4.5/mcs.exe',flags+['-out:'+win(dest),win(Path(a.generated)/'CW3Display.cs' if folder=='display' and name=='CW3Display' else ROOT/'src'/folder/(name+'.cs'))]);return dest
def exe(folder,name,*args):run(compile(folder,name),[win(x) for x in args])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if a.debug:
 source=path('build')/'CW3_Data/Managed/Assembly-CSharp.dll';helper=compile('debug','CW3Debug',True);dest=out/'Assembly-CSharp.debug.dll';exe('debug','Inject',source,helper,G,dest);empty=out/'empty.tsv';empty.write_text('');exe('debug','Verify',source,dest,empty)
 (out/'manifest.json').write_text(json.dumps({'base':str(source.relative_to(ROOT)),'base_sha256':sha(source),'debug_sha256':sha(dest),'helper_sha256':sha(helper)},indent=2)+'\n')
else:
 assert a.generated, 'Use tools/workflow.py build for release builds'
 original=path('original')/'CW3_Data/Managed/Assembly-CSharp.dll';v9=out/'v9.dll';render=out/'render.dll';strings=out/'strings.dll';final=out/'Assembly-CSharp.dll'
 exe('managed','PatchDisplay',original,Path(a.generated)/'managed-v9.tsv',v9,G)
 helper=compile('rendering','CW3Rendering',True);exe('rendering','Patch',v9,helper,G,render);exe('rendering','Verify',original,render,Path(a.generated)/'managed-v9.tsv')
 exe('managed','PatchDisplay',render,Path(a.generated)/'managed-v10.tsv',strings,G)
 helper=compile('display','CW3Display',True);exe('display','MapDisplay',strings,helper,final,G);exe('display','Verify',render,final,Path(a.generated)/'managed-v10.tsv')
 print('Semantic verification passed. Development output is not automatically installed; resource and runtime validation are separate.')
