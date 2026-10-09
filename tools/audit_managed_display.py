"""Inventory original CW3 ldstr sites; report bindings and evidence without translating."""
from pathlib import Path
import argparse,base64,collections,hashlib,json,tempfile
from mono_tools import MonoTools,ROOT
import translation_contract
sha=lambda data:hashlib.sha256(data).hexdigest()
CATEGORIES=('bound','display_candidate','internal_identifier','unknown')
def rows(text):
    result=[]
    for line in text.splitlines():
        c=line.split('\t');assert len(c)==11,'Invalid Cecil audit row'
        category,analysis=c[:2];assert category in CATEGORIES and analysis in CATEGORIES[1:]
        decode=lambda n:base64.b64decode(c[n],validate=True).decode('utf8')
        source=decode(6)
        result.append(dict(classification=category,analysis=analysis,method_token=int(c[2]),instruction_index=int(c[3]),il_offset=int(c[4]),method=decode(5),source=source,source_sha256=sha(source.encode()),consumer=decode(7),reason=decode(8),binding_id=decode(9)or None,binding_stage=c[10]or None))
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--render',help='Override the matching pre-runtime render.dll');p.add_argument('--output',required=True,help='New local-only JSON report');a=p.parse_args()
    output=Path(a.output).resolve()
    if not output.is_relative_to((ROOT/'local-only').resolve())or output.exists():p.error('Choose a new local-only JSON report')
    m=MonoTools(json.loads(Path(a.config).read_text()));original=m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll';render=Path(a.render).resolve()if a.render else m.location('build').parent/'managed/render.dll'
    if not render.is_file():p.error('Matching render.dll missing; use an independent candidate config or --render. This audit does not build it.')
    original_hash=sha(original.read_bytes());render_hash=sha(render.read_bytes());expected=json.loads((ROOT/'resources/layout.json').read_text())['original_hashes']['CW3_Data/Managed/Assembly-CSharp.dll']
    if original_hash!=expected:p.error('Original Assembly-CSharp.dll hash does not match the supported build')
    dictionary=ROOT/'translations/zh-CN.json';data=dictionary.read_bytes();doc=translation_contract.loads(data.decode());translation_contract.check(doc,translation_contract.read(ROOT/'translations/targets.lock.json'),json.loads((ROOT/'fonts/codepoints.json').read_text()))
    with tempfile.TemporaryDirectory(prefix='cw3-il-audit-')as d:
        out=Path(d);snapshot=out/'dictionary.json';snapshot.write_bytes(data)
        exe=m.compile(out,'ManagedDisplayAudit.exe',[ROOT/'src/runtime'/n for n in ('ManagedDisplayAudit.cs','GuiCaptionAudit.cs','NativeEventCaptionAudit.cs','Json.cs')],[m.prepare_cecil(out),'-r:System.Core'])
        run=m.run(exe,[m.win(original),m.win(render),m.win(snapshot)],capture=True);findings=rows(run.stdout)
    if sha(original.read_bytes())!=original_hash or sha(render.read_bytes())!=render_hash:raise RuntimeError('Assembly input changed during audit; report not written')
    counts={c:0 for c in CATEGORIES};counts.update(collections.Counter(row['classification']for row in findings))
    report=dict(format=1,assembly_sha256=original_hash,render_sha256=render_hash,dictionary_sha256=sha(data),counts=counts,total_ldstr=len(findings),boundaries=['Literal inventory only: reflection, external data and strings generated without ldstr are outside coverage.','Display consumers do not prove normal-game reachability, need for translation, rendering or clicks.','Explicit key/comparison patterns only; unknown consumers, branches and mixed uses stay unknown.','v10 bindings map to original sites only when the entire method ldstr sequence matches the render stage.','No translations, locks, assemblies or game files are changed.'],entries=findings)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x')as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print('Read-only IL audit:',json.dumps(counts),'total',len(findings));print('Report:',output)
if __name__=='__main__':main()
