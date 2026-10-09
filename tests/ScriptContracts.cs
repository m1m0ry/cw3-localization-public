using System;using System.IO;using System.Text;using System.Collections;using System.Collections.Generic;
class ScriptContracts {
 sealed class Row{internal string Text;}
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(string[] args){
  var scripts=new ScriptBindings();var messages=new MessageBindings();var defs=new Dictionary<string,Hashtable>();var values=new Dictionary<string,string>();var scripted=new List<Hashtable>();
  foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){defs.Add((string)d["id"],d);scripts.Add(d);if(d.ContainsKey("script_hash"))scripted.Add(d);}
  foreach(Hashtable d in (ArrayList)((Hashtable)Json.Read(File.ReadAllText(args[0])))["entries"])values.Add((string)d["id"],(string)d["translation"]);
  int outputs=0;foreach(var d in scripted){if((string)d["kind"]!="crpl_output")continue;
   string name=(string)d["script"],hash=(string)d["script_hash"],sample=(string)d["source"];int line=(int)d["call_line"],ordinal=(int)d["call_index"];var slots=(ArrayList)d["slots"];var expected=new string[slots.Count];
   for(int i=0;i<slots.Count;i++){expected[i]=(string)slots[i]=="fraction_or_blank"?"123/456":"-1.25E+2";sample=sample.Replace("{"+i+"}",expected[i]);}
   string[] actual;Need(scripts.FindOutput(name,hash,line,ordinal,sample,out actual)==(string)d["id"],"Reviewed output position binds");Need(ScriptBindings.Format(values[(string)d["id"]],actual)==ScriptBindings.Format(values[(string)d["id"]],expected),"Dynamic values preserved exactly");
   Need(scripts.FindOutput(name,"changed",line,ordinal,sample,out actual)==null,"Output code drift fallback");Need(scripts.FindOutput(name+"community",hash,line,ordinal,sample,out actual)==null,"Output script origin guard");Need(scripts.FindOutput(name,hash,line+1,ordinal,sample,out actual)==null,"Output line guard");Need(scripts.FindOutput(name,hash,line,ordinal+100,sample,out actual)==null,"Same-line output position guard");Need(scripts.FindOutput(name,hash,line,ordinal,sample+"!",out actual)==null,"Output full source guard");
   for(int i=0;i<slots.Count;i++){string rejected=((string)d["source"]).Replace("{"+i+"}","internal_identifier");for(int j=0;j<slots.Count;j++)rejected=rejected.Replace("{"+j+"}",expected[j]);Need(scripts.FindOutput(name,hash,line,ordinal,rejected,out actual)==null,"Slots accept no arbitrary identifiers");}
   if(slots.Count>0&&(string)slots[0]=="fraction_or_blank"){string blank=((string)d["source"]).Replace("{0}"," ").Replace("{1}"," ");Need(scripts.FindOutput(name,hash,line,ordinal,blank,out actual)==(string)d["id"],"Native blank initialization supported");}
   var duplicateOutput=new ScriptBindings();duplicateOutput.Add(d);duplicateOutput.Add(d);Need(duplicateOutput.FindOutput(name,hash,line,ordinal,sample,out actual)==null,"Ambiguous templates fallback");outputs++;
  }
  int conversations=0,shows=0;foreach(var d in scripted){if((string)d["kind"]=="crpl_output")continue;
   string kind=(string)d["kind"]=="crpl_conversation"?"conversation":"show",name=(string)d["script"],hash=(string)d["script_hash"],original=ScriptBindings.DisplaySource(d);int line=(int)d["call_line"];
   string id=scripts.Find(kind,name,hash,line,original);Need(id==(string)d["id"],"Declared command binds");Need(scripts.Find(kind,name,"altered",line,original)==null,"Changed script cannot translate");Need(scripts.Find(kind,name+"other",hash,line,original)==null,"Wrong script name fallback");Need(scripts.Find(kind,name,hash,line+1,original)==null,"Wrong command line fallback");Need(scripts.Find(kind,name,hash,line,original+" ")==null,"Source drift fallback");Need(scripts.Find(kind=="show"?"conversation":"show",name,hash,line,original)==null,"Wrong display family fallback");
   if(kind=="conversation"){
    var row=new Row{Text=original};object owner=new object();string status;messages.Added(owner,row);Need(messages.Display(original,row,defs,values,out status)==original,"A familiar dynamic string does not guess");
    messages.BindScript(owner,row,id,"exact script command");Need(messages.Display(original,row,defs,values,out status)==values[id]&&status=="translated","Appended row displays translation");Need(row.Text==original,"Message model stays original");Need(messages.Display(original+" ",row,defs,values,out status)==original+" "&&status=="bound_source_mismatch","Changed row falls back independently");
    messages.Clear(owner);Need(messages.Get(row)==null,"Native clear releases script binding");conversations++;
   }else shows++;
  }
  var first=scripted.Find(d=>(string)d["kind"]!="crpl_output");var duplicate=new ScriptBindings();duplicate.Add(first);duplicate.Add(first);Need(duplicate.Find((string)first["kind"]=="crpl_conversation"?"conversation":"show",(string)first["script"],(string)first["script_hash"],(int)first["call_line"],ScriptBindings.DisplaySource(first))==null,"Ambiguous declaration fallback");
  var independent=new ScriptBindings();var one=(Hashtable)first.Clone();var two=(Hashtable)first.Clone();one["call_line"]=100000;two["call_line"]=100001;two["id"]="second-context";independent.Add(one);independent.Add(two);string family=(string)first["kind"]=="crpl_conversation"?"conversation":"show";Need(independent.Find(family,(string)one["script"],(string)one["script_hash"],100000,ScriptBindings.DisplaySource(one))==(string)one["id"]&&independent.Find(family,(string)two["script"],(string)two["script_hash"],100001,ScriptBindings.DisplaySource(two))=="second-context","Identical phrases at distinct commands retain independent context");
  Console.WriteLine("PASS "+conversations+" script conversations and "+shows+" literal ShowMessage targets and "+outputs+" reviewed numeric outputs: exact command origin, independent drift, raw model, lifecycle and ambiguous fallback. No game code executed.");
 }
}
