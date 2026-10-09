"""Exact existing CW3 NGUI UIFont/BMFont serialized schema, no DLL execution."""
import struct

def read_uifont(raw):
    p=0;positions={}
    def read(fmt):
        nonlocal p
        size=struct.calcsize('<'+fmt);assert p+size<=len(raw)
        value=struct.unpack_from('<'+fmt,raw,p);p+=size
        return value[0] if len(value)==1 else value
    def pointer():return {'file_id':read('i'),'path_id':read('q')}
    def string():
        nonlocal p
        size=read('i');assert 0<=size<=len(raw)-p
        text=raw[p:p+size].decode('utf8');p+=size;p=(p+3)&~3;return text
    def field(name,reader):
        start=p;value=reader();positions[name]=(start,p);return value
    result={}
    result['m_GameObject']=field('m_GameObject',pointer)
    result['m_Enabled']=read('i');assert result['m_Enabled'] in (0,1)
    result['m_Script']=pointer();result['m_Name']=string()
    result['mMat']=field('mMat',pointer);result['mUVRect']=read('4f')
    bm={name:read('i') for name in ('mSize','mBase','mWidth','mHeight')};bm['mSpriteName']=string()
    count=read('i');assert 0<=count<=10000;glyphs=[]
    for unused in range(count):
        glyph=dict(zip(('index','x','y','width','height','offsetX','offsetY','advance','channel'),read('9i')))
        count_kerning=read('i');assert 0<=count_kerning<=10000
        glyph['kerning']=[read('i') for unused in range(count_kerning)];glyphs.append(glyph)
    bm['mSaved']=glyphs;result['mFont']=bm
    result['mSpacingX']=read('i');result['mSpacingY']=read('i')
    result['mAtlas']=field('mAtlas',pointer);result['mReplacement']=pointer();result['mPixelSize']=read('f')
    result['mSymbols']=read('i');assert result['mSymbols']==0,'Nonempty BMSymbol schema is outside this fix'
    result['mDynamicFont']=field('mDynamicFont',pointer)
    result['mDynamicFontSize']=field('mDynamicFontSize',lambda:read('i'))
    result['mDynamicFontStyle']=read('i');assert result['mDynamicFontStyle'] in (0,1,2,3)
    result['mDynamicFontOffset']=read('f')
    assert p==len(raw),('UIFont trailing/unknown fields',p,len(raw))
    return result,positions

def enable_dynamic_font(raw,file_id,path_id):
    before,positions=read_uifont(raw);assert before['mDynamicFont']=={'file_id':0,'path_id':0}
    assert before['mReplacement']=={'file_id':0,'path_id':0}
    after=bytearray(raw);values={'mMat':struct.pack('<iq',0,0),'mAtlas':struct.pack('<iq',0,0),
                               'mDynamicFont':struct.pack('<iq',file_id,path_id),
                               'mDynamicFontSize':struct.pack('<i',before['mFont']['mSize'])}
    for name,value in values.items():
        start,end=positions[name];assert len(value)==end-start;after[start:end]=value
    checked,new_positions=read_uifont(bytes(after));assert new_positions==positions
    assert {k for k in before if before[k]!=checked[k]}==set(values)
    # Check exact byte boundaries too, independent of parsed field comparisons.
    permitted=set().union(*(set(range(*positions[k])) for k in values))
    assert all(a==b or i in permitted for i,(a,b) in enumerate(zip(raw,after)))
    return bytes(after),{'fields':list(values),'positions':{k:positions[k] for k in values},
                         'before':{k:before[k] for k in values},'after':{k:checked[k] for k in values}}
