"""CW3 2.12 fixed-target runtime dictionary candidate builder (no installation)."""
from pathlib import Path
import argparse, json, hashlib, struct, base64, collections, subprocess, shutil, re, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def definitions(entries,original):
    from unity15_metadata import read_unity15_metadata
    from resource_text import unpack_script, paths, scripts, crpl_literals
    files={}; docs={}; result=[]
    scenes={0:'Splash',1:'MainMenu',2:'Gal',3:'Game',4:'Results',5:'Prelude',6:'Epilogue'}
    def resource(name):
        if name not in files:files[name]=read_unity15_metadata((original/name).read_bytes())[0]
        return files[name]
    # Native Resources.Load keys, resolved through the original ResourceManager's PPtrs.
    manager=resource('CW3_Data/mainData');resource_keys=collections.defaultdict(list)
    rm=[o for o in manager.objects.values() if o.type.name=='ResourceManager'];assert len(rm)==1
    for key,ref in rm[0].parse_as_dict()['m_Container']:
        file='CW3_Data/'+manager.externals[ref['m_FileID']-1].path if ref['m_FileID'] else 'CW3_Data/mainData'
        resource_keys[(file,ref['m_PathID'])].append(key)
    def object_path(f,gid):
        go=f.objects[gid].parse_as_dict();tid=next(v['m_PathID'] for k,v in go['m_Component'] if k==4)
        t=f.objects[tid].parse_as_dict();parent=t['m_Father']['m_PathID']
        return (object_path(f,f.objects[parent].parse_as_dict()['m_GameObject']['m_PathID'])+'/' if parent else '')+go['m_Name']
    for e in entries:
        t=e['target'];d={k:e[k] for k in ('id','source')};d['kind']=t['kind']
        if t['kind']=='managed':d.update(site=str(t['method_token'])+':'+str(t['instruction_index']),stage=t['stage'])
        if t['kind'] in ('label','textmesh'):
            f=resource(t['file']);o=f.objects[t['object_id']]
            gid=struct.unpack_from('<q',o.get_raw_data(),4)[0] if t['kind']=='label' else o.parse_as_dict()['m_GameObject']['m_PathID']
            d['path']=object_path(f,gid);name=Path(t['file']).name
            d['scene']=scenes[int(name[5:])] if name.startswith('level') else 'Splash' if name=='mainData' else '*'
            # This prefab is instantiated in Epilogue; Prelude has its own scene object.
            if name=='sharedassets6.assets':d['scene']='Epilogue'
        elif t['kind'] in ('xml_text','crpl','crpl_display','crpl_conversation','crpl_output'):
            key=(t['file'],t['object_id'])
            if key not in docs:
                asset=resource(t['file']).objects[t['object_id']].parse_as_dict();root=ET.fromstring(unpack_script(asset['m_Script']));docs[key]=(root,dict(paths(root)),{c:p for p in root.iter() for c in p},hashlib.sha256(asset['m_Script'].encode('utf8','surrogateescape')).hexdigest())
            root,nodes,parents,resource_hash=docs[key];node=nodes[t['xml_path']]
            if t['kind']=='crpl_output':
                from script_outputs import output_definition
                code=base64.b64decode(scripts(node.text)[t['script']]).decode('utf-16le')
                d.update(output_definition(code,t,e['source']))
            elif t['kind'] in ('crpl','crpl_display','crpl_conversation'):
                code=base64.b64decode(scripts(node.text)[t['script']]).decode('utf-16le');hit=crpl_literals(code)[t['literal_index']]
                assert hit.group()[1:-1]==e['source']
                prefix=code[:hit.start()];suffix=code[hit.end():]
                function=re.search(r'(AddConversationMessage|ShowMessage(?:Dismissible)?)\(\s*[^"()\n]*$',prefix)
                postfix=re.match(r'\s*(?:-?\d+\s+|(?:Screen\w+\s+|\d+\s+sub\s+))*(AddConversationMessage|ShowMessage(?:Dismissible)?)\b',suffix)
                assert function or postfix, 'No declared script display call'
                call_offset=function.start() if function else hit.end()+postfix.start(1)
                d.update(script=t['script'],script_hash=digest(code),line=code[:hit.start()].count('\n')+1,
                         literal_index=t['literal_index'],call_line=code[:call_offset].count('\n')+1)
            elif node.tag=='m':
                group=parents[parents[node]];messages=[m.find('m') for m in group if m.tag=='Message'];assert all(n is not None for n in messages)
                owner=parents[group]
                if owner.tag=='System':
                    assert owner is root;message_list='system'
                elif owner.tag=='Info':
                    assert parents[owner] is root;message_list='mission'
                else:
                    assert owner.tag=='MessageArtifact' and owner.findtext('uid') is not None
                    assert parents[owner].tag=='Units' and parents[parents[owner]] is root
                    message_list='artifact:'+str(int(owner.findtext('uid')))
                keys=resource_keys[(t['file'],t['object_id'])];assert len(keys)==1, 'Ambiguous native resource key'
                d.update(resource=t['file']+':'+str(t['object_id']),resource_key=keys[0],
                         resource_sha256=resource_hash,
                         message_list=message_list,index=messages.index(node))
            else:
                owner=parents[node];guid=owner.findtext('u' if owner.tag=='ShieldKey' else 'g');assert guid
                assert owner.tag in ('Planet','Star','Wormhole','ShieldKey'), 'Declared display name owner'
                d.update(guid=guid,owner={'Planet':'PlanetManager','Star':'StarManager','Wormhole':'StarManager','ShieldKey':'ShieldKeyManager'}[owner.tag])
        if t['kind'] in ('render_map','label_display'):d.update(selector=t['selector'],match=t['match'])
        result.append(d)
    bindings=collections.defaultdict(list)
    for d in result:
        if d['kind'] in ('label','textmesh'):key=(d['kind'],d['scene'],d['path'],d['source'])
        elif d['kind']=='xml_text':key=('xml',d.get('resource'),d.get('message_list'),d.get('index'),d.get('owner'),d.get('guid'))
        elif d['kind']=='crpl_output':key=('output',d['script'],d['script_hash'],d['call_index'],d['source'])
        elif d['kind'] in ('crpl','crpl_display','crpl_conversation'):
            family='conversation' if d['kind']=='crpl_conversation' else 'show'
            source=d['source'].replace('\r\n','\n') if family=='conversation' else d['source'].replace('\\n','\n').replace('\\t','\t')
            key=(family,d['script'],d['script_hash'],d['call_line'],source)
        else:continue
        bindings[key].append(d['id'])
    assert all(len(v)==1 for v in bindings.values()),[(k,v) for k,v in bindings.items() if len(v)>1]
    return result

