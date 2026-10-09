"""Build a separate resource candidate, preserving every non-font object and metadata."""
from pathlib import Path
import argparse
from unity15_metadata import read_unity15_metadata,preserve_script_indices,verify_text_only_changes
p=argparse.ArgumentParser();p.add_argument('input_assets');p.add_argument('output_assets');p.add_argument('--font',default=str(Path(__file__).resolve().parents[1]/'fonts/CW3SansSC-Regular.ttf'));a=p.parse_args();out=Path(a.output_assets);assert not out.exists();raw=Path(a.input_assets).read_bytes();f,_=read_unity15_metadata(raw);base,_=read_unity15_metadata(raw);wanted={};font=Path(a.font).read_bytes()
for oid in (755,756):
 obj=f.objects[oid];assert obj.type.name=='Font';d=obj.parse_as_dict();d['m_FontData']=list(font);d['m_FontNames']=['CW3 Sans SC'];obj.patch(d);wanted[oid]=obj.data
patched,_=preserve_script_indices(raw,f.save());check,_=read_unity15_metadata(patched)
for oid,obj in check.objects.items():assert obj.get_raw_data()==wanted.get(oid,base.objects[oid].get_raw_data()),oid
for oid in wanted:check.objects[oid].set_raw_data(base.objects[oid].get_raw_data())
neutral,_=preserve_script_indices(raw,check.save());verify_text_only_changes(raw,neutral,{});out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(patched);print('Only two embedded font byte arrays and font-name lists changed; other payloads/indices/links preserved.')
