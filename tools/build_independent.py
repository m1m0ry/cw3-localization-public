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
 if name in ('UnitSortCapacityPatch','UnitSortCapacityVerify','UnitSortCapacityContracts'):files += [ROOT/'src/performance/UnitSortCapacityPatch.cs']
 if name in ('PathDistancePatch','PathDistanceVerify','PathDistanceContracts'):files += [ROOT/'src/performance/PathDistancePatch.cs']
 if name in ('CreeperDynamicPatch','CreeperDynamicVerify','CreeperDynamicContracts'):files += [ROOT/'src/performance/CreeperDynamicPatch.cs']
 if name in ('CreeperUVPatch','CreeperUVVerify','CreeperUVContracts'):files += [ROOT/'src/performance/CreeperUVPatch.cs']
 if name in ('SprayerLosPatch','SprayerLosVerify','SprayerLosContracts'):files += [ROOT/'src/performance/SprayerLosPatch.cs']
 if name=='RuntimePatch':files += [ROOT/'src/runtime/GuiCaptionAudit.cs',ROOT/'src/runtime/NativeEventCaptionAudit.cs',ROOT/'src/verification/BindingAnchor.cs']
 if name in ('RenderingVerify','RuntimeVerify','CustomSavePathVerify','EnumeratorDisposePatch','EnumeratorDisposeVerify','EnumeratorDisposeContracts','ManagerSnapshotPatch','ManagerSnapshotVerify','ManagerSnapshotContracts','PathWorkspacePatch','PathWorkspaceVerify','PathWorkspaceContracts','UnitSortCapacityPatch','UnitSortCapacityVerify','UnitSortCapacityContracts','PathDistancePatch','PathDistanceVerify','PathDistanceContracts','CreeperDynamicPatch','CreeperDynamicVerify','CreeperDynamicContracts','CreeperUVPatch','CreeperUVVerify','CreeperUVContracts','SprayerLosPatch','SprayerLosVerify','SprayerLosContracts'):files.append(ROOT/'src/verification/AssemblyStructure.cs')
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
path_probe_dir=out/'path-workspace-probe';path_probe_dir.mkdir(exist_ok=True)
# Unused UI field types need identities during CLR object allocation, not real
# firstpass behavior. Keep this source-built fixture out of production resolution.
m.compile(path_probe_dir,'Assembly-CSharp-firstpass.dll',[ROOT/'tests/PathWorkspaceFirstpass.cs'],['-target:library'])
path_probe=m.compile(path_probe_dir,'PathWorkspaceProbe.exe',[ROOT/'tests/PathWorkspaceProbe.cs'],['-r:System.Core','-r:System.Xml'])
path_before=path_probe_dir/'PathWorkspace.before.dll';path_after=path_probe_dir/'PathWorkspace.after.dll'
run(prepare_path,[win(final),win(path_before),win(g)])
run(prepare_path,[win(path_optimized),win(path_after),win(g)])
path_expected=run(path_probe,[win(path_before),win(g/'UnityEngine.dll')],capture=True).stdout
path_actual=run(path_probe,[win(path_after),win(g/'UnityEngine.dll')],capture=True).stdout
if path_expected!=path_actual:raise RuntimeError('Path workspace changed original search results')
print(path_actual.splitlines()[-1])
shutil.copy2(path_optimized,final)

# One exact capacity reservation replaces repeated per-step sorted-table growth.
# Keep the fixture's mock Unity assembly isolated from real game resolution.
unit_fixture_dir=out/'unit-capacity-fixture';unit_fixture_dir.mkdir(exist_ok=True)
unit_engine=m.compile(unit_fixture_dir,'UnityEngine.dll',[ROOT/'tests/UnitSortCapacityUnity.cs'],['-target:library'])
unit_fixture=m.compile(unit_fixture_dir,'UnitSortCapacityFixture.exe',[ROOT/'tests/UnitSortCapacityFixture.cs'],['-r:'+win(unit_engine)])
unit_patched=unit_fixture_dir/'UnitSortCapacityFixture.patched.exe';unit_optimized=out/'Assembly-CSharp.unit-capacity.dll'
exe('UnitSortCapacityContracts',ROOT/'tests/UnitSortCapacityContracts.cs',unit_fixture,unit_patched,final,g,unit_optimized)
run(unit_fixture,[]);run(unit_patched,[])
exe('UnitSortCapacityVerify',ROOT/'src/performance/VerifyUnitSortCapacity.cs',final,unit_optimized,g)
shutil.copy2(unit_optimized,final)

