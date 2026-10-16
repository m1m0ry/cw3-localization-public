using System;using System.IO;using System.Collections;using System.Collections.Generic;using System.Text.RegularExpressions;

// The release owns defaults; a separate, optional file owns only user overrides.
internal static class TranslationFiles {
 internal static Dictionary<string,string> Load(string folder,Dictionary<string,Hashtable> definitions,Action<string> warning){
  var result=new Dictionary<string,string>();
  string defaults=Path.Combine(folder,"zh-CN.default.json");
  foreach(string path in new[]{defaults,Path.Combine(folder,"zh-CN.user.json")}){
   if(path.EndsWith("zh-CN.user.json",StringComparison.Ordinal)&&!File.Exists(path))continue;
   try{foreach(var row in Read(path,definitions))result[row.Key]=row.Value;}
   catch(Exception e){warning(Path.GetFileName(path)+": "+e.Message);}
  }
  return result;
 }
 static Dictionary<string,string> Read(string path,Dictionary<string,Hashtable> definitions){
  if(new FileInfo(path).Length>4000000)throw new FormatException("Dictionary too large");
  var root=(Hashtable)Json.Read(File.ReadAllText(path));
  if((int)root["format"]!=1||(root["language"] as string)!="zh-CN")throw new FormatException("Dictionary format");
  var seen=new HashSet<string>();var values=new Dictionary<string,string>();
  foreach(Hashtable row in (ArrayList)root["entries"]){
   string id=row["id"] as string;if(id==null||!seen.Add(id))throw new FormatException("Duplicate ID");
   Hashtable definition;string value=row["translation"] as string;
   if(definitions.TryGetValue(id,out definition)&&(row["source"] as string)==(definition["source"] as string)&&!String.IsNullOrEmpty(value)&&Tokens((string)definition["source"],value,definition["kind"] as string))values.Add(id,value);
  }
  return values;
 }
 static bool SameTokens(string a,string b,string pattern,bool reorder){
  var x=new List<string>();var y=new List<string>();foreach(Match m in Regex.Matches(a,pattern))x.Add(m.Value);foreach(Match m in Regex.Matches(b,pattern))y.Add(m.Value);
  if(reorder){x.Sort(StringComparer.Ordinal);y.Sort(StringComparer.Ordinal);}if(x.Count!=y.Count)return false;for(int i=0;i<x.Count;i++)if(x[i]!=y[i])return false;return true;
 }
 static bool Tokens(string a,string b,string kind){
  const string braces=@"\{\d+(?:[^{}]*)\}",printf=@"%(?:\d+\$)?[sdif]",tags=@"\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]";
  if(!SameTokens(a,b,tags,false))return false;
  return kind=="crpl_output"?SameTokens(a,b,braces,true)&&SameTokens(a,b,printf,false):SameTokens(a,b,braces+"|"+printf,false);
 }
}
