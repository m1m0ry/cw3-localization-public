"""Platform hash gates and binding selection with synthetic audit inputs."""
from pathlib import Path
import copy
import hashlib
import lzma
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import audit_campaign
import audit_managed_display
import game_target


class AuditTargets(unittest.TestCase):
    def fixture(self,root,platform):
        files={'CW3_Data/Managed/Assembly-CSharp.dll':('assembly-'+str(platform)).encode(),
               'CW3_Data/mainData':('resource-'+str(platform)).encode()}
        for name,data in files.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        return dict(id=game_target.MACOS if platform==2 else game_target.WINDOWS,platform=platform,
                    original_hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()})

    def test_managed_uses_selected_hash_and_explicit_mac_pristine_binding(self):
        for platform in (2,5):
            with self.subTest(platform=platform),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);target=self.fixture(root,platform)
                canonical=dict(entries=[dict(id='fixture',target=dict(kind='managed',method_token=11))])
                resolved=copy.deepcopy(canonical['entries']);resolved[0]['target']['method_token']=22
                with patch('target_bindings.resolve',return_value=resolved) as convert:
                    result=audit_managed_display.audit_dictionary(root,canonical,target)
                self.assertEqual(result['entries'][0]['target']['method_token'],22 if platform==2 else 11)
                self.assertEqual(canonical['entries'][0]['target']['method_token'],11)
                if platform==2:convert.assert_called_once_with(canonical['entries'],root,target)
                else:convert.assert_not_called()
                (root/'CW3_Data/Managed/Assembly-CSharp.dll').write_bytes(b'other platform')
                with patch('target_bindings.resolve') as convert,self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                    audit_managed_display.audit_dictionary(root,canonical,target)
                convert.assert_not_called()

    def test_mac_audit_rejects_resource_and_binding_anchor_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=self.fixture(root,2);doc=dict(entries=[])
            with patch('target_bindings.resolve',side_effect=ValueError('Mac anchor drift')),self.assertRaisesRegex(ValueError,'anchor drift'):
                audit_managed_display.audit_dictionary(root,doc,target)
            (root/'CW3_Data/mainData').write_bytes(b'drift')
            with patch('target_bindings.resolve') as convert,self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                audit_managed_display.audit_dictionary(root,doc,target)
            convert.assert_not_called()

    def test_campaign_passes_selected_platform_and_resolved_coordinates_to_reader(self):
        for platform in (2,5):
            with self.subTest(platform=platform),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);target=self.fixture(root,platform)
                xml='<Root><Message><m>Fixture message</m></Message></Root>'
                compressed=lzma.compress(xml.encode()).decode('utf8','surrogateescape')
                def obj(kind,data):return SimpleNamespace(type=SimpleNamespace(name=kind),parse_as_dict=lambda:data)
                resource=SimpleNamespace(externals=[],objects={1:obj('ResourceManager',{'m_Container':[
                    ('fixture',{'m_FileID':0,'m_PathID':10})]}),10:obj('TextAsset',{'m_Script':compressed})})
                entry=dict(id='fixture',source='Fixture message',target=dict(kind='xml_text',
                    file='CW3_Data/mainData',object_id=10,xml_path='/Root/Message[1]/m[1]'))
                with patch('unity15_metadata.read_unity15_metadata',return_value=(resource,None)) as reader,patch('target_bindings.resolve',return_value=[entry]) as convert:
                    result=audit_campaign.audit(root,[entry],target)
                self.assertEqual(result['missing'],[])
                self.assertEqual(result['counts']['xml_message'],1)
                reader.assert_called_once_with(('resource-'+str(platform)).encode(),platform)
                if platform==2:convert.assert_called_once_with([entry],root,target)
                else:convert.assert_not_called()
                (root/'CW3_Data/mainData').write_bytes(b'other platform')
                with patch('unity15_metadata.read_unity15_metadata') as reader,self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                    audit_campaign.audit(root,[entry],target)
                reader.assert_not_called()


if __name__=='__main__':unittest.main()
