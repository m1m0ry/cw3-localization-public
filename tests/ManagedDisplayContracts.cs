using System;using System.IO;using System.Linq;using System.Collections;using Mono.Cecil;using Mono.Cecil.Cil;
class ManagedDisplayContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(string[]a){
  var fixture=AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("AuditFixture",new Version(1,0)),"AuditFixture",ModuleKind.Dll);var module=fixture.MainModule;var type=new TypeDefinition("","Fixture",TypeAttributes.Public,module.TypeSystem.Object);module.Types.Add(type);
  Func<MethodDefinition> method=()=>{var m=new MethodDefinition("Display",MethodAttributes.Static|MethodAttributes.Public,module.TypeSystem.Void);type.Methods.Add(m);return m;};
  var label=new MethodReference("Label",module.TypeSystem.Void,new TypeReference("UnityEngine","GUILayout",module,module.TypeSystem.CoreLibrary));label.Parameters.Add(new ParameterDefinition(module.TypeSystem.String));
  var direct=method();var il=direct.Body.GetILProcessor();var text=il.Create(OpCodes.Ldstr,"Price: ");il.Append(text);il.Append(il.Create(OpCodes.Call,label));il.Append(il.Create(OpCodes.Ret));Need(ManagedDisplayAudit.Classify(direct,text).Classification=="display_candidate","Caption literal candidate");
  var style=new MethodReference("GetStyle",module.TypeSystem.Object,new TypeReference("UnityEngine","GUISkin",module,module.TypeSystem.CoreLibrary));style.HasThis=true;style.Parameters.Add(new ParameterDefinition(module.TypeSystem.String));
  var lookup=method();il=lookup.Body.GetILProcessor();il.Append(il.Create(OpCodes.Ldnull));text=il.Create(OpCodes.Ldstr,"Button");il.Append(text);il.Append(il.Create(OpCodes.Callvirt,style));il.Append(il.Create(OpCodes.Pop));il.Append(il.Create(OpCodes.Ret));Need(ManagedDisplayAudit.Classify(lookup,text).Classification=="internal_identifier","Explicit style lookup key");
  var unknownCall=new MethodReference("UnknownConsumer",module.TypeSystem.String,type);unknownCall.Parameters.Add(new ParameterDefinition(module.TypeSystem.String));var unknown=method();il=unknown.Body.GetILProcessor();text=il.Create(OpCodes.Ldstr,"Unknown string");il.Append(text);il.Append(il.Create(OpCodes.Call,unknownCall));il.Append(il.Create(OpCodes.Call,label));il.Append(il.Create(OpCodes.Ret));Need(ManagedDisplayAudit.Classify(unknown,text).Classification=="unknown","Unknown call followed by display cannot be guessed internal or candidate");
  var field=new FieldDefinition("unclassifiedField",FieldAttributes.Static|FieldAttributes.Public,module.TypeSystem.String);type.Fields.Add(field);var stored=method();il=stored.Body.GetILProcessor();text=il.Create(OpCodes.Ldstr,"A field may be a caption");il.Append(text);il.Append(il.Create(OpCodes.Stsfld,field));il.Append(il.Create(OpCodes.Ret));Need(ManagedDisplayAudit.Classify(stored,text).Classification=="unknown","Field storage has no proven internal role");
  var mixed=method();il=mixed.Body.GetILProcessor();text=il.Create(OpCodes.Ldstr,"Button");il.Append(text);il.Append(il.Create(OpCodes.Dup));il.Append(il.Create(OpCodes.Call,label));il.Append(il.Create(OpCodes.Stsfld,field));il.Append(il.Create(OpCodes.Ret));Need(ManagedDisplayAudit.Classify(mixed,text).Classification=="unknown","Mixed display/model use cannot be adopted");
  var nested=new TypeDefinition("","Nested",TypeAttributes.NestedPublic,module.TypeSystem.Object);type.NestedTypes.Add(nested);Need(ManagedDisplayAudit.Types(module.Types).Contains(nested),"Nested types are inventoried");
  using(var native=AssemblyDefinition.ReadAssembly(a[0])){
   var root=(Hashtable)Json.Read(File.ReadAllText(a[1]));var bound=ManagedDisplayAudit.Bindings(native,root);int expected=((ArrayList)root["entries"]).Cast<Hashtable>().Count(e=>(string)((Hashtable)e["target"])["kind"]=="managed");Need(bound.Count==expected,"Every managed binding mapped to its guarded original site");
   var events=native.MainModule.GetType("GameEventManager").Methods.Single(m=>m.Name=="ShowEvent"&&m.Parameters[0].ParameterType.FullName=="GameEventManager/GAME_EVENT");int captions=0,icons=0;
   foreach(var i in events.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr)){
    int at=events.Body.Instructions.IndexOf(i);var next=events.Body.Instructions[at+1];var f=ManagedDisplayAudit.Classify(events,i);
    if(next.OpCode==OpCodes.Stloc_3||next.OpCode==OpCodes.Stloc_S&&((VariableDefinition)next.Operand).Index==4){Need(f.Classification=="display_candidate","Real event caption recognized independently of binding");Need(bound.ContainsKey(ManagedDisplayAudit.Key(events,at)),"Real caption is currently bound");captions++;}
    if(next.OpCode==OpCodes.Stloc_2){Need(f.Classification=="internal_identifier","Real event icon key protected");Need(!bound.ContainsKey(ManagedDisplayAudit.Key(events,at)),"Real icon key unbound");icons++;}
   }
   int live=0;foreach(string name in new[]{"CommandCenter","BuildHandlers","WorldMachineManager"})foreach(var m in native.MainModule.GetType(name).Methods.Where(m=>m.HasBody))foreach(var i in m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr&&new[]{"Upgrade to Lvl: "," for ","Price: ","Map Code:","Rand"}.Contains((string)i.Operand))){Need(ManagedDisplayAudit.Classify(m,i).Classification=="display_candidate","Previously missed native dynamic caption recognized");Need(bound.ContainsKey(ManagedDisplayAudit.Key(m,m.Body.Instructions.IndexOf(i))),"Previously missed caption currently bound");live++;}
   Need(captions==30&&icons==26&&live==10,"Real native caption/key inventory");
   var scoreEntry=((ArrayList)root["entries"]).Cast<Hashtable>().Single(e=>(string)e["source"]=="Online Scores"&&(string)((Hashtable)e["target"])["kind"]=="managed");
   var scoreTarget=(Hashtable)scoreEntry["target"];int scoreToken=(int)scoreTarget["method_token"];
   int scoreIndex=(int)scoreTarget["instruction_index"];
   var scores=(MethodDefinition)native.MainModule.LookupToken(scoreToken);var title=scores.Body.Instructions[scoreIndex];
   Need(scores.FullName=="System.Void ScoreViewerManager::OnGUI()"&&title.OpCode==OpCodes.Ldstr&&(string)title.Operand=="Online Scores","Exact native leaderboard title");
   Need(ManagedDisplayAudit.Classify(scores,title).Classification=="display_candidate"&&bound.ContainsKey(ManagedDisplayAudit.Key(scores,scoreIndex)),"Leaderboard window title reaches display and is bound independently of its button");
   var entry=((ArrayList)root["entries"]).Cast<Hashtable>().First(e=>(string)((Hashtable)e["target"])["kind"]=="managed");var source=entry["source"];entry["source"]="DRIFT";bool refused=false;try{ManagedDisplayAudit.Bindings(native,root);}catch(Exception){refused=true;}Need(refused,"Binding source drift refused");entry["source"]=source;
   var target=(Hashtable)entry["target"];var signature=target["method"];target["method"]="Wrong::Signature";refused=false;try{ManagedDisplayAudit.Bindings(native,root);}catch(Exception){refused=true;}Need(refused,"Exact method signature required");target["method"]=signature;
   var anchor=target["anchor_sha256"];target["anchor_sha256"]=new string('0',64);refused=false;try{ManagedDisplayAudit.Bindings(native,root);}catch(Exception){refused=true;}Need(refused,"IL anchor drift refused");target["anchor_sha256"]=anchor;
   bool repeated=false;
   foreach(Hashtable candidate in (ArrayList)root["entries"]){var t=(Hashtable)candidate["target"];if((string)t["kind"]!="managed")continue;var m=(MethodDefinition)native.MainModule.LookupToken((int)t["method_token"]);int at=(int)t["instruction_index"];
    var twin=m.Body.Instructions.Select((i,index)=>new{Instruction=i,Index=index}).FirstOrDefault(x=>x.Index!=at&&x.Instruction.OpCode==OpCodes.Ldstr&&(string)x.Instruction.Operand==(string)candidate["source"]&&BindingAnchor.Fingerprint(m,x.Index)!=(string)t["anchor_sha256"]);
    if(twin==null)continue;t["instruction_index"]=twin.Index;refused=false;try{ManagedDisplayAudit.Bindings(native,root);}catch(Exception){refused=true;}t["instruction_index"]=at;Need(refused,"Same literal at another IL site is refused");repeated=true;break;
   }Need(repeated,"Real repeated literal exercises anchor refusal");
   Console.WriteLine("PASS IL classification: unknown/mixed/field uses retained, nested types, "+expected+" bindings, 30 real event captions, 26 icon keys, 10 dynamic captions and source/signature/anchor drift and repeated-literal refusal");
  }
 }
}
