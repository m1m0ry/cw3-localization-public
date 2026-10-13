using System;using System.IO;using System.Text;using System.Collections;using System.Collections.Generic;using System.Reflection;
// Execute the shipped ForGuiMessage and collector, with Unity scene/frame getters
// supplied by ScriptOutputEngine. The game, fonts and UI are never initialized.
class ScriptOutputCandidateContracts {
 static readonly BindingFlags Flags=BindingFlags.Static|BindingFlags.NonPublic;
 static object Get(string name){return typeof(CW3Runtime).GetField(name,Flags).GetValue(null);}
 static void Set(string name,object value){typeof(CW3Runtime).GetField(name,Flags).SetValue(null,value);}
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static string Display(Hashtable d,string raw,string[] arguments){Set("guiId",d["id"]);Set("guiOriginal",raw);Set("guiArguments",arguments);Set("guiContext","script:"+d["script"]+":"+d["script_hash"]+":"+d["call_line"]);return CW3Runtime.ForGuiMessage(raw);}
 static void Main(string[] args){
  Set("loaded",true);var definitions=(Dictionary<string,Hashtable>)Get("definitions");var translations=(Dictionary<string,string>)Get("translations");var bindings=new ScriptBindings();
  var adopted=new Dictionary<string,string>();foreach(Hashtable entry in (ArrayList)((Hashtable)Json.Read(File.ReadAllText(args[1])))["entries"])adopted.Add((string)entry["id"],(string)entry["translation"]);
  var collector=new Candidates(true,args[0]);Set("candidates",collector);int outputs=0;
  foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){
   if((string)d["kind"]!="crpl_output")continue;definitions.Add((string)d["id"],d);bindings.Add(d);outputs++;
   for(int attempt=0;attempt<2;attempt++){
    var slots=(ArrayList)d["slots"];var values=new string[slots.Count];for(int i=0;i<values.Length;i++)values[i]=(string)slots[i]=="fraction_or_blank"?(attempt==0?"1/2":" "):attempt==0?"12.5":"24";
    string raw=ScriptBindings.Format((string)d["source"],values);string[] matched;
    Need(bindings.FindOutput((string)d["script"],(string)d["script_hash"],(int)d["call_line"],(int)d["call_index"],raw,out matched)==(string)d["id"],"Actual output binding matches expanded numeric text");
    Need(Display(d,raw,matched)==raw,"Missing translation returns each unmodified display string");
    translations[(string)d["id"]]=adopted[(string)d["id"]];
    Need(Display(d,raw,matched)==ScriptBindings.Format(adopted[(string)d["id"]],matched),"Translated output formats arguments without recording a miss");
    translations.Remove((string)d["id"]);
   }
  }
  Need(outputs==27&&collector.Finish(),"All adopted output bindings captured");
  var snapshot=(Hashtable)Json.Read(File.ReadAllText(args[0]));var rows=(ArrayList)snapshot["candidates"];Need(rows.Count==outputs,"Numeric changes deduplicate by bound template");
  foreach(Hashtable row in rows){Need((int)row["count"]==2&&(string)row["reason"]=="missing_translation"&&(string)row["kind"]=="crpl_output","Only missing translations are captured");Need((string)row["source"]==(string)definitions[(string)row["id"]]["source"],"Collector stores exact bound template");}
  Console.WriteLine("PASS actual runtime: 27 output bindings, unchanged missing display, translated formatting, template candidate counts");
 }
}
