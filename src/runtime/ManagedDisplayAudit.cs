using System;using System.IO;using System.Text;using System.Linq;using System.Collections;using System.Collections.Generic;using Mono.Cecil;using Mono.Cecil.Cil;
// Read-only literal inventory. A rejected display trace is unknown, not an internal identifier.
internal class ManagedDisplayAudit {
 internal sealed class Finding {
  internal string Classification,Consumer,Reason;
  internal Finding(string classification,string consumer,string reason){Classification=classification;Consumer=consumer;Reason=reason;}
 }
 internal sealed class Binding {internal string Id,Stage;}
 internal static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types){foreach(var t in types){yield return t;foreach(var n in Types(t.NestedTypes))yield return n;}}
 internal static string Key(MethodDefinition m,int at){return m.MetadataToken.ToInt32()+":"+at;}
 internal static Finding Classify(MethodDefinition m,Instruction source){
  if(source.OpCode!=OpCodes.Ldstr)throw new ArgumentException("Expected ldstr");string rejected;
  try{var c=GuiCaptionAudit.Consumer(m,source);return new Finding("display_candidate",c.Operand.ToString(),"Verified GUI/UILabel/InfoPanel caption argument; reachability and translation need review");}catch(Exception e){rejected=e.Message;}
  try{var c=NativeEventCaptionAudit.CaptionConsumer(m,source);return new Finding("display_candidate",c.Operand.ToString(),"Verified native event caption local and final argument");}catch(Exception){}
  try{var c=NativeEventCaptionAudit.IconConsumer(m,source);return new Finding("internal_identifier",c.Operand.ToString(),"Verified native event icon local V_2; separate from caption arguments");}catch(Exception){}
  int at=m.Body.Instructions.IndexOf(source)+1;while(at<m.Body.Instructions.Count&&m.Body.Instructions[at].OpCode==OpCodes.Nop)at++;
  if(at<m.Body.Instructions.Count){var i=m.Body.Instructions[at];var c=i.Operand as MethodReference;
   if(c!=null&&(i.OpCode==OpCodes.Call||i.OpCode==OpCodes.Callvirt)){
    string type=c.DeclaringType.FullName;
    bool key=c.Parameters.Count==1&&c.Parameters[0].ParameterType.FullName=="System.String"&&((type=="UnityEngine.GUISkin"&&c.Name=="GetStyle")||(type=="UnityEngine.GameObject"&&c.Name=="Find")||(type=="UnityEngine.Transform"&&c.Name=="Find"));
    bool comparison=type=="System.String"&&c.ReturnType.FullName=="System.Boolean"&&new[]{"Equals","op_Equality","op_Inequality"}.Contains(c.Name)&&c.Parameters.Count>0&&c.Parameters.All(p=>p.ParameterType.FullName=="System.String");
    if(key||comparison)return new Finding("internal_identifier",c.FullName,key?"Literal consumed immediately as a style/object lookup key":"Literal consumed immediately by a string comparison, not displayed");
   }
  }
  return new Finding("unknown","",rejected);
 }
 internal static Dictionary<string,Binding> Bindings(AssemblyDefinition original,AssemblyDefinition render,Hashtable doc){
  var bound=new Dictionary<string,Binding>();var stages=new Dictionary<int,Dictionary<int,int>>();var nativeMethods=Types(original.MainModule.Types).SelectMany(x=>x.Methods).ToDictionary(x=>x.FullName);
  foreach(Hashtable e in(ArrayList)doc["entries"]){var t=(Hashtable)e["target"];if((string)t["kind"]!="managed")continue;
   string stage=(string)t["stage"];if(stage!="v9"&&stage!="v10")throw new Exception("Unknown binding stage "+stage);
   int token=(int)t["method_token"],at=(int)t["instruction_index"];var m=(MethodDefinition)(stage=="v9"?original:render).MainModule.LookupToken(token);
   if(!m.HasBody||at<0||at>=m.Body.Instructions.Count||m.Body.Instructions[at].OpCode!=OpCodes.Ldstr||(string)m.Body.Instructions[at].Operand!=(string)e["source"])throw new Exception("Binding source drift: "+e["id"]);
   MethodDefinition native;if(!nativeMethods.TryGetValue(m.FullName,out native))throw new Exception("Original binding method missing: "+m.FullName);int nativeAt=at;
   if(stage=="v10"){
    Dictionary<int,int> map;if(!stages.TryGetValue(token,out map)){
     if(native.FullName!=m.FullName)throw new Exception("Binding method identity drift");var before=native.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr).ToArray();var after=m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr).ToArray();
     if(!before.Select(i=>(string)i.Operand).SequenceEqual(after.Select(i=>(string)i.Operand)))throw new Exception("Stage literal sequence drift: "+m.FullName);
     map=new Dictionary<int,int>();for(int n=0;n<before.Length;n++)map.Add(m.Body.Instructions.IndexOf(after[n]),native.Body.Instructions.IndexOf(before[n]));stages.Add(token,map);
    }
    nativeAt=map[at];
   }
   string k=Key(native,nativeAt);if(bound.ContainsKey(k))throw new Exception("Duplicate physical binding: "+k);bound.Add(k,new Binding{Id=(string)e["id"],Stage=stage});
  }
  return bound;
 }
 static string B(string s){return Convert.ToBase64String(Encoding.UTF8.GetBytes(s));}
 static void Main(string[]a){
  if(a.Length!=3)throw new ArgumentException("original.dll render.dll dictionary.json required");
  using(var native=AssemblyDefinition.ReadAssembly(a[0]))using(var render=AssemblyDefinition.ReadAssembly(a[1])){
   var bound=Bindings(native,render,(Hashtable)Json.Read(File.ReadAllText(a[2])));int total=0;
   foreach(var type in Types(native.MainModule.Types))foreach(var m in type.Methods.Where(x=>x.HasBody))for(int at=0;at<m.Body.Instructions.Count;at++){
    var i=m.Body.Instructions[at];if(i.OpCode!=OpCodes.Ldstr)continue;var f=Classify(m,i);Binding b;bool adopted=bound.TryGetValue(Key(m,at),out b);
    Console.WriteLine(String.Join("\t",new[]{adopted?"bound":f.Classification,f.Classification,m.MetadataToken.ToInt32().ToString(),at.ToString(),i.Offset.ToString(),B(m.FullName),B((string)i.Operand),B(f.Consumer),B(f.Reason),B(adopted?b.Id:""),adopted?b.Stage:""}));total++;
   }
   Console.Error.WriteLine(total+" ldstr instructions; "+bound.Count+" validated managed bindings");
  }
 }
}