def resource_plan(layout):
    # Serialize only resources with an actual declared repair or embedded font replacement.
    for name in layout['original_hashes']:
        if '/Managed/' in name: continue
        fixes=[f for f in layout['fixed_edits'] if f['file']==name]
        embedded=name=='CW3_Data/sharedassets0.assets'
        if fixes or embedded: yield name,fixes,embedded

def build(config,out):
    import workflow
    from fontTools.ttLib import TTFont
    with TTFont(ROOT/'local-only/independent-font/font.ttf') as external_font:cps=set(external_font.getBestCmap())
    entries=workflow.check(cps);original=workflow.location(config,'original');layout=workflow.read(ROOT/'resources/layout.json')
    for name,sha in layout['original_hashes'].items():assert workflow.sha((original/name).read_bytes())==sha,name
    assert not (out/'manifest.json').exists(),'Keep the installed recovery point; choose a new output'
    out.mkdir(parents=True,exist_ok=True);dest=out/'files';generated=out/'generated';generated.mkdir(exist_ok=True)
    defs=definitions(entries,original);(out/'bindings.json').write_text(json.dumps(defs,ensure_ascii=False,indent=2)+'\n')
    payload=base64.b64encode(json.dumps(defs,ensure_ascii=False,separators=(',',':')).encode()).decode()
    (generated/'Definitions.cs').write_text('internal static class CW3Definitions { internal const string Data="'+payload+'"; }\n')
    rows=[]
    for e in entries:
        t=e['target']
        if t['kind']=='managed':rows.append('\t'.join([str(t['method_token']),str(t['instruction_index']),e['id'],base64.b64encode(e['source'].encode()).decode(),t['stage'], 'event' if e['context'].startswith('Native event caption / ') else 'gui' if e['context'].startswith('GUI caption / ') else 'label' if e['context'].startswith('UILabel caption / ') else '']))
    (generated/'managed.tsv').write_text('\n'.join(rows)+'\n');(generated/'empty.tsv').write_text('')
    planned=list(resource_plan(layout));changed_names={name for name,fixes,embedded in planned}
    required_originals={name:sha for name,sha in layout['original_hashes'].items() if '/Managed/' not in name and name not in changed_names}
    for name,fixes,embedded in planned:
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
        # Keep every serialized text/script original; retain only actual font/layout repairs.
        raw=(original/name).read_bytes()
        updated=workflow.resource(raw,[],fixes,(ROOT/'fonts/CW3SansSC-Regular.ttf').read_bytes() if embedded else None)
        if updated==raw:required_originals[name]=layout['original_hashes'][name]
        else:target.write_bytes(updated)
    cfg=out/'builder-config.json';workflow.save(cfg,config)
    subprocess.run([__import__('sys').executable,str(ROOT/'tools/build_independent.py'),'--config',str(cfg),'--generated',str(generated),'--output',str(out/'managed')],check=True)
    for name in ('Assembly-CSharp.dll','CW3Rendering.dll','CW3Runtime.dll'):
        target=dest/'CW3_Data/Managed'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(out/'managed'/name,target)
    d=dest/'CW3Localization';d.mkdir(exist_ok=True);shutil.copy2(ROOT/'translations/zh-CN.json',d/'zh-CN.json');shutil.copy2(ROOT/'fonts/OFL.txt',d/'OFL.txt')
    # Full OFL source-derived font is prepared separately and hash-checked by the font tool.
    font=ROOT/'local-only/independent-font/font.ttf';assert font.exists(),'Prepare the full static OFL font first';shutil.copy2(font,d/'font.ttf')
    rows=[{'file':str(p.relative_to(dest)),'before':layout['original_hashes'].get(str(p.relative_to(dest))),'after':workflow.sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file()]
    workflow.save(out/'manifest.json',{'source_dirty':subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode!=0,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'format':1,'revision':'independent-v12-candidate','patch_version':config.get('patch_version','v12.3'),'steam_build':'22453699','version':'2.12 Steam','required_originals':required_originals,'files':rows})
    workflow.save(out/'install-config.json',dict(config,package=str(out),build=str(dest)))
    print('Prepared',len(defs),'fixed runtime targets;',len(rows),'candidate files; original texts/scripts preserved. Game unchanged.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));p.add_argument('--version',default='v12.3');p.add_argument('--output',default=str(ROOT/'local-only/independent-v12'));a=p.parse_args();out=Path(a.output).resolve();assert out.is_relative_to(ROOT/'local-only');build(dict(json.loads(Path(a.config).read_text()),patch_version=a.version),out)
