"""Build the CW3-specific runtime bridge with existing wine-mono and Cecil."""
from pathlib import Path
from mono_tools import MonoTools, runtime_sources
import argparse,json,shutil
import game_target
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--generated',required=True);p.add_argument('--output',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text())
m=MonoTools(c);path=m.location;win=m.win;run=m.run
target=game_target.load(c);game_target.verify_inputs(path('original'),target,[n for n in target['original_hashes'] if n.startswith('CW3_Data/Managed/')])
g=path('original')/'CW3_Data/Managed';out=Path(a.output);out.mkdir(parents=True,exist_ok=True);shutil.copy2(m.cecil,out/'Mono.Cecil.dll')
def compile(name,files,library=False):
 flags=[]
 if library:flags+=['-target:library','-deterministic','-nostdlib']+['-r:'+win(g/n) for n in ('mscorlib.dll','UnityEngine.dll','System.dll','System.Xml.dll','System.Core.dll')]
 else:flags+=['-r:'+win(m.cecil),'-r:System.Core']
 if name=='CW3ExternalRuntime' and target['platform']==2:flags+=['-define:CW3_MAC,CW3_RENDER_EXTERNAL']
 if name=='CW3Rendering' and target['platform']==2:flags+=['-r:'+win(out/'CW3Runtime.dll')]
 return m.compile(out,name+('.dll' if library else '.exe'),files,flags)
def exe(name,source,*args):
 files=[source]
 if name in ('RuntimePatch','RuntimeVerify'):files += [ROOT/'src/runtime/MissionScopePatch.cs',ROOT/'src/runtime/MainMenuClickPatch.cs']
 if name in ('CustomSavePathPatch','CustomSavePathVerify'):files += [ROOT/'src/runtime/CustomSavePathPatch.cs']
 if name in ('EnumeratorDisposePatch','EnumeratorDisposeVerify','EnumeratorDisposeContracts'):files += [ROOT/'src/performance/EnumeratorDisposePatch.cs']
 if name in ('ManagerSnapshotPatch','ManagerSnapshotVerify','ManagerSnapshotContracts'):files += [ROOT/'src/performance/ManagerSnapshotPatch.cs']
 if name in ('PathWorkspacePatch','PathWorkspaceVerify','PathWorkspaceContracts'):files += [ROOT/'src/performance/PathWorkspacePatch.cs']
 if name=='RuntimePatch':files += [ROOT/'src/runtime/GuiCaptionAudit.cs',ROOT/'src/runtime/NativeEventCaptionAudit.cs',ROOT/'src/verification/BindingAnchor.cs']
 if name in ('RenderingVerify','RuntimeVerify','CustomSavePathVerify','EnumeratorDisposePatch','EnumeratorDisposeVerify','EnumeratorDisposeContracts','ManagerSnapshotPatch','ManagerSnapshotVerify','ManagerSnapshotContracts','PathWorkspacePatch','PathWorkspaceVerify','PathWorkspaceContracts'):files.append(ROOT/'src/verification/AssemblyStructure.cs')
 run(compile(name,files),[win(x) for x in args])
original=path('original')/'CW3_Data/Managed/Assembly-CSharp.dll';render=out/'render.dll';final=out/'Assembly-CSharp.dll';generated=Path(a.generated)
if target['platform']==2:
 compile('CW3ExternalRuntime',runtime_sources(generated,native_mac=True),True)
 helper=compile('CW3Runtime',[ROOT/'src/runtime/CW3Bridge.cs'],True)
else:helper=compile('CW3Runtime',runtime_sources(generated),True)
render_source='CW3RenderingBridge.cs' if target['platform']==2 else 'CW3Rendering.cs'
render_helper=compile('CW3Rendering',[ROOT/'src/rendering'/render_source],True)
exe('RenderingPatch',ROOT/'src/rendering/Patch.cs',original,render_helper,g,render);exe('RenderingVerify',ROOT/'src/rendering/Verify.cs',original,render)
exe('RuntimePatch',ROOT/'src/runtime/PatchRuntime.cs',render,helper,generated/'managed.tsv',final,g,generated/'audit.tsv',original)
exe('RuntimeVerify',ROOT/'src/runtime/VerifyRuntime.cs',render,final,generated/'audit.tsv')

