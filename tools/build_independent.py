"""Build the CW3-specific runtime bridge with existing wine-mono and Cecil."""
from pathlib import Path
import argparse,json,subprocess,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--generated',required=True);p.add_argument('--output',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text())
def path(k):
 x=Path(c[k]);return x if x.is_absolute() else ROOT/x
cx=path('crossover');mono=cx/'share/wine/mono'/c['mono_version'];cecil=path('cecil') if c.get('cecil') else mono/'lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll';g=path('game')/'CW3_Data/Managed';out=Path(a.output);out.mkdir(parents=True,exist_ok=True);shutil.copy2(cecil,out/'Mono.Cecil.dll')
def win(x):return str(Path(x).resolve()) if c.get('mono_runtime') else 'Z:'+str(Path(x).resolve()).replace('/','\\')
def run(exe,args):
 command=[str(path('mono_runtime')),str(exe)] if c.get('mono_runtime') else [str(cx/'bin/wine'),'--bottle',c.get('bottle','Steam'),'--no-update','--no-gui',str(exe)]
 r=subprocess.run(command+args,capture_output=True,text=True,timeout=60);print(r.stdout+r.stderr);r.check_returncode()
def compile(name,files,library=False):
 flags=['-nologo'];dest=out/(name+('.dll' if library else '.exe'))
 if library:flags+=['-target:library','-nostdlib']+['-r:'+win(g/n) for n in ('mscorlib.dll','UnityEngine.dll','System.dll','System.Xml.dll','System.Core.dll')]
 else:flags+=['-r:'+win(cecil),'-r:System.Core']
 run(path('mono_compiler') if c.get('mono_compiler') else mono/'lib/mono/4.5/mcs.exe',flags+['-out:'+win(dest)]+[win(f) for f in files]);return dest
def exe(name,source,*args):run(compile(name,[source]+([ROOT/'src/runtime/MissionScopePatch.cs',ROOT/'src/runtime/MainMenuClickPatch.cs']+([ROOT/'src/runtime/GuiCaptionAudit.cs',ROOT/'src/runtime/NativeEventCaptionAudit.cs'] if name=='RuntimePatch' else []) if name in ('RuntimePatch','RuntimeVerify') else [])),[win(x) for x in args])
original=path('original')/'CW3_Data/Managed/Assembly-CSharp.dll';render=out/'render.dll';final=out/'Assembly-CSharp.dll';generated=Path(a.generated)
helper=compile('CW3Rendering',[ROOT/'src/rendering/CW3Rendering.cs'],True);exe('RenderingPatch',ROOT/'src/rendering/Patch.cs',original,helper,g,render);exe('RenderingVerify',ROOT/'src/rendering/Verify.cs',original,render,generated/'empty.tsv')
helper=compile('CW3Runtime',[ROOT/'src/runtime/CW3Runtime.cs',ROOT/'src/runtime/CaptionLayout.cs',ROOT/'src/runtime/MessageBindings.cs',ROOT/'src/runtime/ScriptBindings.cs',ROOT/'src/runtime/MissionLoads.cs',ROOT/'src/runtime/Json.cs',ROOT/'src/runtime/FontFile.cs',ROOT/'src/runtime/Candidates.cs',generated/'Definitions.cs'],True)
exe('RuntimePatch',ROOT/'src/runtime/PatchRuntime.cs',render,helper,generated/'managed.tsv',final,g,generated/'audit.tsv',original)
exe('RuntimeVerify',ROOT/'src/runtime/VerifyRuntime.cs',render,final,generated/'audit.tsv')
