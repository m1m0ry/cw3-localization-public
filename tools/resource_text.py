"""Read original CW3 compressed XML and CRPL literals for display bindings."""
from collections import Counter,namedtuple
import lzma,re
LITERAL=re.compile(r'"(?:\\.|[^"\\])*"')
TOKENS=re.compile(LITERAL.pattern+r'|#[^\r\n]*')
DisplayCall=namedtuple('DisplayCall','literal_index family source literal_offset call_offset')
def paths(node,path=None):
 path=path or '/'+node.tag;yield path,node;counts=Counter()
 for child in node:counts[child.tag]+=1;yield from paths(child,path+'/'+child.tag+f'[{counts[child.tag]}]')
def unpack_script(data):return lzma.decompress(data.encode('utf8','surrogateescape')).decode('utf8')
def scripts(container):return dict(x.split(';',1) for x in container.split(','))
def crpl_literals(code):return list(LITERAL.finditer(code))

def _mask(code,strings=False):
 # Quoted # and escaped quotes follow the same rule as crpl_literals. Keep
 # offsets/newlines; raw literal indexes deliberately include quoted comments.
 def replace(hit):
  if hit[0].startswith('#') or strings:return re.sub(r'[^\r\n]',' ',hit[0])
  return hit[0]
 return TOKENS.sub(replace,code)

def show_calls(code):
 return list(re.finditer(r'\bShowMessage(?:Dismissible)?\b',_mask(code,strings=True)))

def display_calls(code):
 """Yield display sites with unchanged raw literal indexes and source offsets."""
 clean=_mask(code)
 for index,hit in enumerate(crpl_literals(code)):
  if clean[hit.start()]!='"':continue
  function=re.search(r'(AddConversationMessage|ShowMessage(?:Dismissible)?)\(\s*[^"()\n]*$',clean[:hit.start()])
  postfix=re.match(r'\s*(?:-?\d+\s+|(?:Screen\w+\s+|\d+\s+sub\s+))*(AddConversationMessage|ShowMessage(?:Dismissible)?)\b',clean[hit.end():])
  if function or postfix:
   call=function.group(1) if function else postfix.group(1)
   offset=function.start() if function else hit.end()+postfix.start(1)
   yield DisplayCall(index,'conversation' if call=='AddConversationMessage' else 'show',hit[0][1:-1],hit.start(),offset)
