"""Default: all Python/C# checks. --suite: only selected C# suites and their fixtures."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile
from mono_tools import MonoTools
ROOT=Path(__file__).resolve().parents[1]
POLICY={
    'CandidateContracts':['Candidates.cs','Json.cs'],
    'RuntimeContracts':['Json.cs','FontFile.cs'],
    'MessageContracts':['Json.cs','MessageBindings.cs'],
    'ScriptContracts':['Json.cs','MessageBindings.cs','ScriptBindings.cs'],
    'MessageCandidateContracts':['Json.cs','MessageBindings.cs','Candidates.cs']}
SUITES=tuple(POLICY)+('CaptionLayoutContracts','RenderingOrderContracts','GuiCaptionContracts','NativeNoticeContracts','MainMenuClickContracts','MissionLoadContracts','ManagedDisplayContracts')
class Contracts:
    def __init__(self,mono,out):self.mono=mono;self.out=out
    def execute(self,name,sources,args=(),flags=()):
        exe=self.mono.compile(self.out,name+'.exe',sources,flags);self.mono.run(exe,args)
    def suite(self,name):
        m=self.mono;o=self.out;runtime=ROOT/'src/runtime';test=ROOT/'tests';w=m.win
        print('RUN '+name,flush=True)
        if name in POLICY:
            sources=[runtime/s for s in POLICY[name]]+[test/(name+'.cs')]
            args=[]
            if name=='CandidateContracts':args=[w(o)]
            elif name=='RuntimeContracts':args=[w(m.location('build')/'CW3Localization/font.ttf'),w(ROOT/'fonts/CW3SansSC-Regular.ttf'),w(o),w(test/'json_rejected.json')]
            else:
                sources.append(m.location('build').parent/'generated/Definitions.cs')
                args=[w(o/'message-candidates.json')] if name=='MessageCandidateContracts' else [w(ROOT/'translations/zh-CN.json')]
            self.execute(name,sources,args)
            if name=='MessageCandidateContracts':subprocess.run([sys.executable,str(test/'check_candidate_pipeline.py'),str(o/'message-candidates.json'),str(o)],check=True)
        elif name=='CaptionLayoutContracts':self.execute(name,[runtime/'CaptionLayout.cs',test/(name+'.cs')])
        elif name=='RenderingOrderContracts':
            engine=o/'UnityEngine.dll';shutil.copy2(m.location('game')/'CW3_Data/Managed/UnityEngine.dll',engine)
            self.execute(name,[ROOT/'src/rendering/CW3Rendering.cs',test/(name+'.cs')],flags=['-r:'+w(engine)])
        else:
            flags=[m.prepare_cecil(o)]
            if name=='GuiCaptionContracts':self.execute(name,[runtime/'GuiCaptionAudit.cs',test/(name+'.cs')],flags=flags)
            elif name=='NativeNoticeContracts':self.execute(name,[runtime/s for s in ('NativeEventCaptionAudit.cs','GuiCaptionAudit.cs','Json.cs','MessageBindings.cs')]+[test/(name+'.cs')],[w(m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll'),w(ROOT/'translations/zh-CN.json')],flags+['-r:System.Core'])
            elif name=='ManagedDisplayContracts':self.execute(name,[runtime/s for s in ('ManagedDisplayAudit.cs','NativeEventCaptionAudit.cs','GuiCaptionAudit.cs','Json.cs')]+[test/(name+'.cs')],[w(m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll'),w(m.location('build').parent/'managed/render.dll'),w(ROOT/'translations/zh-CN.json')],flags+['-r:System.Core','-main:ManagedDisplayContracts'])
            elif name=='MainMenuClickContracts':
                menu=m.compile(o,'MainMenuClickFixture.exe',[test/'MainMenuClickFixture.cs']);patched=o/'MainMenuClickFixture.patched.exe';reversed_=o/'MainMenuClickFixture.reversed.exe'
                m.run(menu,['original']);self.execute(name,[runtime/'MainMenuClickPatch.cs',test/(name+'.cs')],[w(menu),w(patched),w(reversed_)],flags)
                m.run(patched,['patched']);m.run(reversed_,['original'])
            elif name=='MissionLoadContracts':
                fixture=m.compile(o,'MissionLoadFixture.dll',[runtime/'MissionLoads.cs',runtime/'MessageBindings.cs',test/'MissionLoadFixture.cs'],['-target:library'])
                self.execute(name,[runtime/'MissionScopePatch.cs',test/(name+'.cs')],[w(fixture),w(o)],flags+['-r:System.Core'])
            else:raise ValueError('Unknown suite: '+name)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--suite',action='append',choices=SUITES,help='Repeat to select C# suites; Python checks are skipped');p.add_argument('--list',action='store_true',help='List C# suites without loading config or compiling');a=p.parse_args()
    if a.list:print('\n'.join(SUITES));return
    selected=list(dict.fromkeys(a.suite)) if a.suite else list(SUITES)
    if not a.suite:subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],cwd=ROOT,check=True)
    m=MonoTools(json.loads(Path(a.config).read_text()))
    with tempfile.TemporaryDirectory(prefix='cw3-contracts-')as d:
        runner=Contracts(m,Path(d))
        for name in selected:runner.suite(name)
    print('PASS '+('selected C# suites (Python skipped)' if a.suite else 'all Python checks and C# suites')+'; '+str(len(selected))+' suites; '+str(len(m.compilations))+' compilations: '+', '.join(m.compilations))
if __name__=='__main__':main()
