"""Build-local memoization preserves bindings, guards and resource isolation."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import base64, copy, hashlib, lzma, struct, sys, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import independent, resource_text

class Asset:
    def __init__(self, data, kind='Fixture', raw=b''):
        self.data=data;self.type=SimpleNamespace(name=kind);self.raw=raw;self.reads=0
    def parse_as_dict(self):self.reads+=1;return self.data
    def get_raw_data(self):return self.raw

def fixture(count=24):
    files={};entries=[]
    for file_number,filename in enumerate(('mainData','level1')):
        code='\n'.join('"%s-%s" %s'%(filename,i,'AddConversationMessage' if i%2 else 'ShowMessage') for i in range(count))
        container='Shared.crpl;'+base64.b64encode(code.encode('utf-16le')).decode()
        xml='<System><Messages>'+''.join('<Message><m>Message %s</m></Message>'%i for i in range(count))+'</Messages><Scripts><scripts>'+container+'</scripts></Scripts></System>'
        packed=lzma.compress(xml.encode()).decode('utf8','surrogateescape')
        objects={
            10:Asset({'m_Name':filename,'m_Component':[(4,{'m_PathID':20})]}),
            20:Asset({'m_Father':{'m_PathID':0},'m_GameObject':{'m_PathID':10}}),
            30:Asset({'m_Name':'Child','m_Component':[(4,{'m_PathID':40})]}),
            40:Asset({'m_Father':{'m_PathID':20},'m_GameObject':{'m_PathID':30}}),
            50:Asset({'m_GameObject':{'m_PathID':30}},raw=b'\0'*4+struct.pack('<q',30)),
            200:Asset({'m_Script':packed})}
        if not file_number:
            objects[1]=Asset({'m_Container':[(name,{'m_FileID':n,'m_PathID':200}) for n,name in enumerate(('main','other'))]},'ResourceManager')
        files[filename]=SimpleNamespace(objects=objects,externals=[SimpleNamespace(path='level1')])
        def add(kind,source,**fields):
            entries.append(dict(id=str(len(entries)),source=source,target=dict(kind=kind,file='CW3_Data/'+filename,**fields)))
        for i in range(count):
            add('label' if i%2 else 'textmesh','Label '+str(i),object_id=50)
            add('xml_text','Message '+str(i),object_id=200,xml_path='/System/Messages[1]/Message[%d]/m[1]'%(i+1))
            add('crpl_conversation' if i%2 else 'crpl',filename+'-'+str(i),object_id=200,xml_path='/System/Scripts[1]/scripts[1]',script='Shared.crpl',literal_index=i)
    return files,entries

def run_fixture(files,entries,platform=5,build=independent.definitions):
    def read(raw,expected):
        assert expected==platform
        return files[raw.decode()],None
    module=SimpleNamespace(read_unity15_metadata=read)
    with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'unity15_metadata':module}):
        root=Path(directory);(root/'CW3_Data').mkdir()
        for name in files:(root/'CW3_Data'/name).write_text(name)
        return build(entries,root,platform)

class DefinitionCacheContracts(unittest.TestCase):
    def test_complete_bindings_both_platforms_and_parse_counts(self):
        for platform in (2,5):
            with self.subTest(platform=platform):
                files,entries=fixture()
                with patch.object(resource_text,'scripts',wraps=resource_text.scripts) as containers,patch.object(resource_text,'display_calls',wraps=resource_text.display_calls) as sites,patch.object(independent,'digest',wraps=independent.digest) as hashes:
                    result=run_fixture(files,entries,platform)
                self.assertEqual((containers.call_count,sites.call_count,hashes.call_count),(2,2,2))
                self.assertEqual(len(result),len(entries))
                for entry,row in zip(entries,result):
                    target=entry['target'];name=Path(target['file']).name
                    self.assertEqual((row['id'],row['source'],row['kind']),(entry['id'],entry['source'],target['kind']))
                    if target['kind'] in ('label','textmesh'):
                        self.assertEqual(row['path'],name+'/Child');self.assertEqual(row['scene'],'Splash' if name=='mainData' else 'MainMenu')
                    elif target['kind']=='xml_text':
                        self.assertEqual(row['index'],int(entry['source'].split()[-1]));self.assertEqual(row['message_list'],'system')
                        self.assertEqual(row['resource_key'],'main' if name=='mainData' else 'other')
                        self.assertEqual(row['resource_sha256'],hashlib.sha256(files[name].objects[200].data['m_Script'].encode('utf8','surrogateescape')).hexdigest())
                    else:
                        self.assertEqual(row['call_line'],target['literal_index']+1);self.assertEqual(row['line'],row['call_line'])
                for file in files.values():
                    self.assertEqual(file.objects[10].reads,1);self.assertEqual(file.objects[30].reads,1)
                script_hashes={row['script_hash'] for row in result if 'script_hash' in row}
                self.assertEqual(len(script_hashes),2,'Same script name in different resources remains isolated')

    def test_no_cache_survives_next_build(self):
        files,entries=fixture();before=run_fixture(files,entries)
        files['mainData'].objects[10].data['m_Name']='Renamed'
        after=run_fixture(files,entries)
        self.assertEqual(before[0]['path'],'mainData/Child');self.assertEqual(after[0]['path'],'Renamed/Child')

    def test_cached_script_still_checks_every_row(self):
        for change in ('source','family','literal'):
            files,entries=fixture()
            row=entries[5] # second script row, after its parse has been cached
            if change=='source':row['source']='Drift'
            elif change=='family':row['target']['kind']='crpl'
            else:row['target']['literal_index']=999
            with self.subTest(change=change),self.assertRaises(AssertionError):run_fixture(files,entries)

    def test_message_structure_and_ambiguity_still_rejected(self):
        files,entries=fixture()
        source=files['mainData'].objects[200].data
        xml=resource_text.unpack_script(source['m_Script']).replace('<m>Message 1</m>','')
        source['m_Script']=lzma.compress(xml.encode()).decode('utf8','surrogateescape')
        with self.assertRaises(AssertionError):run_fixture(files,entries)
        files,entries=fixture();entries.append(copy.deepcopy(entries[1]));entries[-1]['id']='duplicate'
        with self.assertRaises(AssertionError):run_fixture(files,entries)
        files,entries=fixture();files['mainData'].objects[1].data['m_Container'].append(('ambiguous',{'m_FileID':0,'m_PathID':200}))
        with self.assertRaisesRegex(AssertionError,'Ambiguous native resource key'):run_fixture(files,entries)

    def test_shared_node_multiple_scripts_and_output(self):
        files,entries=fixture()
        asset=files['mainData'].objects[200].data
        xml=resource_text.unpack_script(asset['m_Script'])
        from xml.etree import ElementTree as ET
        root=ET.fromstring(xml);node=root.find('Scripts/scripts')
        original=base64.b64decode(resource_text.scripts(node.text)['Shared.crpl']).decode('utf-16le')
        extra='"extra" ShowMessage'
        node.text+=',Other.crpl;'+base64.b64encode(extra.encode('utf-16le')).decode()
        asset['m_Script']=lzma.compress(ET.tostring(root)).decode('utf8','surrogateescape')
        entries.append(dict(id='other',source='extra',target=dict(entries[2]['target'],script='Other.crpl')))
        entries.append(dict(id='output',source='mainData-0',target=dict(entries[2]['target'],kind='crpl_output',script_sha256=hashlib.sha256(original.encode()).hexdigest(),call_index=0,parts=[0])))
        with patch.object(resource_text,'scripts',wraps=resource_text.scripts) as containers:
            result=run_fixture(files,entries)
        self.assertEqual(containers.call_count,2)
        self.assertEqual(result[-2]['script_hash'],hashlib.sha256(extra.encode()).hexdigest())
        self.assertEqual(result[-1]['script_hash'],result[2]['script_hash'])
        self.assertEqual(result[-1]['slots'],[]);self.assertEqual(result[-1]['call_index'],0)

    def test_secondary_message_node_preserves_value_error(self):
        files,entries=fixture()
        asset=files['mainData'].objects[200].data
        xml=resource_text.unpack_script(asset['m_Script']).replace('<m>Message 0</m>','<m>Message 0</m><m>Secondary</m>')
        asset['m_Script']=lzma.compress(xml.encode()).decode('utf8','surrogateescape')
        entries[1]['target']['xml_path']='/System/Messages[1]/Message[1]/m[2]'
        with self.assertRaises(ValueError):run_fixture(files,entries)

    def test_output_hash_guard_is_not_cached_away(self):
        files,entries=fixture()
        target=dict(entries[2]['target'],kind='crpl_output',script_sha256='0'*64,call_index=0,parts=[0])
        entries.insert(3,dict(id='output',source='mainData-0',target=target))
        with self.assertRaisesRegex(AssertionError,'Output script drift'):run_fixture(files,entries)

if __name__=='__main__':unittest.main()
