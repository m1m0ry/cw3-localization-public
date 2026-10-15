"""Build the CW3-specific runtime bridge with existing wine-mono and Cecil."""
from pathlib import Path
from mono_tools import MonoTools, runtime_sources
import argparse,json,shutil
import game_target
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--generated',required=True);p.add_argument('--output',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text())
m=MonoTools(c);path=m.location;win=m.win;run=m.run
target=game_target.load(c);game_target.verify_inputs(path('original'),target)
g=path('original')/'CW3_Data/Managed';out=Path(a.output);out.mkdir(parents=True,exist_ok=True);shutil.copy2(m.cecil,out/'Mono.Cecil.dll')
def compile(name,files,library=False):
 flags=[]
 if library:flags+=['-target:library','-nostdlib']+['-r:'+win(g/n) for n in ('mscorlib.dll','UnityEngine.dll','System.dll','System.Xml.dll','System.Core.dll')]
 else:flags+=['-r:'+win(m.cecil),'-r:System.Core']
 if name=='CW3ExternalRuntime' and target['platform']==2:flags+=['-define:CW3_MAC']
 return m.compile(out,name+('.dll' if library else '.exe'),files,flags)
def exe(name,source,*args):
 files=[source]
 if name in ('RuntimePatch','RuntimeVerify'):files += [ROOT/'src/runtime/MissionScopePatch.cs',ROOT/'src/runtime/MainMenuClickPatch.cs']
 if name=='RuntimePatch':files += [ROOT/'src/runtime/GuiCaptionAudit.cs',ROOT/'src/runtime/NativeEventCaptionAudit.cs',ROOT/'src/verification/BindingAnchor.cs']
 if name in ('RenderingVerify','RuntimeVerify'):files.append(ROOT/'src/verification/AssemblyStructure.cs')
 run(compile(name,files),[win(x) for x in args])
original=path('original')/'CW3_Data/Managed/Assembly-CSharp.dll';render=out/'render.dll';final=out/'Assembly-CSharp.dll';generated=Path(a.generated)
helper=compile('CW3Rendering',[ROOT/'src/rendering/CW3Rendering.cs'],True);exe('RenderingPatch',ROOT/'src/rendering/Patch.cs',original,helper,g,render);exe('RenderingVerify',ROOT/'src/rendering/Verify.cs',original,render)
if target['platform']==2:
 compile('CW3ExternalRuntime',runtime_sources(generated,True),True)
 helper=compile('CW3Runtime',[ROOT/'src/runtime/CW3Bridge.cs'],True)
else:helper=compile('CW3Runtime',runtime_sources(generated),True)
exe('RuntimePatch',ROOT/'src/runtime/PatchRuntime.cs',render,helper,generated/'managed.tsv',final,g,generated/'audit.tsv',original)
exe('RuntimeVerify',ROOT/'src/runtime/VerifyRuntime.cs',render,final,generated/'audit.tsv')

# Audit the runtime bridge first, then independently bound the rendering change to
# UIPanel's material-fill phase. The native Mac assembly passed the same exact
# two-method verification; promote either platform only after that check succeeds.
optimized=out/'Assembly-CSharp.panel-fill.dll'
exe('PanelFillPatch',ROOT/'src/rendering/PatchPanelFill.cs',final,optimized,g)
exe('PanelFillVerify',ROOT/'src/rendering/VerifyPanelFill.cs',final,optimized)
shutil.copy2(optimized,final)
