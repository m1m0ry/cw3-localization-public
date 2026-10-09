using System;using System.Collections;using System.Collections.Generic;using System.Text;using System.Text.RegularExpressions;

// Fingerprinted script plus native output ordinal/line and guarded source. Models stay English.
internal sealed class ScriptBindings {
 readonly Dictionary<string,string> targets=new Dictionary<string,string>();
 readonly HashSet<string> ambiguous=new HashSet<string>();
 readonly Dictionary<string,List<Output>> outputs=new Dictionary<string,List<Output>>();
 readonly HashSet<string> outputScripts=new HashSet<string>();
 sealed class Output {internal string Id;internal Regex Pattern;}
 const string Number=@"[-+]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)(?:[Ee][-+]?[0-9]+)?";
 static string Origin(string name,string hash){return name+"|"+hash;}
 static string Key(string kind,string name,string hash,int line,string source){return kind+"|"+Origin(name,hash)+"|"+line+"|"+source;}
 internal static string DisplaySource(Hashtable d){string s=(string)d["source"];return (string)d["kind"]=="crpl_conversation"?FixedText.NormalizeXml(s):Decode(s);}
 internal static string Decode(string s){return s==null?null:s.Replace("\\n","\n").Replace("\\t","\t");}
 internal void Add(Hashtable d){
  string kind=d["kind"] as string;
  if(kind=="crpl_output"){
   string origin=Origin((string)d["script"],(string)d["script_hash"]);outputScripts.Add(origin);
   string key=origin+"|"+d["call_line"]+"|"+d["call_index"];List<Output> list;if(!outputs.TryGetValue(key,out list))outputs.Add(key,list=new List<Output>());
   string source=(string)d["source"];var slots=(ArrayList)d["slots"];var pattern=new StringBuilder(@"\A");int at=0;
   for(int i=0;i<slots.Count;i++){
    string token="{"+i+"}";int next=source.IndexOf(token,at,StringComparison.Ordinal);if(next<at)throw new FormatException("Output slot order");pattern.Append(Regex.Escape(source.Substring(at,next-at)));
    string type=(string)slots[i],p=Number;
    if(type=="fraction_or_blank")p="(?:"+Number+"/"+Number+"| )";
    else if(type=="number_or_blank")p="(?:"+Number+"| )";
    else if(type!="number")throw new FormatException("Unknown output slot");
    pattern.Append("(").Append(p).Append(")");at=next+token.Length;
   }
   pattern.Append(Regex.Escape(source.Substring(at))).Append(@"\z");list.Add(new Output{Id=(string)d["id"],Pattern=new Regex(pattern.ToString(),RegexOptions.CultureInvariant)});return;
  }
  if(kind!="crpl"&&kind!="crpl_display"&&kind!="crpl_conversation")return;
  string exact=Key(kind=="crpl_conversation"?"conversation":"show",(string)d["script"],(string)d["script_hash"],(int)d["call_line"],DisplaySource(d));
  if(targets.ContainsKey(exact))ambiguous.Add(exact);else targets.Add(exact,(string)d["id"]);
 }
 internal bool HasOutputs(string name,string hash){return outputScripts.Contains(Origin(name,hash));}
 internal string FindOutput(string name,string hash,int line,int ordinal,string original,out string[] arguments){
  arguments=null;List<Output> list;if(original==null||original.Length>4096||!outputs.TryGetValue(Origin(name,hash)+"|"+line+"|"+ordinal,out list))return null;
  string id=null;foreach(var output in list){var match=output.Pattern.Match(FixedText.NormalizeXml(original));if(!match.Success)continue;if(id!=null){arguments=null;return null;}id=output.Id;arguments=new string[match.Groups.Count-1];for(int i=0;i<arguments.Length;i++)arguments[i]=match.Groups[i+1].Value;}return id;
 }
 internal static string Format(string template,string[] arguments){if(arguments==null)return null;for(int i=0;i<arguments.Length;i++)template=template.Replace("{"+i+"}",arguments[i]);return template;}
 internal string Find(string kind,string name,string hash,int line,string original){string id,key=Key(kind,name,hash,line,kind=="conversation"?FixedText.NormalizeXml(original):original);return !ambiguous.Contains(key)&&targets.TryGetValue(key,out id)?id:null;}
}
