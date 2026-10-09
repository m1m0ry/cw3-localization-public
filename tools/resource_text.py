"""CW3 display text boundaries; compressed XML and CRPL code stay structurally intact."""
from collections import Counter
from xml.sax.saxutils import escape
import base64,lzma,re,struct,xml.etree.ElementTree as ET
LITERAL=re.compile(r'"(?:\\.|[^"\\])*"')
def paths(node,path=None):
 path=path or '/'+node.tag;yield path,node;counts=Counter()
 for child in node:counts[child.tag]+=1;yield from paths(child,path+'/'+child.tag+f'[{counts[child.tag]}]')
def spans(xml):
 assert '<![CDATA[' not in xml;result={};stack=[]
 for m in re.finditer(r'<(/?)([A-Za-z_][\w:.-]*)(?:\s[^>]*)?(/?)>',xml):
  closing,tag,_=m.groups()
  if closing:
   top=stack.pop();assert top['tag']==tag
   if not top['child']:result[top['path']]=(top['start'],m.start())
  else:
   if stack:
    p=stack[-1];p['child']=True;p['counts'][tag]+=1;path=p['path']+'/'+tag+f'[{p["counts"][tag]}]'
   else:path='/'+tag
   if not m.group(0).endswith('/>'):stack.append({'tag':tag,'path':path,'start':m.end(),'counts':Counter(),'child':False})
 assert not stack;return result
def unpack_script(data):return lzma.decompress(data.encode('utf8','surrogateescape')).decode('utf8')
def pack_script(xml):
 raw=xml.encode();z=lzma.compress(raw,format=lzma.FORMAT_ALONE,filters=[{'id':lzma.FILTER_LZMA1,'dict_size':8388608,'lc':3,'lp':0,'pb':2}]);return (z[:5]+struct.pack('<Q',len(raw))+z[13:]).decode('utf8','surrogateescape')
def scripts(container):return dict(x.split(';',1) for x in container.split(','))
def crpl_literals(code):return list(LITERAL.finditer(code))
def patch_xml(xml,entries):
 before=dict(paths(ET.fromstring(xml)));positions=spans(xml);replacements={};crpl={}
 for e in entries:
  t=e['target'];xp=t['xml_path'];node=before[xp]
  if t['kind']=='xml_text':
   assert node.tag in ('m','n') and node.text==e['source'];replacements[xp]=e['translation']
  else:
   assert node.tag=='scripts';crpl.setdefault(xp,[]).append(e)
 for xp,rows in crpl.items():
  old=before[xp].text;container=old;byname={}
  for e in rows:byname.setdefault(e['target']['script'],[]).append(e)
  for name,items in byname.items():
   hits=list(re.finditer(re.escape(name)+r';([A-Za-z0-9+/=]+)',container));assert len(hits)==1;hit=hits[0];code=base64.b64decode(hit[1],validate=True).decode('utf-16le');original=code;literals=crpl_literals(code)
   for e in sorted(items,key=lambda x:x['target']['literal_index'],reverse=True):
    m=literals[e['target']['literal_index']];assert m.group()[1:-1]==e['source'];assert re.search(r'ShowMessage(?:Dismissible)?\(\s*$',original[:m.start()]);assert not any(c in e['translation'].replace('\\n', '') for c in '\"\r\n\\');code=code[:m.start()]+'"'+e['translation']+'"'+code[m.end():]
   assert LITERAL.sub('"STRING"',code)==LITERAL.sub('"STRING"',original);container=container[:hit.start(1)]+base64.b64encode(code.encode('utf-16le')).decode()+container[hit.end(1):]
  replacements[xp]=container
 for xp,value in sorted(replacements.items(),key=lambda x:positions[x[0]][0],reverse=True):
  a,z=positions[xp];text=escape(value)
  if '\r\n' in xml:text=text.replace('\n','\r\n')
  xml=xml[:a]+text+xml[z:]
 after=dict(paths(ET.fromstring(xml)));assert set(before)==set(after)
 for xp,node in before.items():
  n=after[xp];assert (node.tag,node.attrib,node.tail)==(n.tag,n.attrib,n.tail);assert n.text==replacements.get(xp,node.text)
 return xml
