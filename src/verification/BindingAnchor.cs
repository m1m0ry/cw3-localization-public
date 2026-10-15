using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

// A fixed location must still have the reviewed display instruction and nearby IL.
// This is a guard, never a search or a fallback to another same-text instruction.
internal static class BindingAnchor {
 internal static string Fingerprint(MethodDefinition method,int at){
  return Hash(method,at,Math.Max(0,at-4),Math.Min(method.Body.Instructions.Count-1,at+4));
 }
 internal static string MethodFingerprint(MethodDefinition method){return Hash(method,0,0,method.Body.Instructions.Count-1);}
 static string Hash(MethodDefinition method,int at,int first,int last){
  var body=method.Body.Instructions;
  if(at<0||at>=body.Count)throw new InvalidOperationException("Binding index outside method");
  var rows=new List<string>();
  for(int n=first;n<=last;n++){
   var i=body[n];string name=i.OpCode.Name;object value=i.Operand;string operand="";
   if(value is Instruction){if(name.EndsWith(".s",StringComparison.Ordinal))name=name.Substring(0,name.Length-2);operand="branch:"+(body.IndexOf((Instruction)value)-at);}
   else if(value is Instruction[])operand="branches:"+String.Join(",",((Instruction[])value).Select(x=>(body.IndexOf(x)-at).ToString(CultureInfo.InvariantCulture)).ToArray());
   else if(value is VariableDefinition){var v=(VariableDefinition)value;operand="local:"+v.Index+":"+v.VariableType.FullName;}
   else if(value is ParameterDefinition){var p=(ParameterDefinition)value;operand="argument:"+p.Index+":"+p.ParameterType.FullName;}
   else if(value is IFormattable)operand=((IFormattable)value).ToString(null,CultureInfo.InvariantCulture);
   else if(value!=null)operand=value.ToString();
   rows.Add((n-at).ToString(CultureInfo.InvariantCulture)+"|"+name+"|"+Convert.ToBase64String(Encoding.UTF8.GetBytes(operand)));
  }
  using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(String.Join("\n",rows.ToArray())))).Replace("-","").ToLowerInvariant();
 }
 internal static void Require(MethodDefinition method,int at,string fullName,string source,string fingerprint){
  if(method.FullName!=fullName||!method.HasBody||at<0||at>=method.Body.Instructions.Count)throw new InvalidOperationException("Binding method/index drift: "+fullName);
  var i=method.Body.Instructions[at];
  if(i.OpCode!=OpCodes.Ldstr||(string)i.Operand!=source||Fingerprint(method,at)!=fingerprint)throw new InvalidOperationException("Binding IL anchor drift: "+fullName+" #"+at);
 }
}
