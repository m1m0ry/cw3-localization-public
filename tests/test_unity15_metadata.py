"""Guard platform selection and preservation without proprietary game fixtures."""
from pathlib import Path
import struct
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from unity15_metadata import read_unity15_metadata, preserve_script_indices, verify_text_only_changes


def asset(platform, payload=b'SHADER', type_hash=b'T'*16, script_index=-1):
    # One opaque Shader object is sufficient to exercise the real UnityPy v15
    # reader and metadata repair. It must never be rewritten as a font payload.
    meta=bytearray(b'5.2.3f1\0'+struct.pack('<iBi',platform,0,1))
    meta.extend(struct.pack('<i',48)+type_hash+struct.pack('<i',1))
    while (20+len(meta))%4:meta.append(0)
    meta.extend(struct.pack('<qIIiHhB',1,0,len(payload),48,48,script_index,0))
    meta.extend(struct.pack('<ii',0,0)+b'\0')
    # UnityPy's format detection intentionally treats files shorter than 128
    # bytes as opaque data. Real resources exceed this; retain a valid tiny file.
    offset=max(128,(20+len(meta)+15)&~15)
    header=struct.pack('>4I',len(meta),offset+len(payload),15,offset)+b'\0'*4
    return header+meta+b'\0'*(offset-20-len(meta))+payload


class Unity15Metadata(unittest.TestCase):
    def test_explicit_platform_and_windows_default(self):
        self.assertEqual(read_unity15_metadata(asset(5))[0]._m_target_platform,5)
        self.assertEqual(read_unity15_metadata(asset(2),2)[0]._m_target_platform,2)
        for raw,expected in ((asset(2),5),(asset(5),2),(asset(3),2)):
            with self.subTest(expected=expected),self.assertRaisesRegex(ValueError,'platform'):
                read_unity15_metadata(raw,expected)
        for invalid in (0,3,True,'2',None):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,'platform'):
                read_unity15_metadata(asset(2),invalid)

    def test_repair_and_verifier_reject_cross_platform_pairs(self):
        for expected,other in ((2,5),(5,2)):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError,'platform'):
                    preserve_script_indices(asset(expected),asset(other),expected)
                with self.assertRaisesRegex(ValueError,'platform'):
                    verify_text_only_changes(asset(expected),asset(other),{},expected)

    def test_script_index_repair_preserves_payload_and_platform(self):
        for platform in (2,5):
            with self.subTest(platform=platform):
                original=asset(platform)
                repaired,changed=preserve_script_indices(original,asset(platform,script_index=7),platform)
                self.assertEqual(changed,[1])
                self.assertEqual(repaired,original)
                self.assertEqual(verify_text_only_changes(original,repaired,{},platform),{})

    def test_undeclared_shader_and_type_changes_are_rejected(self):
        original=asset(2)
        with self.assertRaisesRegex(AssertionError,'undeclared object'):
            verify_text_only_changes(original,asset(2,payload=b'WINSHADER'),{},2)
        with self.assertRaisesRegex(AssertionError,'type definition'):
            verify_text_only_changes(original,asset(2,type_hash=b'W'*16),{},2)
        with self.assertRaisesRegex(AssertionError,'type definition'):
            preserve_script_indices(original,asset(2,type_hash=b'W'*16),2)

    def test_optimized_python_cannot_disable_resource_guards(self):
        code='import sys;sys.path.insert(0,sys.argv[1]);from unity15_metadata import read_unity15_metadata;read_unity15_metadata(b"",2)'
        result=subprocess.run([sys.executable,'-B','-O','-c',code,str(Path(__file__).resolve().parents[1]/'tools')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('require Python assertions',result.stderr)


if __name__=='__main__':unittest.main()
