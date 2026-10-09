"""Single adopted translation source -> guarded, incremental local patch build.

check/generate require only Python's standard library. build needs UnityPy and
configured CrossOver; it never installs, translates over the network, or edits saves.
"""
from pathlib import Path
import argparse, base64, hashlib, json, re, shutil, subprocess, sys
import translation_contract
ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def encoded(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def location(config, key):
    path = Path(config[key])
    return path if path.is_absolute() else ROOT / path
def check(codepoints=None):
    doc = translation_contract.read(ROOT / 'translations/zh-CN.json')
    locks = translation_contract.read(ROOT / 'translations/targets.lock.json')
    cps = read(ROOT / 'fonts/codepoints.json') if codepoints is None else codepoints
    entries = translation_contract.check(doc, locks, cps)
    print('Checked',len(entries),'adopted targets; source/IDs, placeholders, tags and font coverage preserved')
    return entries

def generate(entries, output):
    output.mkdir(parents=True, exist_ok=True)
    for stage in ('v9','v10'):
        lines=[]
        for e in entries:
            t=e['target']
            if t['kind']=='managed' and t['stage']==stage:
                lines.append('\t'.join([str(t['method_token']),str(t['instruction_index'])]+[base64.b64encode(e[k].encode()).decode() for k in ('source','translation')]))
        (output/f'managed-{stage}.tsv').write_text('\n'.join(lines)+'\n')
    template=(ROOT/'src/display/CW3Display.cs.in').read_text()
    for e in entries:
        if e['target']['kind']=='render_map':
            token='{{'+e['id']+'}}';assert template.count(token)==1
            template=template.replace(token,json.dumps(e['translation'],ensure_ascii=False))
    assert '{{text.' not in template
    (output/'CW3Display.cs').write_text(template)

def resource(raw, rows, fixes, font):
    import struct
    from unity15_metadata import read_unity15_metadata, preserve_script_indices, verify_text_only_changes
    from resource_text import unpack_script, pack_script, patch_xml
    f,_=read_unity15_metadata(raw); original,_=read_unity15_metadata(raw); wanted={}; grouped={}
    for e in rows: grouped.setdefault(e['target']['object_id'],[]).append(e)
    for oid, entries in grouped.items():
        obj=f.objects[oid];kind=entries[0]['target']['kind']
        if kind=='label':
            assert len(entries)==1 and obj.type.name=='MonoBehaviour'
            old=obj.get_raw_data();length=struct.unpack_from('<i',old,92)[0];end=(96+length+3)&~3
            assert old[96:96+length].decode()==entries[0]['source'] and len(old)-end==64
            text=entries[0]['translation'].encode();new=old[:92]+struct.pack('<i',len(text))+text
            new+=b'\0'*((-len(new))%4)+old[end:];obj.set_raw_data(new)
        elif kind=='textmesh':
            assert len(entries)==1 and obj.type.name=='TextMesh';d=obj.parse_as_dict();assert d['m_Text']==entries[0]['source'];d['m_Text']=entries[0]['translation'];obj.patch(d)
        else:
            assert obj.type.name=='TextAsset';d=obj.parse_as_dict();d['m_Script']=pack_script(patch_xml(unpack_script(d['m_Script']),entries));obj.patch(d)
        wanted[oid]=obj.data
    for fix in fixes:
        oid=fix['object_id'];assert oid not in wanted;obj=f.objects[oid]
        if fix['kind']=='raw_fixed':
            data=bytearray(obj.get_raw_data());assert sha(data)==fix['source_sha256']
            for edit in fix['edits']:
                start=edit['offset'];before=bytes.fromhex(edit['before']);after=bytes.fromhex(edit['after']);assert len(before)==len(after) and data[start:start+len(before)]==before;data[start:start+len(before)]=after
            obj.set_raw_data(bytes(data))
        else:
            d=obj.parse_as_dict()
            for key,pair in fix['fields'].items():assert d[key]==pair['before'];d[key]=pair['after']
            obj.patch(d)
        wanted[oid]=obj.data
    if font:
        for oid in (755,756):
            obj=f.objects[oid];assert obj.type.name=='Font';d=obj.parse_as_dict();d['m_FontData']=list(font);d['m_FontNames']=['CW3 Sans SC'];obj.patch(d);wanted[oid]=obj.data
    result,corrected=preserve_script_indices(raw,f.save());verified,_=read_unity15_metadata(result)
    for oid,obj in verified.objects.items():assert obj.get_raw_data()==wanted.get(oid,original.objects[oid].get_raw_data()),('Unexpected payload',oid)
    for oid in wanted:verified.objects[oid].set_raw_data(original.objects[oid].get_raw_data())
    neutral,_=preserve_script_indices(raw,verified.save());verify_text_only_changes(raw,neutral,{})
    return result

def build(entries, config, out):
    from importlib.metadata import version
    from fontTools.ttLib import TTFont
    assert version('UnityPy') == '1.25.2', 'Use the verified UnityPy 1.25.2 writer'
    with TTFont(ROOT/'fonts/CW3SansSC-Regular.ttf') as embedded_font:
        cmap = embedded_font.getBestCmap()
        assert all(ord(ch) in cmap for e in entries for ch in e['translation'] if not ch.isspace()), 'Rebuild the actual font subset, not just its codepoint list'
    layout=read(ROOT/'resources/layout.json');original=location(config,'original');game=location(config,'game');files=layout['original_hashes']
    # Fail before building if even one original file belongs to another version.
    for name,expected in files.items():assert sha((original/name).read_bytes())==expected, 'Original version mismatch: '+name
    previous=read(out/'manifest.json') if (out/'manifest.json').exists() else None
    installed=bool(previous) and all((game/f['file']).exists() and sha((game/f['file']).read_bytes())==f['after'] for f in previous['files'])
    generated=out/'generated';generate(entries,generated);destination=out/'files';cachepath=out/'build-state.json';cache=read(cachepath) if cachepath.exists() else {};newcache={};rebuilt=[];skipped=[]
    toolhash=sha(b''.join((ROOT/'tools'/name).read_bytes() for name in ('workflow.py','resource_text.py','unity15_metadata.py')))
    font=(ROOT/'fonts/CW3SansSC-Regular.ttf').read_bytes()
    def reusable(key,fingerprint,names):
        record=cache.get(key,{})
        return record.get('input')==fingerprint and all((destination/n).exists() and sha((destination/n).read_bytes())==record.get('outputs',{}).get(n) for n in names)
    for name in files:
        if '/Managed/' in name:continue
        rows=[e for e in entries if e['target'].get('file')==name];fixes=[f for f in layout['fixed_edits'] if f['file']==name];embedded=font if name=='CW3_Data/sharedassets0.assets' else None
        fingerprint=sha(encoded([toolhash,files[name],rows,fixes,sha(embedded) if embedded else None]))
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        if reusable(name,fingerprint,[name]):skipped.append(name)
        else:
            assert not installed, 'This output is the installed recovery point; choose a new --output local-only/name'
            target.write_bytes(resource((original/name).read_bytes(),rows,fixes,embedded));rebuilt.append(name)
        newcache[name]={'input':fingerprint,'outputs':{name:sha(target.read_bytes())}}
    managed=['CW3_Data/Managed/'+name for name in ('Assembly-CSharp.dll','CW3Rendering.dll','CW3Display.dll')]
    sources=sorted((ROOT/'src').glob('*/*.cs'))+[ROOT/'src/display/CW3Display.cs.in',ROOT/'tools/build_managed.py']
    runtime=[game/'CW3_Data/Managed'/name for name in ('mscorlib.dll','UnityEngine.dll')]
    mono=location(config,'crossover')/'share/wine/mono'/config['mono_version']
    runtime += [mono/'lib/mono/4.5/mcs.exe', mono/'lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll']
    fingerprint=sha(encoded([files['CW3_Data/Managed/Assembly-CSharp.dll'],[e for e in entries if e['target']['kind'] in ('managed','render_map')],[sha(p.read_bytes()) for p in sources+runtime],config['mono_version'],str(location(config,'crossover'))]))
    if reusable('managed',fingerprint,managed):skipped+=managed
    else:
        assert not installed, 'This output is the installed recovery point; choose a new --output local-only/name'
        cfg=out/'builder-config.json';save(cfg,config)
        subprocess.run([sys.executable,str(ROOT/'tools/build_managed.py'),'--config',str(cfg),'--generated',str(generated),'--output',str(out/'managed')],check=True)
        for name in managed:
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(out/'managed'/Path(name).name,target)
        rebuilt+=managed
    newcache['managed']={'input':fingerprint,'outputs':{name:sha((destination/name).read_bytes()) for name in managed}}
    save(cachepath,newcache)
    rows=[{'file':name,'before':files.get(name),'after':sha((destination/name).read_bytes()),'bytes':(destination/name).stat().st_size} for name in list(files)+managed[1:]]
    save(out/'manifest.json',{'format':1,'revision':'source-build','steam_build':'22453699','version':'2.12 Steam','files':rows})
    installconfig=dict(config,package=str(out),build=str(destination));save(out/'install-config.json',installconfig)
    print('Rebuilt',len(rebuilt),'files:',', '.join(rebuilt));print('Reused',len(skipped),'verified files')
    print('Candidate only; game unchanged. Installer configuration:',out/'install-config.json')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check','generate','prepare','build']);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--output',default=str(ROOT/'local-only/source-build'));a=p.parse_args();entries=check();out=Path(a.output).resolve()
    assert out.is_relative_to((ROOT/'local-only').resolve()), 'Build products must stay in local-only'
    if a.action=='check':return
    if a.action=='generate':generate(entries,out/'generated');return
    config=read(a.config)
    if a.action=='prepare':
        original=location(config,'original');game=location(config,'game');files=read(ROOT/'resources/layout.json')['original_hashes']
        for name,expected in files.items():assert sha((game/name).read_bytes())==expected, 'A clean matching game is required: '+name
        for name,expected in files.items():
            dst=original/name
            if dst.exists():assert sha(dst.read_bytes())==expected
        for name in files:
            dst=original/name;dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists():shutil.copy2(game/name,dst)
        print('Prepared',len(files),'hash-verified originals');return
    build(entries,config,out)
if __name__=='__main__':main()
