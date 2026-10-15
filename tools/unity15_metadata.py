"""Preserve per-object script indices when saving these Unity 5.2 v15 assets.

UnityPy 1.25.2 stores this old format's per-object index on a shared type, so its
writer can use the last-read object's index for unrelated objects of that type.
Inspect the original table and repair only those two-byte fields after saving.
"""
from dataclasses import dataclass
import struct

import UnityPy
from UnityPy.files.ObjectReader import ObjectReader


@dataclass(frozen=True)
class ObjectMetadata:
    type_id: int
    class_id: int
    stripped: int
    script_index: int
    script_index_position: int


def read_unity15_metadata(raw, expected_platform=5):
    """Read one explicitly selected CW3 platform, never infer a write target."""
    if type(expected_platform) is not int or expected_platform not in (2, 5):
        raise ValueError('Supported CW3 asset platforms are 2 (Mac) and 5 (Windows)')
    # The preservation checks below deliberately use assertions. Do not allow an
    # optimized interpreter to turn a guarded resource writer into an unchecked one.
    if not __debug__:
        raise RuntimeError('CW3 resource checks require Python assertions (no -O)')
    entries = {}
    original_reader = ObjectReader.from_reader.__func__

    def capture(cls, assets_file, reader):
        assert assets_file.header.version == 15, 'This helper supports only verified v15 assets.'
        obj = original_reader(cls, assets_file, reader)
        end = reader.Position
        # v15 ends each object entry with an int16 script index and uint8 flag.
        position = end - 3
        reader.Position = position
        index = reader.read_short()
        reader.Position = end
        entries[obj.path_id] = ObjectMetadata(obj.type_id, obj.class_id, obj.is_stripped, index, position)
        return obj

    # This is local to the short-lived, single-threaded preparation process;
    # restore the parser immediately, including on a parsing error.
    ObjectReader.from_reader = classmethod(capture)
    try:
        file = UnityPy.load(raw).file
    finally:
        ObjectReader.from_reader = classmethod(original_reader)
    if file.header.version != 15 or file.unity_version != '5.2.3f1' or file.header.endian != '<':
        raise ValueError('Expected little-endian Unity 5.2.3f1 serialized v15 assets')
    if file._m_target_platform != expected_platform:
        raise ValueError('Unity asset platform %s does not match expected platform %s' %
                         (file._m_target_platform, expected_platform))
    return file, entries


def _verify_definitions(source, target):
    assert [t.class_id for t in source.types] == [t.class_id for t in target.types]
    assert str(source.script_types) == str(target.script_types)
    assert str(source.externals) == str(target.externals)
    fields = ('class_id', 'is_stripped_type', 'script_id', 'old_type_hash',
              'node', 'm_ClassName', 'm_NameSpace', 'm_AssemblyName', 'type_dependencies')
    for old_type, new_type in zip(source.types, target.types):
        assert all(getattr(old_type, name) == getattr(new_type, name) for name in fields), 'type definition changed'


def preserve_script_indices(original, saved, expected_platform=5):
    source, source_entries = read_unity15_metadata(original, expected_platform)
    target, target_entries = read_unity15_metadata(saved, expected_platform)
    assert set(source_entries) == set(target_entries)
    _verify_definitions(source, target)
    repaired = bytearray(saved)
    corrected = []
    for path_id, before in source_entries.items():
        after = target_entries[path_id]
        assert (before.type_id, before.class_id, before.stripped) == (after.type_id, after.class_id, after.stripped)
        if before.script_index != after.script_index:
            start = after.script_index_position
            assert struct.unpack(target.header.endian + 'h', repaired[start:start + 2])[0] == after.script_index
            repaired[start:start + 2] = struct.pack(target.header.endian + 'h', before.script_index)
            corrected.append(path_id)
    result = bytes(repaired)
    checked, checked_entries = read_unity15_metadata(result, expected_platform)
    for path_id, before in source_entries.items():
        after = checked_entries[path_id]
        assert (before.type_id, before.class_id, before.stripped, before.script_index) == (
            after.type_id, after.class_id, after.stripped, after.script_index)
        # The repair may change metadata only, never a translated object payload.
        assert checked.objects[path_id].get_raw_data() == target.objects[path_id].get_raw_data()
    return result, corrected


def verify_text_only_changes(original, patched, allowed_fields, expected_platform=5):
    """Reject altered script links and every undeclared serialized object field."""
    source, before = read_unity15_metadata(original, expected_platform)
    target, after = read_unity15_metadata(patched, expected_platform)
    assert set(before) == set(after)
    _verify_definitions(source, target)
    changed = {}
    for path_id, meta in before.items():
        other = after[path_id]
        assert (meta.type_id, meta.class_id, meta.stripped, meta.script_index) == (
            other.type_id, other.class_id, other.stripped, other.script_index), ('script/object metadata changed', path_id)
        if source.objects[path_id].get_raw_data() == target.objects[path_id].get_raw_data():
            continue
        assert path_id in allowed_fields, ('undeclared object changed', path_id)
        old = source.objects[path_id].parse_as_dict()
        new = target.objects[path_id].parse_as_dict()
        assert set(old) == set(new), ('serialized field set changed', path_id)
        fields = {key for key in old if old[key] != new[key]}
        assert fields == set(allowed_fields[path_id]), ('non-text field changed', path_id, fields)
        changed[path_id] = sorted(fields)
    assert set(changed) == set(allowed_fields)
    return changed
