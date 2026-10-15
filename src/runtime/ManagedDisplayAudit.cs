using System;using System.IO;using System.Text;using System.Linq;using System.Collections;using System.Collections.Generic;using Mono.Cecil;using Mono.Cecil.Cil;
// Read-only literal inventory. A rejected display trace is unknown, not an internal identifier.
internal class ManagedDisplayAudit {
 internal sealed class Finding {
  internal string Classification,Consumer,Reason;
  internal Finding(string classification,string consumer,string reason){Classification=classification;Consumer=consumer;Reason=reason;}
 }
 internal sealed class Binding {internal string Id;}
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
 internal static Dictionary<string,Binding> Bindings(AssemblyDefinition original,Hashtable doc){
  var bound=new Dictionary<string,Binding>();
  foreach(Hashtable e in(ArrayList)doc["entries"]){var t=(Hashtable)e["target"];if((string)t["kind"]!="managed")continue;
   if(t.Count!=5)throw new Exception("Expected pristine anchored binding");
   int token=(int)t["method_token"],at=(int)t["instruction_index"];var m=(MethodDefinition)original.MainModule.LookupToken(token);
   BindingAnchor.Require(m,at,(string)t["method"],(string)e["source"],(string)t["anchor_sha256"]);
   string k=Key(m,at);if(bound.ContainsKey(k))throw new Exception("Duplicate physical binding: "+k);bound.Add(k,new Binding{Id=(string)e["id"]});
  }
  return bound;
 }
 static string B(string s){return Convert.ToBase64String(Encoding.UTF8.GetBytes(s));}
 static void Main(string[]a){
  if(a.Length!=2)throw new ArgumentException("original.dll dictionary.json required");
  using(var native=AssemblyDefinition.ReadAssembly(a[0])){
   var bound=Bindings(native,(Hashtable)Json.Read(File.ReadAllText(a[1])));int total=0;
   foreach(var type in Types(native.MainModule.Types))foreach(var m in type.Methods.Where(x=>x.HasBody))for(int at=0;at<m.Body.Instructions.Count;at++){
    var i=m.Body.Instructions[at];if(i.OpCode!=OpCodes.Ldstr)continue;var f=Classify(m,i);Binding b;bool adopted=bound.TryGetValue(Key(m,at),out b);
    Console.WriteLine(String.Join("\t",new[]{adopted?"bound":f.Classification,f.Classification,m.MetadataToken.ToInt32().ToString(),at.ToString(),i.Offset.ToString(),B(m.FullName),B((string)i.Operand),B(f.Consumer),B(f.Reason),B(adopted?b.Id:"")}));total++;
   }
   Console.Error.WriteLine(total+" ldstr instructions; "+bound.Count+" validated managed bindings");
  }
 }
}
