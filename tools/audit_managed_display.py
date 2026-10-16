"""Inventory original CW3 ldstr sites; report bindings and evidence without translating."""
from pathlib import Path
import argparse,base64,collections,hashlib,json,tempfile
from mono_tools import MonoTools,ROOT
import translation_contract
import game_target
sha=lambda data:hashlib.sha256(data).hexdigest()
CATEGORIES=('bound','display_candidate','internal_identifier','unknown')
def audit_dictionary(original,doc,target):
    names=None if target['platform']==2 else ['CW3_Data/Managed/Assembly-CSharp.dll']
    game_target.verify_inputs(original,target,names)
    if target['platform']==2:
        from target_bindings import resolve
        return dict(doc,entries=resolve(doc['entries'],original,target))
    return doc

def rows(text):
    result=[]
    for line in text.splitlines():
        c=line.split('\t');assert len(c)==10,'Invalid Cecil audit row'
        category,analysis=c[:2];assert category in CATEGORIES and analysis in CATEGORIES[1:]
        decode=lambda n:base64.b64decode(c[n],validate=True).decode('utf8')
        source=decode(6)
        result.append(dict(classification=category,analysis=analysis,method_token=int(c[2]),instruction_index=int(c[3]),il_offset=int(c[4]),method=decode(5),source=source,source_sha256=sha(source.encode()),consumer=decode(7),reason=decode(8),binding_id=decode(9)or None))
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--output',required=True,help='New local-only JSON report');a=p.parse_args()
    output=Path(a.output).resolve()
    if not output.is_relative_to((ROOT/'local-only').resolve())or output.exists():p.error('Choose a new local-only JSON report')
    config=json.loads(Path(a.config).read_text());target=game_target.load(config);m=MonoTools(config);original=m.location('original')/'CW3_Data/Managed/Assembly-CSharp.dll'
    dictionary=ROOT/'translations/zh-CN.json';data=dictionary.read_bytes();doc=translation_contract.loads(data.decode());translation_contract.check(doc,translation_contract.read(ROOT/'translations/targets.lock.json'),json.loads((ROOT/'fonts/codepoints.json').read_text()))
    resolved=audit_dictionary(m.location('original'),doc,target);original_hash=sha(original.read_bytes())
    with tempfile.TemporaryDirectory(prefix='cw3-il-audit-')as d:
        out=Path(d);snapshot=out/'dictionary.json';snapshot.write_text(json.dumps(resolved,ensure_ascii=False))
        exe=m.compile(out,'ManagedDisplayAudit.exe',[ROOT/'src/runtime'/n for n in ('ManagedDisplayAudit.cs','GuiCaptionAudit.cs','NativeEventCaptionAudit.cs','Json.cs')]+[ROOT/'src/verification/BindingAnchor.cs'],[m.prepare_cecil(out),'-r:System.Core'])
        run=m.run(exe,[m.win(original),m.win(snapshot)],capture=True);findings=rows(run.stdout)
    if sha(original.read_bytes())!=original_hash:raise RuntimeError('Assembly input changed during audit; report not written')
    counts={c:0 for c in CATEGORIES};counts.update(collections.Counter(row['classification']for row in findings))
    report=dict(format=1,assembly_sha256=original_hash,dictionary_sha256=sha(data),counts=counts,total_ldstr=len(findings),boundaries=['Literal inventory only: reflection, external data and strings generated without ldstr are outside coverage.','Display consumers do not prove normal-game reachability, need for translation, rendering or clicks.','Explicit key/comparison patterns only; unknown consumers, branches and mixed uses stay unknown.','Managed bindings require exact pristine method signatures, sources and IL anchors.','No translations, locks, assemblies or game files are changed.'],entries=findings)
    report.update(target_id=target['target_id'],platform=target['platform'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x')as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print('Read-only IL audit:',json.dumps(counts),'total',len(findings));print('Report:',output)
if __name__=='__main__':main()
