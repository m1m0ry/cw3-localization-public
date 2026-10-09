"""Validate explicitly reviewed CRPL output positions; never rewrite script variables."""
import hashlib,re
from resource_text import crpl_literals

def show_calls(code):
    masked=re.sub(r'"(?:\\.|[^"\\])*"|#[^\r\n]*',lambda m:' '*len(m[0]),code)
    return list(re.finditer(r'\bShowMessage(?:Dismissible)?\b',masked))

def output_definition(code,target,source):
    assert hashlib.sha256(code.encode('utf8')).hexdigest()==target['script_sha256'],'Output script drift'
    literals=crpl_literals(code)
    calls=show_calls(code)
    index=target['call_index'];assert type(index)is int and 0<=index<len(calls),'Output call drift'
    call=calls[index];parts=[];types=[]
    for part in target['parts']:
        if type(part)is int:
            hit=literals[part];assert hit.start()<call.start(),'Output fragment after call'
            parts.append(hit[0][1:-1].replace('\\n','\n').replace('\\t','\t').replace('\r\n','\n'))
        else:
            assert set(part)=={'slot','type'} and type(part['slot'])is int and part['slot']==len(types)
            assert part['type']in('number','fraction_or_blank','number_or_blank')
            types.append(part['type']);parts.append('{'+str(part['slot'])+'}')
    assert ''.join(parts)==source,'Output source does not match declared fragments'
    assert re.findall(r'\{\d+\}',source)==['{'+str(i)+'}'for i in range(len(types))]
    assert len(source)<=4096 and len(types)<=8
    return dict(script=target['script'],script_hash=target['script_sha256'],line=code[:call.start()].count('\n')+1,
                call_line=code[:call.start()].count('\n')+1,call_index=index,slots=types)
