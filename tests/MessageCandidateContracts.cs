using System;using System.IO;using System.Text;using System.Collections;using System.Collections.Generic;using System.Xml;

// Real binding reports -> real bounded collector -> Python CLI export/merge (tools/test.py).
class MessageCandidateContracts {
 static void Need(bool value,string why){if(!value)throw new Exception(why);}
 static object Row=new object();static Hashtable sample;static Dictionary<string,Hashtable> definitions=new Dictionary<string,Hashtable>();
 static Dictionary<string,string> translations=new Dictionary<string,string>();static Candidates collector;
 static MessageBindings Create(bool duplicate=false){var bindings=new MessageBindings();bindings.Add(sample);if(duplicate)bindings.Add(sample);return bindings;}
 static XmlNode Node(MessageBindings bindings,bool registered=true,bool validList=true,int count=1){
  var doc=new XmlDocument();doc.LoadXml(validList?"<System><Messages/></System>":"<System><Other><Messages/></Other></System>");var node=doc.SelectSingleNode("//Messages");
  for(int i=0;i<count;i++)node.AppendChild(doc.CreateElement("Message"));
  if(registered)bindings.Register(doc,bindings.FromResource((string)sample["resource_key"],(string)sample["resource_sha256"]));return node;
 }
 static void Record(MessageBindings bindings,object row,string source,string expected){
  var report=bindings.Report(source,row,definitions,translations);Need((string)report["status"]==expected,"Formal report: "+expected);Need((string)report["display"]==source,"Raw fallback: "+expected);
  collector.Record(0,(string)report["source"],"xml_message","Gal",(string)report["context"],(string)report["status"],(string)report["id"]);
 }
 static void Main(string[] args){
  foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){
   definitions.Add((string)d["id"],d);
   if(d.ContainsKey("resource_key")&&(string)d["message_list"]=="system"&&(int)d["index"]==0&&((string)d["source"]).Contains("\n"))sample=d;
  }
  Need(sample!=null,"Actual multiline XML target");string raw=((string)sample["source"]).Replace("\n","\r\n");collector=new Candidates(true,args[0]);
  var b=Create();b.Bind(new object(),new ArrayList{Row},Node(b,false));Record(b,Row,raw,"unknown_resource");
  b=Create();b.Bind(new object(),new ArrayList{Row},Node(b,true,false));Record(b,Row,raw,"unknown_message_list");
  b=Create();b.Bind(new object(),new ArrayList{Row,new object()},Node(b));Record(b,Row,raw,"message_list_mismatch");
  b=Create();var extra=new object();b.Bind(new object(),new ArrayList{Row,extra},Node(b,true,true,2));Record(b,extra,raw,"unbound_target");
  b=Create(true);b.Bind(new object(),new ArrayList{Row},Node(b));Record(b,Row,raw,"ambiguous_target");
  b=Create();b.Bind(new object(),new ArrayList{Row},Node(b));Record(b,Row,raw,"missing_translation");Record(b,Row,raw+" drift","bound_source_mismatch");
  definitions.Remove((string)sample["id"]);Record(b,Row,raw,"unknown_id");
  Need(collector.Finish(),"Actual snapshot write");Console.WriteLine("PASS eight actual message statuses -> bounded JSON snapshot; original CRLF retained.");
 }
}
