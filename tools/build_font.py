"""Reproduce the OFL-only static subset from the hash-pinned official font."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib.instancer import instantiateVariableFont
import argparse,json,hashlib
R=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--external',action='store_true',help='Name subset for process-private runtime loading');p.add_argument('--external-full',action='store_true',help='Full static font for process-private runtime loading');a=p.parse_args();source=Path(a.source);out=Path(a.output);assert not out.exists();provenance=json.loads((R/'fonts/provenance.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==provenance['source_sha256'];keep=set(json.loads((R/'fonts/codepoints.json').read_text()));f=TTFont(source);
if a.external_full:keep=set(f.getBestCmap())
else:
 sub=subset.Subsetter();sub.populate(unicodes=keep);sub.subset(f)
f=instantiateVariableFont(f,{'wght':400},inplace=True)
tag=hashlib.sha256((provenance['source_sha256']+str(sorted(keep))).encode()).hexdigest()[:12]
family=('CW3 Sans SC External '+tag) if a.external_full or a.external else 'CW3 Sans SC';postscript=('CW3SansSCExternal-'+tag+'-Regular') if a.external_full or a.external else 'CW3SansSC-Regular'
external=a.external_full or a.external
platforms=({(n.platformID,n.platEncID,n.langID)for n in f['name'].names}|{(3,1,0x409),(1,0,0)}) if external else {(3,1,0x409),(1,0,0)}
for platform,enc,lang in sorted(platforms):
 for nid,value in [(1,family),(2,'Regular'),(3,family+' Regular 2.004'+('' if external else ' subset')),(4,family+' Regular'),(6,postscript),(16,family),(17,'Regular')]:f['name'].setName(value,nid,platform,enc,lang)
f['OS/2'].fsType=0;out.parent.mkdir(parents=True,exist_ok=True);f.save(out);assert 'fvar' not in f and keep<=set(f.getBestCmap());print('Static weight400; covered',len(keep),'codepoints. Retain fonts/OFL.txt when redistributing.')
