"""Offline integration against user-supplied originals; never writes game files."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import UnityPy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import native_font_template
import style_font_resources
from mono_tools import MonoTools
from unity15_metadata import read_unity15_metadata, preserve_script_indices


def reject(call):
    try:call()
    except ValueError as error:
        assert 'platform' in str(error), str(error)
    else:raise AssertionError('A mixed or wrong platform was accepted')


def inspect_resources(original,platform,faces):
    shared_raw=(original/'CW3_Data/sharedassets0.assets').read_bytes()
    main_raw=(original/'CW3_Data/mainData').read_bytes()
    shared,_=read_unity15_metadata(shared_raw,platform)
    main,_=read_unity15_metadata(main_raw,platform)
    resources=style_font_resources.build(shared_raw,main_raw,faces,expected_platform=platform)
    changed,_=read_unity15_metadata(resources['CW3_Data/sharedassets0.assets'],platform)
    assert set(changed.objects)-set(shared.objects)==set(range(10001,10007))
    for ident,obj in shared.objects.items():
        assert obj.get_raw_data()==changed.objects[ident].get_raw_data(), ('Original payload changed',platform,ident)
    for ident in (10002,10005):
        assert changed.objects[ident].parse_as_dict()['m_Shader']==shared.objects[4].parse_as_dict()['m_Shader']
    updated,_=read_unity15_metadata(resources['CW3_Data/mainData'],platform)
    old_manager=main.objects[13].parse_as_dict()
    manager=updated.objects[13].parse_as_dict()
    extra=manager['m_Container'][len(old_manager['m_Container']):]
    assert [key for key,ref in extra]==['cw3-localization/fonts/sans','cw3-localization/fonts/serif']
    manager['m_Container']=manager['m_Container'][:len(old_manager['m_Container'])]
    assert manager==old_manager, 'Existing ResourceManager fields changed'
    for ident,obj in main.objects.items():
        if ident!=13:assert obj.get_raw_data()==updated.objects[ident].get_raw_data()
    print('PASS platform %s font resources: original objects/Shader payloads and ResourceManager fields preserved'%platform,flush=True)
    return shared_raw,main_raw


def inspect_template(original,platform,mono,out,font):
    generated=out/('NativeFontTemplate%s.cs'%platform)
    generated.write_text(native_font_template.build(original,expected_platform=platform))
    runtime=ROOT/'src/runtime'
    executable=mono.compile(out,'NativeFontBundle%s.exe'%platform,
                            [runtime/'LocalFontFile.cs',runtime/'NativeFontBundle.cs',
                             ROOT/'tests/NativeFontBundleContracts.cs',generated])
    bundle=out/('native-font-%s.bundle'%platform)
    mono.run(executable,[mono.win(font),mono.win(bundle)])
    subprocess.run([sys.executable,'-B',str(ROOT/'tests/check_native_font_bundle.py'),
                    str(bundle),str(font),'--platform',str(platform)],check=True)
    envelope=UnityPy.load(bundle.read_bytes()).file
    file=next(value for value in envelope.files.values() if hasattr(value,'objects'))
    source,_=read_unity15_metadata((original/'CW3_Data/sharedassets0.assets').read_bytes(),platform)
    font_data=source.objects[756].read_typetree()
    refs=(756,font_data['m_DefaultMaterial']['m_PathID'],font_data['m_Texture']['m_PathID'])
    for original_id,bundle_id in zip(refs,(10,11,12)):
        assert file.objects[bundle_id].serialized_type.old_type_hash==source.objects[original_id].serialized_type.old_type_hash
    # The new bundle references the selected player's built-in Shader. No Shader
    # payload from either platform is embedded in this generated envelope.
    assert all(obj.type.name!='Shader' for obj in file.objects.values())
    assert file.externals[0].path=='library/unity default resources'
    print('PASS platform %s template: C# output independently parsed; source Font/Material/Texture type hashes retained'%platform,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-original',type=Path,required=True)
    parser.add_argument('--macos-original',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'config.local.json')
    args=parser.parse_args()
    faces={'sans':ROOT/'fonts/CW3SansSC-Regular.ttf','serif':ROOT/'fonts/CW3SerifSC-Regular.ttf'}
    windows=inspect_resources(args.windows_original,5,faces)
    macos=inspect_resources(args.macos_original,2,faces)
    for shared,main_raw,platform in ((windows[0],macos[1],5),(macos[0],windows[1],2)):
        reject(lambda:style_font_resources.build(shared,main_raw,faces,expected_platform=platform))
    reject(lambda:preserve_script_indices(macos[0],windows[0],expected_platform=2))
    reject(lambda:native_font_template.build(args.macos_original,expected_platform=5))
    reject(lambda:native_font_template.build(args.windows_original,expected_platform=2))
    print('PASS mixed resource pairs and wrong-platform templates rejected',flush=True)
    mono=MonoTools(json.loads(args.config.read_text()))
    with tempfile.TemporaryDirectory(prefix='cw3-platform-resources-') as folder:
        out=Path(folder)
        inspect_template(args.windows_original,5,mono,out,faces['sans'])
        inspect_template(args.macos_original,2,mono,out,faces['sans'])
        assert (out/'NativeFontTemplate5.cs').read_bytes()!=(out/'NativeFontTemplate2.cs').read_bytes()
    print('PASS Windows/Mac offline resource contracts; no native player was started')


if __name__=='__main__':main()
