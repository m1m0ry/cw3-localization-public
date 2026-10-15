"""Check adopted translations, prepare locked originals and repair resources.

Candidate builds use tools/independent.py; serialized text/scripts stay original.
"""
from pathlib import Path
import argparse, hashlib, json, shutil
import translation_contract
ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_text())
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

def repair_resource(raw, fixes, font):
    """Apply declared layout/font repairs while preserving all other payloads."""
    from unity15_metadata import read_unity15_metadata, preserve_script_indices, verify_text_only_changes
    f,_=read_unity15_metadata(raw); original,_=read_unity15_metadata(raw); wanted={}
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

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check','prepare']);p.add_argument('--config',default=str(ROOT/'config.local.json'));a=p.parse_args();check()
    if a.action=='check':return
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
if __name__=='__main__':main()
