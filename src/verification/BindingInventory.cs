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
  if(args.Length!=4)throw new ArgumentException("windows-original windows-render macos-original canonical-managed.tsv");
  using(var windows=AssemblyDefinition.ReadAssembly(args[0]))using(var render=AssemblyDefinition.ReadAssembly(args[1]))using(var macos=AssemblyDefinition.ReadAssembly(args[2])){
   var methods=macos.MainModule.Types.SelectMany(Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName);
   var originals=windows.MainModule.Types.SelectMany(Types).SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName);
   var sites=new HashSet<string>();var output=new List<string>();
   foreach(string line in File.ReadAllLines(args[3])){
    var c=line.Split('\t');if(c[4]!="v9"&&c[4]!="v10")throw new InvalidOperationException("Unknown canonical stage");
    var staged=(MethodDefinition)(c[4]=="v9"?windows:render).MainModule.LookupToken(Int32.Parse(c[0]));int at=Int32.Parse(c[1]);string source=Decode(c[3]);
    if(!staged.HasBody||at<0||at>=staged.Body.Instructions.Count||staged.Body.Instructions[at].OpCode!=OpCodes.Ldstr||(string)staged.Body.Instructions[at].Operand!=source)throw new InvalidOperationException("Canonical stage source drift: "+c[2]);
    var original=originals[staged.FullName];
    if(c[4]=="v10"){
     var before=original.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr).ToArray();var after=staged.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldstr).ToArray();
     if(!before.Select(i=>(string)i.Operand).SequenceEqual(after.Select(i=>(string)i.Operand)))throw new InvalidOperationException("Canonical stage literal sequence drift: "+c[2]);
     at=original.Body.Instructions.IndexOf(before[Array.IndexOf(after,staged.Body.Instructions[at])]);
    }
    if(!original.HasBody||at<0||at>=original.Body.Instructions.Count||original.Body.Instructions[at].OpCode!=OpCodes.Ldstr||(string)original.Body.Instructions[at].Operand!=source)throw new InvalidOperationException("Canonical pristine source drift: "+c[2]);
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