# Audit the runtime bridge first, then independently bound the rendering change to
# UIPanel's material-fill phase. The native Mac assembly passed the same exact
# two-method verification; promote either platform only after that check succeeds.
optimized=out/'Assembly-CSharp.panel-fill.dll'
exe('PanelFillPatch',ROOT/'src/rendering/PatchPanelFill.cs',final,optimized,g)
exe('PanelFillVerify',ROOT/'src/rendering/VerifyPanelFill.cs',final,optimized)
shutil.copy2(optimized,final)

# The native game otherwise probes Documents before reading its custom path.
if target['platform']==2:
 adjusted=out/'Assembly-CSharp.custom-save-path.dll'
 exe('CustomSavePathPatch',ROOT/'src/runtime/PatchCustomSavePath.cs',final,adjusted,g)
 exe('CustomSavePathVerify',ROOT/'src/runtime/VerifyCustomSavePath.cs',final,adjusted)
 shutil.copy2(adjusted,final)

# Replace old compiler disposal boxes with stack copies, not collection/algorithm
# rewrites. This is audited independently after all display and save-path stages.
disposal_fixture=compile('EnumeratorDisposeFixture',[ROOT/'tests/EnumeratorDisposeFixture.cs'])
disposal_patched=out/'EnumeratorDisposeFixture.patched.exe'
exe('EnumeratorDisposeContracts',ROOT/'tests/EnumeratorDisposeContracts.cs',disposal_fixture,disposal_patched)
run(disposal_fixture,['original']);run(disposal_patched,['patched'])
allocation_optimized=out/'Assembly-CSharp.enumerator-dispose.dll'
exe('EnumeratorDisposePatch',ROOT/'src/performance/PatchEnumeratorDispose.cs',final,allocation_optimized,g)
exe('EnumeratorDisposeVerify',ROOT/'src/performance/VerifyEnumeratorDispose.cs',final,allocation_optimized)
shutil.copy2(allocation_optimized,final)

# Preserve public fresh snapshots; only five audited synchronous loops borrow.
snapshot_fixture=compile('ManagerSnapshotFixture',[ROOT/'tests/ManagerSnapshotFixture.cs'])
snapshot_patched=out/'ManagerSnapshotFixture.patched.exe';snapshot_fault=out/'ManagerSnapshotFixture.copyfault.exe'
exe('ManagerSnapshotContracts',ROOT/'tests/ManagerSnapshotContracts.cs',snapshot_fixture,snapshot_patched,snapshot_fault)
run(snapshot_fixture,['original']);run(snapshot_patched,['patched']);run(snapshot_fault,['copyfault'])
snapshot_optimized=out/'Assembly-CSharp.snapshots.dll'
exe('ManagerSnapshotPatch',ROOT/'src/performance/PatchManagerSnapshots.cs',final,snapshot_optimized,g)
exe('ManagerSnapshotVerify',ROOT/'src/performance/VerifyManagerSnapshots.cs',final,snapshot_optimized,g)
shutil.copy2(snapshot_optimized,final)

# Reuse only internal path scores; never share the returned predecessor dictionary.
path_fixture=compile('PathWorkspaceFixture',[ROOT/'tests/PathWorkspaceFixture.cs'])
path_fixture_patched=out/'PathWorkspaceFixture.patched.exe';path_optimized=out/'Assembly-CSharp.path-workspace.dll'
exe('PathWorkspaceContracts',ROOT/'tests/PathWorkspaceContracts.cs',path_fixture,path_fixture_patched,final,g,path_optimized)
run(path_fixture_patched,[])
exe('PathWorkspaceVerify',ROOT/'src/performance/VerifyPathWorkspace.cs',final,path_optimized,g)
# Run exact original search IL over deterministic synthetic terrain. This is
# behavior evidence on the host runtime, separate from real-game performance.
prepare_path=compile('PreparePathWorkspaceProbe',[ROOT/'tests/PreparePathWorkspaceProbe.cs'])
path_probe=compile('PathWorkspaceProbe',[ROOT/'tests/PathWorkspaceProbe.cs'])
path_before=out/'PathWorkspace.before.dll';path_after=out/'PathWorkspace.after.dll'
run(prepare_path,[win(final),win(path_before),win(g)])
run(prepare_path,[win(path_optimized),win(path_after),win(g)])
path_expected=run(path_probe,[win(path_before),win(g/'UnityEngine.dll')],capture=True).stdout
path_actual=run(path_probe,[win(path_after),win(g/'UnityEngine.dll')],capture=True).stdout
if path_expected!=path_actual:raise RuntimeError('Path workspace changed original search results')
print(path_actual.splitlines()[-1])
shutil.copy2(path_optimized,final)
