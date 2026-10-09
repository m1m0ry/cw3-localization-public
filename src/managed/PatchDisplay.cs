using System;using System.Linq;using System.Text;using System.IO;using Mono.Cecil;using Mono.Cecil.Cil;
class PatchDisplay {
 static void Main(string[] a){
  var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(a[3]);var asm=AssemblyDefinition.ReadAssembly(a[0],new ReaderParameters{AssemblyResolver=resolver});int changed=0;
  foreach(var line in File.ReadAllLines(a[1])){
   var c=line.Split('\t');var m=(MethodDefinition)asm.MainModule.LookupToken(Int32.Parse(c[0]));int idx=Int32.Parse(c[1]);var i=m.Body.Instructions[idx];
   string source=Encoding.UTF8.GetString(Convert.FromBase64String(c[2]));string target=Encoding.UTF8.GetString(Convert.FromBase64String(c[3]));
   if(i.OpCode!=OpCodes.Ldstr||(string)i.Operand!=source)throw new Exception("Site mismatch "+m.FullName+" #"+idx);
   i.Operand=target;changed++;
  }
  asm.Write(a[2]);Console.WriteLine("Changed "+changed+" reviewed display ldstr operands; no instruction or hook added.");
 }
}
