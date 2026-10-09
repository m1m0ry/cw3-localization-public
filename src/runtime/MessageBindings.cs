using System;using System.Collections;using System.Collections.Generic;using System.Xml;

// Only CW3's compiled resource targets. No scene/text heuristics or saved-model writes.
internal sealed class MessageBindings {
 internal sealed class Resource {internal string Key,Identity,Hash;}
 internal sealed class Binding {internal string Id,Context,Reason;internal object Owner;}
 sealed class Document {internal WeakReference Xml;internal Resource Source;}
 readonly Dictionary<string,Resource> resources=new Dictionary<string,Resource>(StringComparer.OrdinalIgnoreCase);
 readonly Dictionary<string,string> targets=new Dictionary<string,string>();
 readonly HashSet<string> ambiguous=new HashSet<string>();
 readonly List<Document> documents=new List<Document>();
 readonly Dictionary<object,Binding> rows=new Dictionary<object,Binding>();
 readonly Dictionary<object,HashSet<object>> owners=new Dictionary<object,HashSet<object>>();
 internal int Count {get{return rows.Count;}}
 internal int BoundCount {get{int count=0;foreach(var binding in rows.Values)if(binding.Id!=null)count++;return count;}}
 static string Key(Resource resource,string list,int index){return resource.Identity+"|"+list+"|"+index;}
 internal void Add(Hashtable d){
  string key=d["resource_key"] as string;if(key==null)return;
  Resource resource;if(!resources.TryGetValue(key,out resource))resources.Add(key,resource=new Resource{Key=key,Identity=(string)d["resource"],Hash=(string)d["resource_sha256"]});
  if(resource.Identity!=(string)d["resource"]||resource.Hash!=(string)d["resource_sha256"])throw new FormatException("Ambiguous resource key");
  string target=Key(resource,(string)d["message_list"],(int)d["index"]);
  if(targets.ContainsKey(target))ambiguous.Add(target);else targets.Add(target,(string)d["id"]);
 }
 internal Resource FromResource(string key,string hash){Resource r;return key!=null&&resources.TryGetValue(key,out r)&&r.Hash==hash?r:null;}
 internal void Register(XmlDocument doc,Resource resource){
  if(doc==null)return;for(int i=documents.Count-1;i>=0;i--)if(!documents[i].Xml.IsAlive||Object.ReferenceEquals(doc,documents[i].Xml.Target))documents.RemoveAt(i);
  if(resource!=null)documents.Add(new Document{Xml=new WeakReference(doc),Source=resource});
 }
 Resource Source(XmlNode node){if(node==null)return null;foreach(var d in documents)if(Object.ReferenceEquals(node.OwnerDocument,d.Xml.Target))return d.Source;return null;}
 static string ListKey(XmlNode node){
  if(node==null||node.Name!="Messages"||node.OwnerDocument==null)return null;
  XmlNode root=node.OwnerDocument.DocumentElement,parent=node.ParentNode;
  if(parent==root&&root.Name=="System")return "system";
  if(parent!=null&&parent.Name=="Info"&&parent.ParentNode==root&&root.Name=="Game")return "mission";
  if(parent!=null&&parent.Name=="MessageArtifact"&&parent.ParentNode!=null&&parent.ParentNode.Name=="Units"&&parent.ParentNode.ParentNode==root&&root.Name=="Game"){
   XmlNode uid=parent.SelectSingleNode("uid");int value;if(uid!=null&&Int32.TryParse(uid.InnerText,out value)&&value>=0)return "artifact:"+value;
  }
  return null;
 }
 internal void Added(object owner,object row){
  if(owner==null||row==null)return;Binding current;if(rows.TryGetValue(row,out current)&&Object.ReferenceEquals(current.Owner,owner))return;
  if(current!=null)Removed(current.Owner,row);
  HashSet<object> members;if(!owners.TryGetValue(owner,out members))owners.Add(owner,members=new HashSet<object>());members.Add(row);
  rows[row]=new Binding{Owner=owner,Context="unknown resource",Reason="unknown_resource"};
 }
 internal void Bind(object owner,IList messages,XmlNode node){
  Clear(owner);if(messages==null)return;Resource resource=Source(node);string list=ListKey(node);
  int count=0;if(node!=null)foreach(XmlNode child in node.ChildNodes)if(child.Name=="Message")count++;
  bool ordered=count==messages.Count;
  for(int i=0;i<messages.Count;i++){
   object row=messages[i];Added(owner,row);Binding binding=rows[row];
   if(resource==null)continue;
   binding.Context=resource.Key+"/"+(list??"unknown list")+"/Message["+(i+1)+"]";
   binding.Reason=list==null?"unknown_message_list":!ordered?"message_list_mismatch":"unbound_target";
   if(list==null||!ordered)continue;
   string target=Key(resource,list,i),id;
   if(ambiguous.Contains(target)){binding.Reason="ambiguous_target";continue;}
   if(targets.TryGetValue(target,out id)){binding.Id=id;binding.Reason=null;}
  }
 }
 internal void BindScript(object owner,object row,string id,string context){
  Added(owner,row);Binding binding=Get(row);if(binding==null)return;binding.Id=id;binding.Context=context;binding.Reason=id==null?"unbound_script_literal":null;
 }
 internal Binding Get(object row){Binding b;return row!=null&&rows.TryGetValue(row,out b)?b:null;}
 internal string Display(string original,object row,Dictionary<string,Hashtable> definitions,Dictionary<string,string> translations,out string status){
  Binding binding=Get(row);if(binding==null||binding.Id==null){status=binding==null?"unknown_resource":binding.Reason;return original;}
  string value=FixedText.Resolve(definitions,translations,binding.Id,FixedText.NormalizeXml(original),out status);return status=="translated"?value:original;
 }
 internal Hashtable Report(string original,object row,Dictionary<string,Hashtable> definitions,Dictionary<string,string> translations){
  string status;var binding=Get(row);var display=Display(original,row,definitions,translations,out status);
  return new Hashtable{{"status",status},{"source",original},{"display",display},{"id",binding==null?null:binding.Id},{"context",binding==null?"unknown resource":binding.Context}};
 }
 internal void Removed(object owner,object row){Binding b;if(row==null||!rows.TryGetValue(row,out b)||!Object.ReferenceEquals(b.Owner,owner))return;rows.Remove(row);HashSet<object> members;if(owners.TryGetValue(owner,out members)){members.Remove(row);if(members.Count==0)owners.Remove(owner);}}
 internal void Clear(object owner){if(owner==null)return;HashSet<object> members;if(!owners.TryGetValue(owner,out members))return;foreach(object row in members)rows.Remove(row);owners.Remove(owner);}
 internal void Cleanup(Predicate<object> dead){var gone=new List<object>();foreach(object owner in owners.Keys)if(dead(owner))gone.Add(owner);foreach(object owner in gone)Clear(owner);for(int i=documents.Count-1;i>=0;i--)if(!documents[i].Xml.IsAlive)documents.RemoveAt(i);}
}

// One source guard and status vocabulary for managed text, components and XML displays.
internal static class FixedText {
 internal static string NormalizeXml(string text){return text==null?null:text.Replace("\r\n","\n");}
 internal static string Resolve(Dictionary<string,Hashtable> definitions,Dictionary<string,string> translations,string id,string original,out string status){
  Hashtable definition;string value;
  if(id==null||!definitions.TryGetValue(id,out definition)){status="unknown_id";return original;}
  if((string)definition["source"]!=original){status="bound_source_mismatch";return original;}
  if(!translations.TryGetValue(id,out value)){status="missing_translation";return original;}
  status="translated";return value;
 }
}
