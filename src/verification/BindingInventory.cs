using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Maintainer-only, read-only cross-platform binding extraction. Output is reviewed
// and committed as data; normal builds consume fixed coordinates, never search.
internal static class BindingInventory {
 static IEnumerable<TypeDefinition> Types(TypeDefinition t){yield return t;foreach(var n in t.NestedTypes)foreach(var x in Types(n))yield return x;}
 static string Decode(string s){return Encoding.UTF8.GetString(Convert.FromBase64String(s));}
 static string Encode(string s){return Convert.ToBase64String(Encoding.UTF8.GetBytes(s));}
 static void Main(string[] args){
  if(args.Length!=3)throw new ArgumentException("windows-original macos-original canonical-managed.tsv");
  using(var windows=AssemblyDefinition.ReadAssembly(args[0]))using(var macos=AssemblyDefinition.ReadAssembly(args[1])){
   var methods=macos.MainModule.Types.SelectMany(Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName);
   var sites=new HashSet<string>();var output=new List<string>();
   foreach(string line in File.ReadAllLines(args[2])){
    var c=line.Split('\t');if(c.Length!=7)throw new InvalidOperationException("Invalid canonical managed row");
    var original=(MethodDefinition)windows.MainModule.LookupToken(Int32.Parse(c[0]));int at=Int32.Parse(c[1]);string source=Decode(c[3]);
    BindingAnchor.Require(original,at,Decode(c[5]),source,c[6]);
    MethodDefinition target;if(!methods.TryGetValue(original.FullName,out target)||!target.HasBody)throw new InvalidOperationException("Missing exact method: "+original.FullName);
    var matches=target.Body.Instructions.Select((i,index)=>new{Instruction=i,Index=index}).Where(x=>x.Instruction.OpCode==OpCodes.Ldstr&&(string)x.Instruction.Operand==source).ToArray();
    if(matches.Length!=1){
     if(BindingAnchor.MethodFingerprint(original)==BindingAnchor.MethodFingerprint(target))matches=matches.Where(x=>x.Index==at).ToArray();
     else{string fingerprint=BindingAnchor.Fingerprint(original,at);matches=matches.Where(x=>BindingAnchor.Fingerprint(target,x.Index)==fingerprint).ToArray();}
    }
    if(matches.Length!=1)throw new InvalidOperationException("Ambiguous exact IL context: "+c[2]+" "+original.FullName+" #"+at+" matches "+matches.Length);
    int mapped=matches[0].Index;string key=target.FullName+":"+mapped;
    if(!sites.Add(key))throw new InvalidOperationException("Duplicate physical display site: "+c[2]);
    output.Add(String.Join("\t",new[]{c[2],target.MetadataToken.ToInt32().ToString(),mapped.ToString(),Encode(target.FullName),BindingAnchor.Fingerprint(target,mapped),Encode(source)}));
   }
   foreach(string row in output)Console.WriteLine(row);
  }
 }
}
