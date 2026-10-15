"""Generate the selected Unity 5.2.3 native-font envelope, never user font data.

Runtime C# fills only the Font names/data/metrics and object lengths/offsets. The
Raw-v3 wrapper, Shader PPtr and class-142 identity match the selected player.
Mac templates retain platform 2 and its built-in Shader dependency. Independent
parsing checks the envelope; actual Mac font loading still needs live acceptance.
"""
import base64,copy,hashlib,struct
from pathlib import Path
import UnityPy
from UnityPy.enums import ClassIDType
from UnityPy.files.ObjectReader import ObjectReader
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers.Tpk import get_typetree_node
from UnityPy.helpers.UnityVersion import UnityVersion
from unity15_metadata import read_unity15_metadata

def build(original, expected_platform=5):
    source,_=read_unity15_metadata((Path(original)/'CW3_Data/sharedassets0.assets').read_bytes(),expected_platform)
    f=copy.copy(source);f.objects={};f.script_types=[];f.userInformation='';f._enable_type_tree=True;f.externals=[copy.copy(source.externals[1])]
    font=source.objects[756];fd=font.read_typetree();mat=source.objects[fd['m_DefaultMaterial']['m_PathID']];md=mat.read_typetree();tex=source.objects[fd['m_Texture']['m_PathID']];td=tex.read_typetree()
    assert fd['m_DefaultMaterial']['m_FileID']==fd['m_Texture']['m_FileID']==0
    assert [obj.type.name for obj in (font,mat,tex)]==['Font','Material','Texture2D']
    assert md['m_Shader']==dict(m_FileID=2,m_PathID=10101) and f.externals[0].path=='library/unity default resources'
    types={name:copy.copy(obj.serialized_type) for name,obj in [('Font',font),('Material',mat),('Texture2D',tex)]}
    types['AssetBundle']=copy.copy(types['Font']);types['AssetBundle'].class_id=142;types['AssetBundle'].old_type_hash=bytes.fromhex('f284abb6f2df17ebedae2b6b50436810')
    for t in types.values():
        t.script_type_index=-1;node=get_typetree_node(t.class_id,UnityVersion.from_str('5.2.3f1'));t.node=TypeTreeNode.from_list([{key:getattr(n,key) for key in ('m_Level','m_Type','m_Name','m_ByteSize','m_Version','m_TypeFlags','m_Index','m_MetaFlag')} for n in node.traverse()])
        for n in t.node.traverse():n.m_TypeFlags=1 if n.m_Type=='Array' else 0
    f.types=list(types.values());ptr=lambda ident:dict(m_FileID=0,m_PathID=ident)
    def obj(name,ident,data,template):
        o=copy.copy(template);o.assets_file=f;o.path_id=ident;o.type_id=o.class_id=types[name].class_id;o.type=ClassIDType(o.class_id);o.serialized_type=types[name];o.patch(data);f.objects[ident]=o
    name='CW3_LOCAL_FACE';family='CW3_LOCAL_FAMILY';payload=b'CW3_FONT_PAYLOAD';bundle_name='cw3-native-font-template'
    fd.update(m_Name=name,m_FontNames=[family],m_FontData=payload,m_DefaultMaterial=ptr(11),m_Texture=ptr(12),m_CharacterRects=[],m_KerningValues=[],m_FallbackFonts=[],m_FontSize=20.,m_Ascent=17.625,m_LineSpacing=23.125,m_FontRenderingMode=0,m_PixelScale=.1)
    md['m_Name']='CW3 Local Font Material';md['m_Shader']=dict(m_FileID=1,m_PathID=10101)
    for k,v in md['m_SavedProperties']['m_TexEnvs']:v['m_Texture']=ptr(12)
    td['m_Name']='CW3 Local Font Atlas';assert td['image data']==b''
    ab=dict(m_Name='',m_PreloadTable=[ptr(10),ptr(11),ptr(12),md['m_Shader']],m_Container=[('fonts/local',dict(preloadIndex=0,preloadSize=4,asset=ptr(10)))],m_MainAsset=dict(preloadIndex=0,preloadSize=0,asset=ptr(0)),m_RuntimeCompatibility=1,m_AssetBundleName=bundle_name,m_Dependencies=[],m_IsStreamedSceneAssetBundle=False)
    for args in [('Font',10,fd,font),('Material',11,md,mat),('Texture2D',12,td,tex),('AssetBundle',1,ab,font)]:obj(*args)
    raw=f.save();positions={};orig=ObjectReader.from_reader.__func__
    def capture(cls,assets,reader):
        reader.align_stream();start=reader.Position;o=orig(cls,assets,reader);positions[o.path_id]=(start+8,start+12);return o
    ObjectReader.from_reader=classmethod(capture)
    try:sf=UnityPy.load(raw).file
    finally:ObjectReader.from_reader=classmethod(orig)
    checked,_=read_unity15_metadata(raw,expected_platform)
    assert set(checked.objects)=={1,10,11,12} and str(checked.externals)==str(f.externals)
    assert [t.old_type_hash for t in checked.types]==[t.old_type_hash for t in f.types]
    assert checked.objects[11].read_typetree()['m_Shader']==dict(m_FileID=1,m_PathID=10101)
    def field(data,value):
        value=value.encode() if isinstance(value,str) else value;pattern=struct.pack('<I',len(value))+value;assert data.count(pattern)==1;start=data.index(pattern);return start,(start+4+len(value)+3)&~3
    font_raw=sf.objects[10].get_raw_data();na,nb=field(font_raw,name);fa,fb=field(font_raw,family);pa,pb=field(font_raw,payload);assert na==0 and nb<pa<pb<=fa
    prefix=font_raw[nb:pa];middle=font_raw[pb:fa];line=prefix.index(struct.pack('<f',23.125));ascent=middle.index(struct.pack('<f',17.625));asset=sf.objects[1].get_raw_data();aa,az=field(asset,bundle_name)
    chunks=dict(Metadata=raw[:sf.header.data_offset],FontPrefix=prefix,FontMiddle=middle,FontSuffix=font_raw[fb:],BundlePrefix=asset[:aa],BundleSuffix=asset[az:],Material=sf.objects[11].get_raw_data(),Texture=sf.objects[12].get_raw_data())
    key=hashlib.sha256(b''.join(chunks.values())).hexdigest()
    code='internal static class NativeFontTemplate {\n'
    code+=' internal const string Key="'+key+'";\n'
    for k,v in chunks.items():code+=' internal const string '+k+'="'+base64.b64encode(v).decode()+'";\n'
    code+=' internal const int LineSpacing='+str(line)+',Ascent='+str(ascent)+';\n'
    code+=' internal static readonly int[] OffsetFields={'+','.join(str(positions[i][0]) for i in (1,10,11,12))+'};\n'
    code+=' internal static readonly int[] SizeFields={'+','.join(str(positions[i][1]) for i in (1,10,11,12))+'};\n}\n'
    return code
