from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from resource_text import display_calls,show_calls
from script_outputs import output_definition
import hashlib
class CampaignAudit(unittest.TestCase):
    def test_function_postfix_multiline_and_commented_calls(self):
        code='# ShowMessage("Do not adopt")\nAddConversationMessage(1 "Short!")\n"First line\n\tSecond line" -1 16 ShowMessage\nShowMessageDismissible("Hint")'
        self.assertEqual([(s.literal_index,s.family,s.source) for s in display_calls(code)],[(1,'conversation','Short!'),(2,'show','First line\n\tSecond line'),(3,'show','Hint')])
    def test_closed_call_does_not_capture_later_internal_identifiers(self):
        self.assertEqual([s.source for s in display_calls('ShowMessage("Hint") GetUnit("CRPLCORE")')],['Hint'])
    def test_comment_marker_inside_display_text_is_preserved(self):
        self.assertEqual([s.source for s in display_calls('ShowMessage("Map #1") # ShowMessage("ignored")')],['Map #1'])
    def test_comments_between_literal_and_call_keep_raw_index_and_offsets(self):
        code='# "ignored"\r\n"Hint" # "also ignored"\r\n0 0 ShowMessage'
        site,=display_calls(code)
        self.assertEqual((site.literal_index,site.family,site.source),(1,'show','Hint'))
        self.assertEqual(site.literal_offset,code.index('"Hint"'))
        self.assertEqual(site.call_offset,code.index('ShowMessage'))
        self.assertEqual(code[:site.call_offset].count('\n')+1,3)
        self.assertEqual([m.start() for m in show_calls(code)],[site.call_offset])
    def test_escaped_quotes_do_not_turn_quoted_hash_into_comment(self):
        code='ShowMessage("Map \\"#1\\"") # ShowMessage("ignored")'
        site,=display_calls(code)
        self.assertEqual(site.source,'Map \\"#1\\"')
        self.assertEqual(site.call_offset,0)
        self.assertEqual([m.start() for m in show_calls(code)],[0])
    def test_declared_commented_target_does_not_become_an_active_call(self):
        code='# ShowMessage("Inactive")\nShowMessage("Active")'
        active,=display_calls(code)
        self.assertEqual((active.literal_index,active.source),(1,'Active'))
        declared=list(display_calls(code,include_comments=True))
        self.assertEqual([(s.literal_index,s.source) for s in declared],[(0,'Inactive'),(1,'Active')])
        self.assertEqual(declared[0].call_offset,2)
        self.assertEqual([m.start() for m in show_calls(code)],[active.call_offset])
    def test_variable_calls_on_same_line_are_not_hidden_by_literals(self):
        code='"ShowMessage fake # marker" ->Msg ShowMessage(<-Msg 0 0) <-Msg 0 0 ShowMessage # ShowMessage ignored'
        self.assertEqual([m[0] for m in show_calls(code)],['ShowMessage','ShowMessage'])
        self.assertEqual(len(set(m.start() for m in show_calls(code))),2)
    def test_output_fragments_and_fingerprint_are_checked(self):
        code='"Score: " ->Msg <-Msg 0 0 ShowMessage'
        target=dict(script='Scores.crpl',script_sha256=hashlib.sha256(code.encode()).hexdigest(),call_index=0,parts=[0,dict(slot=0,type='number')])
        self.assertEqual(output_definition(code,target,'Score: {0}')['call_index'],0)
        with self.assertRaises(AssertionError):output_definition(code+' ',target,'Score: {0}')
        with self.assertRaises(AssertionError):output_definition(code,target,'InternalID {0}')
        with self.assertRaises(AssertionError):output_definition(code,dict(target,call_index=1),'Score: {0}')
        with self.assertRaises(AssertionError):output_definition(code,dict(target,parts=[0,dict(slot=0,type='arbitrary_text')]),'Score: {0}')
if __name__=='__main__':unittest.main()
