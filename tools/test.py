"""Default: all Python/C# checks. --suite: only selected C# suites and their fixtures."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile,time
from mono_tools import MonoTools, runtime_sources
ROOT=Path(__file__).resolve().parents[1]
POLICY={
    'CandidateContracts':['Candidates.cs','Json.cs'],
    'RuntimeContracts':['Json.cs','FontFile.cs'],
    'TranslationFileContracts':['Json.cs','TranslationFiles.cs'],
    'LocalFontContracts':['LocalFontFile.cs'],
    'NativeFontBundleContracts':['LocalFontFile.cs','NativeFontBundle.cs'],
    'RuntimePathsContracts':['RuntimePaths.cs'],
    'FontSettingsContracts':['Json.cs','TextStylePolicy.cs','FontSettingsModel.cs'],
    'FontSettingsViewContracts':['Json.cs','TextStylePolicy.cs','FontSettingsModel.cs','FontSettingsView.cs'],
    'TextStyleContracts':['Json.cs','FontRegistry.cs','TextStylePolicy.cs','TextStyles.cs','CaptionLayout.cs','RuntimePaths.cs'],
    'MessageContracts':['Json.cs','MessageBindings.cs'],
    'ScriptContracts':['Json.cs','MessageBindings.cs','ScriptBindings.cs'],
    'MessageCandidateContracts':['Json.cs','MessageBindings.cs','Candidates.cs']}
SUITES=tuple(POLICY)+('MeshLifetimeContracts','AssemblyStructureContracts','CaptionLayoutContracts','RenderingOrderContracts','GuiCaptionContracts','NativeNoticeContracts','MainMenuClickContracts','MissionLoadContracts','ManagedDisplayContracts','PanelFillContracts','ScriptOutputCandidateContracts')
STANDALONE=('CandidateContracts','TranslationFileContracts','RuntimePathsContracts',
            'FontSettingsContracts','FontSettingsViewContracts','TextStyleContracts','CaptionLayoutContracts')
class Contracts:
    def __init__(self,mono,out):self.mono=mono;self.out=out
    def execute(self,name,sources,args=(),flags=()):
        exe=self.mono.compile(self.out,name+'.exe',sources,flags);self.mono.run(exe,args)
    def suite(self,name):
        m=self.mono;o=self.out;runtime=ROOT/'src/runtime';test=ROOT/'tests';w=m.win
        print('RUN '+name,flush=True)
        if name in POLICY:
            sources=[runtime/s for s in POLICY[name]]+[test/(name+'.cs')]
            if name=='FontSettingsViewContracts':sources.append(test/'UnityFixture.cs')
            args=[]
            if name in ('CandidateContracts','RuntimePathsContracts','TranslationFileContracts'):args=[w(o)]
            elif name in ('TextStyleContracts','FontSettingsContracts','FontSettingsViewContracts'):pass
            elif name=='NativeFontBundleContracts':
                import native_font_template
                import game_target
                platform=game_target.load(m.config)['platform']
                generated=o/'NativeFontTemplate.cs';generated.write_text(native_font_template.build(m.location('original'),expected_platform=platform));sources.append(generated)
                args=[w(m.location('build')/'CW3Localization/font.ttf'),w(o/'native-contract.bundle')]
            elif name=='LocalFontContracts':
                import font_registry
                from fontTools.ttLib import TTFont
                font=m.location('build')/'CW3Localization/font.ttf';spec=font_registry.inspect_font(font)
                with TTFont(font) as face:family=face['name'].getDebugName(1)
                args=[w(font),family,spec['coverage'],str(spec['probe_advance'])]
            elif name=='RuntimeContracts':args=[w(m.location('build')/'CW3Localization/font.ttf'),w(ROOT/'fonts/CW3SansSC-Regular.ttf'),w(o),w(test/'json_rejected.json')]
            else:
                sources.append(m.location('build').parent/'generated/Definitions.cs')
                args=[w(o/'message-candidates.json')] if name=='MessageCandidateContracts' else [w(ROOT/'translations/zh-CN.json')]
            self.execute(name,sources,args)
            if name=='NativeFontBundleContracts':subprocess.run([sys.executable,str(test/'check_native_font_bundle.py'),str(o/'native-contract.bundle'),str(m.location('build')/'CW3Localization/font.ttf'),'--platform',str(platform)],check=True)
            if name=='TextStyleContracts':
                for mode in ('native','native-state-unavailable','registry-missing','registry-invalid','registry-runtime','registry-resource'):m.run(o/(name+'.exe'),[mode,w(o)])
            if name=='MessageCandidateContracts':subprocess.run([sys.executable,str(test/'check_candidate_pipeline.py'),str(o/'message-candidates.json'),str(o)],check=True)
        elif name=='MeshLifetimeContracts':
            self.execute(name,runtime_sources(m.location('build').parent/'generated')+[test/'UnityFixture.cs',test/(name+'.cs')],flags=['-r:System.Xml'])
        elif name=='ScriptOutputCandidateContracts':
            self.execute('ScriptOutputEngine',[test/'ScriptOutputEngine.cs'],[w(m.location('original')/'CW3_Data/Managed/UnityEngine.dll'),w(o/'UnityEngine.dll')],[m.prepare_cecil(o),'-r:System.Core'])
            sources=runtime_sources(m.location('build').parent/'generated')+[test/(name+'.cs')]
            self.execute(name,sources,[w(o/'script-candidates.json'),w(ROOT/'translations/zh-CN.json')],['-r:'+w(o/'UnityEngine.dll'),'-r:System.Xml'])
            subprocess.run([sys.executable,str(test/'check_script_candidate_pipeline.py'),str(o/'script-candidates.json'),str(o)],check=True)
        elif name=='PanelFillContracts':
            fixture=m.compile(o,'PanelFillContract.exe',[test/'PanelFillContract.cs'])
            patched=o/'PanelFillContract.patched.exe'
            self.execute('PatchPanelFill',[ROOT/'src/rendering/PatchPanelFill.cs'],[w(fixture),w(patched),w(m.location('original')/'CW3_Data/Managed')],[m.prepare_cecil(o),'-r:System.Core'])
            m.run(patched,[])
        elif name=='CaptionLayoutContracts':self.execute(name,[runtime/'CaptionLayout.cs',test/(name+'.cs')])
        elif name=='RenderingOrderContracts':
            engine=o/'UnityEngine.dll';shutil.copy2(m.location('original')/'CW3_Data/Managed/UnityEngine.dll',engine)
            self.execute(name,[ROOT/'src/rendering/CW3Rendering.cs',test/(name+'.cs')],flags=['-r:'+w(engine)])
        else:
            flags=[m.prepare_cecil(o)]
            targets=m.location('build').parent/'generated/targets.json' if name in ('NativeNoticeContracts','ManagedDisplayContracts') and m.config.get('target_id')=='macos-steam-22453699' else ROOT/'translations/zh-CN.json'
            if name=='AssemblyStructureContracts':self.execute(name,[ROOT/'src/verification/AssemblyStructure.cs',test/(name+'.cs')],flags=flags+['-r:System.Core'])
            elif name=='GuiCaptionContracts':self.execute(name,[runtime/'GuiCaptionAudit.cs',test/(name+'.cs')],flags=flags)
            elif name=='NativeNoticeContracts':self.execute(name,[runtime/s for s in ('NativeEventCaptionAudit.cs','GuiCaptionAudit.cs','Json.cs','MessageBindings.cs')]+[test/(name+'.cs')],[w(m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll'),w(targets)],flags+['-r:System.Core'])
            elif name=='ManagedDisplayContracts':self.execute(name,[runtime/s for s in ('ManagedDisplayAudit.cs','NativeEventCaptionAudit.cs','GuiCaptionAudit.cs','Json.cs')]+[ROOT/'src/verification/BindingAnchor.cs',test/(name+'.cs')],[w(m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll'),w(targets)],flags+['-r:System.Core','-main:ManagedDisplayContracts'])
            elif name=='MainMenuClickContracts':
                menu=m.compile(o,'MainMenuClickFixture.exe',[test/'MainMenuClickFixture.cs']);patched=o/'MainMenuClickFixture.patched.exe';reversed_=o/'MainMenuClickFixture.reversed.exe'
                m.run(menu,['original']);self.execute(name,[runtime/'MainMenuClickPatch.cs',test/(name+'.cs')],[w(menu),w(patched),w(reversed_)],flags)
                m.run(patched,['patched']);m.run(reversed_,['original'])
            elif name=='MissionLoadContracts':
                fixture=m.compile(o,'MissionLoadFixture.dll',[runtime/'MissionLoads.cs',runtime/'MessageBindings.cs',test/'MissionLoadFixture.cs'],['-target:library'])
                self.execute(name,[runtime/'MissionScopePatch.cs',test/(name+'.cs')],[w(fixture),w(o)],flags+['-r:System.Core'])
            else:raise ValueError('Unknown suite: '+name)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',help='Configured Mono/game inputs; full runs default to config.local.json')
    p.add_argument('--suite',action='append',choices=SUITES,help='Repeat to select C# suites; Python checks are skipped')
    p.add_argument('--standalone',action='store_true',help='Only C# suites needing no game files, generated bindings or Cecil; uses Mono/mcs on PATH unless --config is given')
    p.add_argument('--list',action='store_true',help='List C# suites without loading config or compiling')
    a=p.parse_args()
    if a.list:
        print('\n'.join(STANDALONE if a.standalone else SUITES))
        return
    selected=list(dict.fromkeys(a.suite)) if a.suite else list(STANDALONE if a.standalone else SUITES)
    configured=any(name not in STANDALONE for name in selected)
    if a.standalone and configured:
        p.error('--standalone cannot run suites requiring configured inputs or Cecil')
    if not a.suite and not a.standalone:
        subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],cwd=ROOT,check=True)
    config=Path(a.config) if a.config else None
    if config is None and configured:
        config=ROOT/'config.local.json'
    if config is not None and not config.is_file():
        p.error('Configured suites need --config; use --standalone for game-independent C# checks')
    started=time.monotonic()
    m=MonoTools(json.loads(config.read_text())) if config is not None else MonoTools()
    with tempfile.TemporaryDirectory(prefix='cw3-contracts-')as d:
        runner=Contracts(m,Path(d))
        for name in selected:runner.suite(name)
    mode='standalone C# suites' if a.standalone else 'selected C# suites (Python skipped)' if a.suite else 'all Python checks and C# suites'
    print(f'PASS {mode}; {len(selected)} suites; {len(m.compilations)} compilations: '
          +', '.join(m.compilations)+f'; elapsed {time.monotonic()-started:.2f}s')
if __name__=='__main__':main()
