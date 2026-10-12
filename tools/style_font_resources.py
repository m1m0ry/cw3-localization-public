"""Fixed CW3 5.2 native Font assets and namespaced Resources.Load entries.

Preserve existing objects/references and append owned Font/Material/Texture2D objects.
The ResourceManager gains explicit namespaced keys; no OS font registration.
"""
import copy
import hashlib
import struct
from fontTools.ttLib import TTFont
from unity15_metadata import read_unity15_metadata, preserve_script_indices

PREFIX = 'cw3-localization/fonts/'
FAMILIES = ('sans', 'serif')


def asset_name(family, digest):
    return 'CW3Style_' + family + '_' + digest[:12]


def _save_added(original, file, added):
    before, before_meta = read_unity15_metadata(original)
    saved = file.save()
    after, after_meta = read_unity15_metadata(saved)
    assert set(after_meta) == set(before_meta) | set(added)
    assert [t.class_id for t in before.types] == [t.class_id for t in after.types]
    assert str(before.script_types) == str(after.script_types)
    assert str(before.externals) == str(after.externals)
    fields = ('class_id', 'is_stripped_type', 'script_id', 'old_type_hash',
              'node', 'm_ClassName', 'm_NameSpace', 'm_AssemblyName', 'type_dependencies')
    for old_type, new_type in zip(before.types, after.types):
        assert all(getattr(old_type,key) == getattr(new_type,key) for key in fields), 'Type definition changed'
    repaired = bytearray(saved)
    for ident, old in before_meta.items():
        new = after_meta[ident]
        assert (old.type_id, old.class_id, old.stripped) == (new.type_id, new.class_id, new.stripped)
        struct.pack_into(after.header.endian + 'h', repaired, new.script_index_position, old.script_index)
    for ident in added:
        assert after_meta[ident].script_index == -1 and after_meta[ident].stripped == 0
    result = bytes(repaired)
    checked, meta = read_unity15_metadata(result)
    for ident, old in before_meta.items():
        assert checked.objects[ident].get_raw_data() == before.objects[ident].get_raw_data(), ('Original object changed', ident)
        assert meta[ident].script_index == old.script_index
    for ident in added:
        assert checked.objects[ident].get_raw_data() == file.objects[ident].data
    return result


def build(shared_raw, main_raw, fonts, metadata=None):
    """Return exactly two guarded resource payloads for the declared controlled faces."""
    from font_registry import font_id
    assert fonts and set(fonts)<=set(FAMILIES)
    for family in fonts:font_id(family)
    shared, _ = read_unity15_metadata(shared_raw)
    original_ids = set(shared.objects)
    assert max(original_ids)==756
    next_id=10001
    refs = {}
    added = []
    for index, family in enumerate(f for f in FAMILIES if f in fonts):
        path = fonts[family]
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        with TTFont(path) as tt:
            family_name = tt['name'].getDebugName(1)
            em = tt['head'].unitsPerEm
            ascent = tt['hhea'].ascent
            line = ascent - tt['hhea'].descent + tt['hhea'].lineGap
        font_id, material_id, texture_id = next_id + index*3, next_id + index*3+1, next_id + index*3+2
        assert not ({font_id,material_id,texture_id} & original_ids)
        ptr = lambda ident: {'m_FileID': 0, 'm_PathID': ident}
        font = shared.objects[755].parse_as_dict()
        font.update(m_Name=asset_name(family,digest), m_FontNames=[family_name],
                    m_FontData=list(data), m_DefaultMaterial=ptr(material_id), m_Texture=ptr(texture_id),
                    m_CharacterRects=[], m_KerningValues=[], m_FallbackFonts=[], m_FontSize=20,
                    m_Ascent=ascent*20/em, m_LineSpacing=line*20/em, m_FontRenderingMode=0)
        material = shared.objects[4].parse_as_dict()
        material['m_Name'] = 'CW3 ' + family + ' Material'
        material['m_SavedProperties']['m_TexEnvs'][0][1]['m_Texture'] = ptr(texture_id)
        texture = shared.objects[6].parse_as_dict()
        texture['m_Name'] = 'CW3 ' + family + ' Atlas'
        if metadata and metadata[family]['pixel_size']>0:
            texture['m_TextureSettings']['m_FilterMode'] = 0
        for template, ident, value in ((755,font_id,font),(4,material_id,material),(6,texture_id,texture)):
            obj = copy.copy(shared.objects[template])
            obj.path_id = ident
            obj.serialized_type = copy.copy(obj.serialized_type)
            obj.serialized_type.script_type_index = -1
            obj.patch(value)
            shared.objects[ident] = obj
            added.append(ident)
        refs[PREFIX+family] = font_id
    updated_shared = _save_added(shared_raw, shared, added)
    main, _ = read_unity15_metadata(main_raw)
    external = [i+1 for i,x in enumerate(main.externals) if x.path == 'sharedassets0.assets']
    assert len(external) == 1
    manager = main.objects[13]
    assert manager.type.name == 'ResourceManager'
    content = manager.parse_as_dict()
    old_keys = {key for key, ref in content['m_Container']}
    assert not (old_keys & set(refs))
    original_count = len(content['m_Container'])
    assert original_count == 548
    content['m_Container'].extend((key, {'m_FileID':external[0], 'm_PathID':ident}) for key,ident in refs.items())
    manager.patch(content)
    updated_main, _ = preserve_script_indices(main_raw, main.save())
    checked, _ = read_unity15_metadata(updated_main)
    original, _ = read_unity15_metadata(main_raw)
    for ident, obj in checked.objects.items():
        if ident != 13:
            assert obj.get_raw_data() == original.objects[ident].get_raw_data()
    final = checked.objects[13].parse_as_dict()
    assert final['m_Container'][original_count:] == content['m_Container'][original_count:]
    final['m_Container'] = final['m_Container'][:original_count]
    assert final == original.objects[13].parse_as_dict()
    return {'CW3_Data/sharedassets0.assets':updated_shared, 'CW3_Data/mainData':updated_main}
