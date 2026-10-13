"""Read original CW3 compressed XML and CRPL literals for display bindings."""
from collections import Counter
import lzma,re
LITERAL=re.compile(r'"(?:\\.|[^"\\])*"')
def paths(node,path=None):
 path=path or '/'+node.tag;yield path,node;counts=Counter()
 for child in node:counts[child.tag]+=1;yield from paths(child,path+'/'+child.tag+f'[{counts[child.tag]}]')
def unpack_script(data):return lzma.decompress(data.encode('utf8','surrogateescape')).decode('utf8')
def scripts(container):return dict(x.split(';',1) for x in container.split(','))
def crpl_literals(code):return list(LITERAL.finditer(code))
