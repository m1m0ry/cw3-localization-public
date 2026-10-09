"""Configured Mono compiler/runtime for owned test and metadata executables."""
from pathlib import Path
import shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
class MonoTools:
    def __init__(self,config):
        self.config=config;self.compilations=[]
        if config.get('mono_runtime'):
            self.runtime=self.location('mono_runtime');self.compiler=self.location('mono_compiler');self.cecil=self.location('cecil');self.native=True
        else:
            self.runtime=self.location('crossover')/'bin/wine';mono=self.location('crossover')/'share/wine/mono'/config['mono_version']
            self.compiler=mono/'lib/mono/4.5/mcs.exe';self.cecil=self.location('cecil') if config.get('cecil') else mono/'lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll';self.native=False
    def location(self,key):
        p=Path(self.config[key]);return p if p.is_absolute() else ROOT/p
    def win(self,path):
        p=Path(path).resolve();return str(p) if self.native else 'Z:'+str(p).replace('/','\\')
    def run(self,exe,args=(),capture=False):
        if not self.runtime.is_file():raise FileNotFoundError('Configured runtime missing: '+str(self.runtime))
        command=[str(self.runtime),str(exe)] if self.native else [str(self.runtime),'--bottle',self.config.get('bottle','Steam'),'--no-update','--no-gui',str(exe)]
        result=subprocess.run([*command,*args],capture_output=capture,text=True,timeout=60)
        if result.returncode and capture:raise RuntimeError(result.stdout+result.stderr)
        result.check_returncode();return result
    def prepare_cecil(self,out):
        target=out/'Mono.Cecil.dll'
        if not target.exists():shutil.copy2(self.cecil,target)
        return '-r:'+self.win(target)
    def compile(self,out,name,sources,flags=()):
        if not self.compiler.is_file():raise FileNotFoundError('Configured compiler missing: '+str(self.compiler))
        target=out/name;print('COMPILE '+name,flush=True)
        self.run(self.compiler,['-nologo',*flags,'-out:'+self.win(target),*[self.win(p) for p in sources]])
        self.compilations.append(name);return target
