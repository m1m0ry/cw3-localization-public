using System;using System.IO;using System.Text;using System.Collections;using System.Collections.Generic;using System.Xml;

// Execute the real binding/guard policy against generated fixed targets; no Unity mocks.
class MessageContracts {
 sealed class Row {internal string Text;}
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static XmlNode List(string kind,out XmlDocument doc){doc=new XmlDocument();if(kind=="system")doc.LoadXml("<System><Messages/></System>");else if(kind=="mission")doc.LoadXml("<Game><Info><Messages/></Info></Game>");else doc.LoadXml("<Game><Units><MessageArtifact><uid>"+kind.Substring(9)+"</uid><Messages/></MessageArtifact></Units></Game>");return doc.SelectSingleNode("//Messages");}
 static void Append(XmlNode list){XmlElement row=list.OwnerDocument.CreateElement("Message");row.AppendChild(list.OwnerDocument.CreateElement("m"));list.AppendChild(row);}
 static void Main(string[] args){
  var definitions=new Dictionary<string,Hashtable>();var translations=new Dictionary<string,string>();var bindings=new MessageBindings();
  var groups=new Dictionary<string,SortedDictionary<int,Hashtable>>();
  foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){
   definitions.Add((string)d["id"],d);bindings.Add(d);if(!d.ContainsKey("resource_key"))continue;
   string key=d["resource"]+"|"+d["message_list"];SortedDictionary<int,Hashtable> group;if(!groups.TryGetValue(key,out group))groups.Add(key,group=new SortedDictionary<int,Hashtable>());group.Add((int)d["index"],d);
  }
  foreach(Hashtable d in (ArrayList)((Hashtable)Json.Read(File.ReadAllText(args[0])))["entries"])translations.Add((string)d["id"],(string)d["translation"]);
  int checkedRows=0;object sampleOwner=null;ArrayList sampleRows=null;XmlNode sampleList=null;Hashtable sampleDefinition=null;
  foreach(var group in groups.Values){
   Hashtable first=null;int size=0;foreach(var pair in group){if(first==null)first=pair.Value;size=Math.Max(size,pair.Key+1);}
   XmlDocument doc;XmlNode list=List((string)first["message_list"],out doc);var rows=new ArrayList();
   for(int i=0;i<size;i++){Hashtable d;rows.Add(new Row{Text=group.TryGetValue(i,out d)?((string)d["source"]).Replace("\n","\r\n"):"UNREVIEWED"});Append(list);}
   var resource=bindings.FromResource((string)first["resource_key"],(string)first["resource_sha256"]);Need(resource!=null,"Known exact resource");Need(bindings.FromResource(resource.Key.ToUpperInvariant(),resource.Hash)==resource,"Native key case handling");Need(bindings.FromResource(resource.Key,"wrong hash")==null,"Altered resource must not acquire identity");
   bindings.Register(doc,resource);object owner=new object();bindings.Bind(owner,rows,list);
   foreach(var pair in group){var row=(Row)rows[pair.Key];string original=row.Text,status;Need(bindings.Get(row).Id==(string)pair.Value["id"],"Existing resource index/ID preserved");Need(bindings.Display(original,row,definitions,translations,out status)==translations[(string)pair.Value["id"]]&&status=="translated","CRLF/LF display equivalence");Need(row.Text==original,"Never change model text");checkedRows++;}
   if((string)first["resource_key"]=="story_0_system"){sampleOwner=owner;sampleRows=rows;sampleList=list;sampleDefinition=first;}
  }
  Need(sampleRows!=null,"Real origin archive fixture");int before=bindings.Count;var changed=(Row)sampleRows[0];string raw=changed.Text;changed.Text+=" ";string reason;
  Need(bindings.Display(changed.Text,changed,definitions,translations,out reason)==changed.Text&&reason=="bound_source_mismatch","Single source drift preserves raw text");
  for(int i=1;i<sampleRows.Count;i++){var row=(Row)sampleRows[i];Need(bindings.Display(row.Text,row,definitions,translations,out reason)!=row.Text&&reason=="translated","Single drift cannot unbind other rows");}
  changed.Text=raw;var extra=new Row{Text="EXTRA"};sampleRows.Add(extra);Append(sampleList);bindings.Bind(sampleOwner,sampleRows,sampleList);
  Need(bindings.Count==before+1,"Append owns one new row");Need(bindings.Display(extra.Text,extra,definitions,translations,out reason)==extra.Text&&reason=="unbound_target","Appended unknown row falls back locally");
  for(int i=0;i<sampleRows.Count-1;i++){var row=(Row)sampleRows[i];Need(bindings.Display(row.Text,row,definitions,translations,out reason)!=row.Text&&reason=="translated","Append cannot invalidate fixed rows");}
  sampleRows.Reverse();Need(bindings.Display(changed.Text,changed,definitions,translations,out reason)!=raw&&reason=="translated","Reordering live list keeps identity on object");
  string id=bindings.Get(changed).Id,value=translations[id];translations.Remove(id);Need(bindings.Display(raw,changed,definitions,translations,out reason)==raw&&reason=="missing_translation","Missing translation preserves original CRLF bytes");translations.Add(id,value);
  bindings.Removed(sampleOwner,extra);Need(bindings.Count==before,"Remove releases only removed object");bindings.Clear(sampleOwner);Need(bindings.Count==before-(sampleRows.Count-1),"Clear releases only this list");bindings.Added(sampleOwner,changed);Need(bindings.Display(raw,changed,definitions,translations,out reason)==raw&&reason=="unknown_resource","Dynamic add cannot guess from familiar text");bindings.Cleanup(owner=>Object.ReferenceEquals(owner,sampleOwner));Need(bindings.Get(changed)==null,"Destroyed owner releases rows");
  var unknown=new MessageBindings();unknown.Add(sampleDefinition);XmlDocument other;XmlNode unknownList=List("system",out other);Append(unknownList);unknown.Bind(new object(),new ArrayList{changed},unknownList);Need(unknown.Display(raw,changed,definitions,translations,out reason)==raw&&reason=="unknown_resource","Unregistered XML cannot acquire identity from text");
  unknown.Register(other,unknown.FromResource((string)sampleDefinition["resource_key"],(string)sampleDefinition["resource_sha256"]));unknown.Add(sampleDefinition);unknown.Bind(new object(),new ArrayList{changed},unknownList);Need(unknown.Display(raw,changed,definitions,translations,out reason)==raw&&reason=="ambiguous_target","Duplicate fixed target is a safe fallback");
  Console.WriteLine("PASS "+groups.Count+" resource message lists / "+checkedRows+" existing targets; isolated drift/append, object identity, raw fallback, lifecycle, unknown/ambiguous source. No game code executed.");
 }
}
