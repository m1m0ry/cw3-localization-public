"""Independent reader validates C# output, including source bytes and native PPtrs."""
from pathlib import Path
import sys,hashlib
import UnityPy
from fontTools.ttLib import TTFont
bundle,font=map(Path,sys.argv[1:])
def inspect(path,point):
    env=UnityPy.load(path.read_bytes());f=next(v for v in env.file.files.values() if hasattr(v,'objects'))
    assert env.file.signature=='UnityRaw' and env.file.version==3
    assert f.header.version==15 and f.unity_version=='5.2.3f1' and f._m_target_platform==5 and f._enable_type_tree
    fd=f.objects[10].read_typetree();md=f.objects[11].read_typetree();ab=f.objects[1].read_typetree();source=font.read_bytes();sha=hashlib.sha256(source).hexdigest()
    with TTFont(font) as face:family=face['name'].getDebugName(1);em=face['head'].unitsPerEm;metrics=face['hhea']
    assert bytes(fd['m_FontData'])==source and (fd['m_Name'].startswith('CW3Local_Point_') if point else fd['m_Name']=='CW3Local_'+sha[:12]) and fd['m_FontNames']==[family]
    assert fd['m_ConvertCase']==-2 and not fd['m_CharacterRects'] and abs(fd['m_LineSpacing']-(metrics.ascent-metrics.descent+metrics.lineGap)*20/em)<.001
    assert fd['m_DefaultMaterial']==dict(m_FileID=0,m_PathID=11) and fd['m_Texture']==dict(m_FileID=0,m_PathID=12)
    assert md['m_Shader']==dict(m_FileID=1,m_PathID=10101) and f.externals[0].path=='library/unity default resources'
    assert ab['m_PreloadTable'][-1]==md['m_Shader'] and ab['m_Container'][0][0]=='fonts/local'
    for t in f.types:
     assert t.old_type_hash!=bytes(16)
     for node in t.node.traverse():
      if node.m_Type=='Array':assert node.m_TypeFlags==1
    cab=next(name for name in env.file.files if name.startswith('CAB-'))
    assert len(cab)==36 and all(c in '0123456789abcdef' for c in cab[4:])
    return cab,fd['m_Name'],ab['m_AssetBundleName']
smooth=inspect(bundle,False);point=inspect(Path(str(bundle)+'.point'),True)
assert all(a!=b for a,b in zip(smooth,point))
print('PASS independent Unity reader: smooth/point identities differ; both retain exact source, metrics and font/material/texture/shader references')
