"""Read-only audit of CW3 2.12 bundled message bodies and script display calls, including variable and concatenated outputs."""
from pathlib import Path
import argparse,base64,collections,json,re,xml.etree.ElementTree as ET
from resource_text import unpack_script,paths,scripts,crpl_literals
ROOT=Path(__file__).resolve().parents[1]

def display_calls(code):
    # CW3's lexer treats # outside quotes as a comment. Preserve offsets and line numbers.
    clean=list(code);quoted=False;comment=False
    for i,ch in enumerate(code):
        if ch=='\n':comment=False
        if ch=='"' and not comment:quoted=not quoted
        if ch=='#' and not quoted:comment=True
        if comment and ch!='\n':clean[i]=' '
    clean=''.join(clean)
    for index,hit in enumerate(crpl_literals(code)):
        if clean[hit.start()]!='"':continue
        prefix=clean[:hit.start()];suffix=clean[hit.end():]
        function=re.search(r'(AddConversationMessage|ShowMessage(?:Dismissible)?)\(\s*[^"()\n]*$',prefix)
        postfix=re.match(r'\s*(?:-?\d+\s+|(?:Screen\w+\s+|\d+\s+sub\s+))*(AddConversationMessage|ShowMessage(?:Dismissible)?)\b',suffix)
        call=function.group(1) if function else postfix.group(1) if postfix else None
        if call:yield index,'conversation' if call=='AddConversationMessage' else 'show',hit.group()[1:-1]

def audit(original,entries):
    from unity15_metadata import read_unity15_metadata
    resources={};counts=collections.Counter();missing=[]
    def resource(name):
        if name not in resources:resources[name]=read_unity15_metadata((original/name).read_bytes())[0]
        return resources[name]
    targets={};outputs=collections.defaultdict(list)
    for e in entries:
        t=e['target']
        if t['kind']=='crpl_output':
            outputs[(t['file'],t['object_id'],t['xml_path'],t['script'],t['call_index'])].append(e);continue
        if t['kind'] not in ('xml_text','crpl','crpl_display','crpl_conversation'):continue
        key=(t['file'],t['object_id'],t['xml_path'],t.get('script'),t.get('literal_index'))
        assert key not in targets,'Duplicate resource display target';targets[key]=e
    main=resource('CW3_Data/mainData');manager=next(o for o in main.objects.values() if o.type.name=='ResourceManager')
    def check(key,source,context,family):
        counts[family]+=1;e=targets.get(key)
        if e is None:missing.append(dict(family=family,context=context,source=source));return
        assert e['source']==source,'Source drift: '+e['id']
        if family=='conversation':assert e['target']['kind']=='crpl_conversation'
        elif family=='show':assert e['target']['kind'] in ('crpl','crpl_display')
    for name,ref in manager.parse_as_dict()['m_Container']:
        if name.startswith('credits'):continue
        file='CW3_Data/'+main.externals[ref['m_FileID']-1].path if ref['m_FileID'] else 'CW3_Data/mainData'
        obj=resource(file).objects[ref['m_PathID']]
        if obj.type.name!='TextAsset':continue
        try:root=ET.fromstring(unpack_script(obj.parse_as_dict()['m_Script']))
        except (ET.ParseError,UnicodeError,__import__('lzma').LZMAError):continue
        counts['resources']+=1;parents={c:p for p in root.iter() for c in p}
        for xp,node in paths(root):
            if node.tag=='m' and parents.get(node) is not None and parents[node].tag=='Message' and re.search('[A-Za-z\u3400-\u9fff]',node.text or ''):
                check((file,ref['m_PathID'],xp,None,None),node.text,name+'/'+xp,'xml_message')
            if node.tag!='scripts' or not (node.text or '').strip():continue
            for script,encoded in scripts(node.text).items():
                code=base64.b64decode(encoded,validate=True).decode('utf-16le')
                from script_outputs import show_calls,output_definition
                calls=show_calls(code);registered=set();literals=crpl_literals(code)
                for index,family,source in display_calls(code):
                    if re.search('[A-Za-z\u3400-\u9fff]',source):check((file,ref['m_PathID'],xp,script,index),source,name+'/'+script+' literal '+str(index),family)
                    if family=='show':
                        hit=literals[index];function=re.search(r'(ShowMessage(?:Dismissible)?)\(\s*[^"()\n]*$',code[:hit.start()]);postfix=re.match(r'\s*(?:-?\d+\s+|(?:Screen\w+\s+|\d+\s+sub\s+))*(ShowMessage(?:Dismissible)?)\b',code[hit.end():])
                        offset=function.start() if function else hit.end()+postfix.start(1)
                        registered.update(i for i,c in enumerate(calls)if c.start()==offset)
                for ordinal,call in enumerate(calls):
                    counts['show_call_positions']+=1;key=(file,ref['m_PathID'],xp,script,ordinal)
                    rows=outputs.get(key,[])
                    for row in rows:output_definition(code,row['target'],row['source'])
                    if rows:counts['reviewed_output_positions']+=1
                    if ordinal not in registered and not rows:missing.append(dict(family='show_output',context=name+'/'+script+' output '+str(ordinal+1),source='variable/concatenated output requires source review'))
    return dict(counts=dict(counts),missing=missing)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(ROOT/'config.local.json'));a=p.parse_args()
    config=json.loads(Path(a.config).read_text());original=Path(config['original']);original=original if original.is_absolute() else ROOT/original
    result=audit(original,json.loads((ROOT/'translations/zh-CN.json').read_text())['entries']);print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['missing']:raise SystemExit(1)