# Reuse only same-call endpoint Vector3 values across x/y distance components.
distance_dir=out/'path-distance-fixture';distance_dir.mkdir(exist_ok=True)
distance_engine=m.compile(distance_dir,'UnityEngine.dll',[ROOT/'tests/PathDistanceUnity.cs'],['-target:library'])
distance_fixture=m.compile(distance_dir,'PathDistanceFixture.exe',[ROOT/'tests/PathDistanceFixture.cs'],['-r:'+win(distance_engine)])
distance_patched=distance_dir/'PathDistanceFixture.patched.exe';distance_optimized=out/'Assembly-CSharp.path-distance.dll'
exe('PathDistanceContracts',ROOT/'tests/PathDistanceContracts.cs',distance_fixture,distance_patched,final,g,distance_optimized)
run(distance_fixture,['original']);run(distance_patched,['patched'])
exe('PathDistanceVerify',ROOT/'src/performance/VerifyPathDistance.cs',final,distance_optimized,g)
shutil.copy2(distance_optimized,final)

# Measured native Mac graphics-backend efficiency hint. Windows stays unchanged.
if target['platform']==2:
 dynamic_dir=out/'creeper-dynamic-fixture';dynamic_dir.mkdir(exist_ok=True)
 dynamic_engine=m.compile(dynamic_dir,'UnityEngine.dll',[ROOT/'tests/CreeperDynamicUnity.cs'],['-target:library'])
 dynamic_fixture=m.compile(dynamic_dir,'CreeperDynamicFixture.exe',[ROOT/'tests/CreeperDynamicFixture.cs'],['-r:'+win(dynamic_engine)])
 dynamic_patched=dynamic_dir/'CreeperDynamicFixture.patched.exe';dynamic_optimized=out/'Assembly-CSharp.creeper-dynamic.dll'
 exe('CreeperDynamicContracts',ROOT/'tests/CreeperDynamicContracts.cs',dynamic_fixture,dynamic_patched,final,g,dynamic_optimized)
 run(dynamic_fixture,['original']);run(dynamic_patched,['patched'])
 exe('CreeperDynamicVerify',ROOT/'src/performance/VerifyCreeperDynamic.cs',final,dynamic_optimized,g)
 shutil.copy2(dynamic_optimized,final)

# Native Mac only: exact direct Vector2 stores, no animation or upload skipping.
if target['platform']==2:
 uv_dir=out/'creeper-uv-fixture';uv_dir.mkdir(exist_ok=True)
 uv_engine=m.compile(uv_dir,'UnityEngine.dll',[ROOT/'tests/CreeperUVUnity.cs'],['-target:library'])
 uv_fixture=m.compile(uv_dir,'CreeperUVFixture.exe',[ROOT/'tests/CreeperUVFixture.cs'],['-r:'+win(uv_engine)])
 uv_patched=uv_dir/'CreeperUVFixture.patched.exe';uv_optimized=out/'Assembly-CSharp.creeper-uv.dll'
 exe('CreeperUVContracts',ROOT/'tests/CreeperUVContracts.cs',uv_fixture,uv_patched,final,g,uv_optimized)
 run(uv_fixture,[]);run(uv_patched,[])
 exe('CreeperUVVerify',ROOT/'src/performance/VerifyCreeperUV.cs',final,uv_optimized,g)
 shutil.copy2(uv_optimized,final)

# Native Mac only: remove one redundant ray when Digitalis cannot improve.
# Full original/patched query IL is replayed on synthetic maps, not game assets.
if target['platform']==2:
 sprayer_optimized=out/'Assembly-CSharp.sprayer-los.dll'
 exe('SprayerLosContracts',ROOT/'tests/SprayerLosContracts.cs',final,sprayer_optimized,g)
 sprayer_skeleton=compile('SprayerLosProbe',[ROOT/'tests/SprayerLosProbe.cs'])
 sprayer_probe=out/'SprayerLosProbe.ready.exe'
 exe('PrepareSprayerLosProbe',ROOT/'tests/PrepareSprayerLosProbe.cs',final,sprayer_optimized,sprayer_skeleton,sprayer_probe)
 run(sprayer_probe,[])
 exe('SprayerLosVerify',ROOT/'src/performance/VerifySprayerLos.cs',final,sprayer_optimized,g)
 shutil.copy2(sprayer_optimized,final)
