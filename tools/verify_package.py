"""Exercise the shipped complete-file install/restore on a disposable original fixture."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--package',required=True);a=p.parse_args();c=json.loads(Path(a.config).read_text())
    def loc(key):
        path=Path(c[key]);return path if path.is_absolute() else ROOT/path
    manifest=json.loads((loc('package')/'manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='cw3-package-gate-')as folder:
        tmp=Path(folder)
        with zipfile.ZipFile(a.package)as z:
            names=z.namelist();assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
            z.extractall(tmp/'package')
        package=next((tmp/'package').iterdir());player=json.loads((package/'manifest.json').read_text())
        assert player['format']==2 and player['version']==manifest['patch_version']
        assert player.get('required_originals',{})==manifest.get('required_originals',{})
        assert player['files']==manifest['files']
        controls={'manifest.json','install.py','安装或恢复.command','安装或恢复.cmd','使用说明.txt','OFL.txt','LICENSE','NOTICE.md'}
        assert {str(p.relative_to(package))for p in package.rglob('*')if p.is_file()}=={f['file']for f in manifest['files']}|controls
        for row in player['files']:assert sha(package/row['file'])==row['after'],row['file']
        exe=loc('game')/'CW3.exe';assert sha(exe)==player['exe_sha256']
        game=tmp/'game';game.mkdir();shutil.copy2(exe,game/'CW3.exe')
        originals={r['file']:r['before']for r in manifest['files']if r['before']};originals.update(manifest.get('required_originals',{}))
        for name,expected in originals.items():
            source=loc('original')/name;assert sha(source)==expected
            target=game/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        sentinel=game/'fixture-save.dat';sentinel.write_bytes(b'UNCHANGED SAVE SENTINEL')
        def run(action):subprocess.run([sys.executable,str(package/'install.py'),'--game',str(game),'--action',action],check=True,timeout=180)
        run('install');assert all(sha(game/r['file'])==r['after']for r in manifest['files'])
        run('restore');assert all(sha(game/r['file'])==r['before']for r in manifest['files'])
        assert all(sha(game/name)==expected for name,expected in originals.items())
        assert sentinel.read_bytes()==b'UNCHANGED SAVE SENTINEL'
    print('PASS shipped complete-file CLI install/restore and every payload hash; installed game untouched.')
if __name__=='__main__':main()
