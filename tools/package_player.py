"""Package verified complete patch files with the offline install/restore entry point."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--directory-only',action='store_true');a=p.parse_args()
    config=json.loads(Path(a.config).read_text());out=Path(a.output).resolve()
    assert out.is_relative_to((ROOT/'local-only').resolve()) and not out.exists(),'Choose a new local-only output directory'
    def loc(key):
        value=Path(config[key]);return value if value.is_absolute() else ROOT/value
    build=json.loads((loc('package')/'manifest.json').read_text());supported=json.loads((ROOT/'resources/supported-build.json').read_text())
    assert build['revision']=='independent-v12-candidate','Use the current runtime source build'
    out.mkdir(parents=True)
    for row in build['files']:
        name=row['file'];source=loc('build')/name
        assert sha(source)==row['after'] and source.stat().st_size==row['bytes'],name
        if row['before']:assert sha(loc('original')/name)==row['before'],name
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        assert sha(target)==row['after'],name
    manifest=dict(format=2,name='CW3 简体中文补丁',version=build['patch_version'],runtime_files=['CW3Localization/zh-CN.json','CW3Localization/font.ttf'],exe_sha256=supported['exe_sha256'],target='Windows Steam 2.12 / build 22453699 / Unity 5.2.3f1',required_originals=build.get('required_originals',{}),files=build['files'])
    for key in ('source_repo','source_commit','source_dirty','build_inputs_sha256'):
        if key in build:manifest[key]=build[key]
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    for source,dest in [('tools/player_install.py','install.py'),('player/安装或恢复.command','安装或恢复.command'),('player/安装或恢复.cmd','安装或恢复.cmd'),('fonts/OFL.txt','OFL.txt'),('LICENSE','LICENSE'),('NOTICE.md','NOTICE.md')]:shutil.copy2(ROOT/source,out/dest)
    (out/'使用说明.txt').write_text((ROOT/'player/使用说明-v12.txt').read_text().replace(' v12\n',' '+manifest['version']+'\n',1))
    (out/'安装或恢复.command').chmod(0o755)
    if not a.directory_only:
        archive=out.with_suffix(out.suffix+'.zip')
        assert not archive.exists(),'Keep existing packages'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED)as z:
            for path in sorted(out.rglob('*')):
                if path.is_file():z.write(path,out.name+'/'+str(path.relative_to(out)))
        print('Player ZIP:',archive,archive.stat().st_size,'bytes')
    print('Prepared',len(build['files']),'verified complete patch files')
if __name__=='__main__':main()
