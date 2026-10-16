"""The two shipped font faces: source cmap, identity and native glyph probes."""
from pathlib import Path
import base64
import hashlib
import json
import re

ID = re.compile(r'[a-z][a-z0-9_-]{0,31}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
RESOURCES = ('CW3_Data/sharedassets0.assets', 'CW3_Data/mainData')
REGISTRY = 'CW3Localization/fonts.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def font_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Font ID must be 1–32 lowercase letters, digits, hyphens or underscores, beginning with a letter')
    return value

def font_path(value):
    if value in ('font.ttf', 'serif.ttf'):
        return value
    raise ValueError('Invalid shipped font path')

def inspect_font(path, pixel_size=0):
    from fontTools.ttLib import TTLibError
    try:
        return _inspect_font(path, pixel_size)
    except (TTLibError, KeyError) as e:
        raise ValueError('Font is damaged or lacks required outline/name/metrics tables') from e

def _inspect_font(path, pixel_size=0):
    from fontTools.ttLib import TTFont
    path = Path(path)
    if path.suffix.lower() not in ('.ttf', '.otf') or not 0 < path.stat().st_size <= 50_000_000:
        raise ValueError('Use a static TTF or OTF of at most 50 MB')
    if type(pixel_size) is not int or not 0 <= pixel_size <= 64:
        raise ValueError('Pixel size must be 0 (smooth) or 1–64')
    with TTFont(path) as f:
        if f.flavor or 'fvar' in f or 'CFF2' in f or not ('glyf' in f or 'CFF ' in f):
            raise ValueError('This Unity 5.2 import supports static outline TTF/OTF; variable, collection, web and bitmap-only fonts must be exported to a static outline face first')
        # Match the runtime Unicode name reader. Keep the user font bytes and names intact.
        names=[]
        for n in f['name'].names:
            if n.nameID in (1,16) and (n.platformID==0 or n.platformID==3 and n.platEncID in (1,10)):
                names.append(((4 if n.nameID==16 else 0)+(2 if n.platformID==3 else 0)+(1 if n.langID==0x409 else 0),n.toUnicode()))
        if not names:
            raise ValueError('Font has no supported Unicode family name')
        family=max(names,key=lambda n:n[0])[1]
        cmap={cp:g for cp,g in f.getBestCmap().items() if cp<65536 and f.getGlyphID(g)!=0}
        usable=[cp for cp in cmap if cp>=33 and not chr(cp).isspace() and cp not in range(0xD800,0xE000)]
        if not usable:raise ValueError('No supported BMP glyphs')
        char=next((cp for cp in (ord('W'),ord('中'),ord('A')) if cp in cmap),min(usable))
        advance=f['hmtx'][cmap[char]][0]*20/f['head'].unitsPerEm
        bits=bytearray(8192)
        for cp in cmap:bits[cp//8]|=1<<(cp%8)
        return dict(sha256=sha(path.read_bytes()),family=family,coverage=base64.b64encode(bits).decode(),pixel_size=pixel_size,probe_char=char,probe_advance=int(round(advance)))

def validate(d):
    if not isinstance(d,dict) or set(d)!= {'format','resources','fonts','runtime_sha256'} or type(d['format']) is not int or d['format']!=1:
        raise ValueError('Font registry format')
    if not isinstance(d['runtime_sha256'],str) or not HASH.fullmatch(d['runtime_sha256']):raise ValueError('Font runtime hash')
    if set(d['resources'])!=set(RESOURCES) or not all(isinstance(v,str) and HASH.fullmatch(v) for v in d['resources'].values()):raise ValueError('Font resource hashes')
    if not isinstance(d['fonts'],dict) or set(d['fonts'])!={'sans','serif'}:raise ValueError('Font registry requires only shipped sans/serif faces')
    for ident,spec in d['fonts'].items():
        font_id(ident)
        if not isinstance(spec,dict) or set(spec)!= {'file','sha256','family','coverage','pixel_size','probe_char','probe_advance'}:raise ValueError('Font registry entry')
        if font_path(spec['file']) != {'sans':'font.ttf','serif':'serif.ttf'}[ident]:raise ValueError('Font face/path mismatch')
        if not isinstance(spec['sha256'],str) or not HASH.fullmatch(spec['sha256']) or not isinstance(spec['family'],str) or not 0<len(spec['family'])<=256:raise ValueError('Font identity')
        if len(base64.b64decode(spec['coverage'],validate=True))!=8192:raise ValueError('Font coverage')
        if any(type(spec[k]) is not int for k in ('pixel_size','probe_char','probe_advance')) or not 0<=spec['pixel_size']<=64 or not 33<=spec['probe_char']<65536 or not 0<=spec['probe_advance']<=4096:raise ValueError('Font metadata')
    return d

def load(path):
    path=Path(path)
    if path.stat().st_size>256000:raise ValueError('Font registry too large')
    import translation_contract
    return validate(translation_contract.loads(path.read_text(encoding='utf8')))
