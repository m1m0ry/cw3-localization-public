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
   if(definitions.TryGetValue(id,out definition)&&(row["source"] as string)==(definition["source"] as string)&&!String.IsNullOrEmpty(value)&&Tokens((string)definition["source"],value))values.Add(id,value);
  }
  return values;
 }
 static bool Tokens(string a,string b){foreach(string rx in new[]{@"\{\d+(?:[^{}]*)\}|%(?:\d+\$)?[sdif]",@"\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]"}){var x=Regex.Matches(a,rx);var y=Regex.Matches(b,rx);if(x.Count!=y.Count)return false;for(int i=0;i<x.Count;i++)if(x[i].Value!=y[i].Value)return false;}return true;}
}
