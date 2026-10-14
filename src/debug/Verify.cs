using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;
class Verify {
 static void Require(bool b,string msg){if(!b)throw new Exception(msg);}
 static void Main(string[] a){
  var old=AssemblyDefinition.ReadAssembly(a[0]);var patch=AssemblyDefinition.ReadAssembly(a[1]);int methods=0,instructions=0;
  foreach(string name in new[]{"MainMenu","GameSpace","MessageDialogManager"}){var method=patch.MainModule.GetType(name).Methods.Single(x=>x.Name=="Awake");var first=method.Body.Instructions[0];Require(first.OpCode==OpCodes.Call&&((MethodReference)first.Operand).FullName=="System.Void CW3Debug::Boot()","unexpected hook");method.Body.Instructions.RemoveAt(0);}
  AssemblyStructure.RequireSame(old,patch,out methods,out instructions);
  Console.WriteLine("PASS: original types, field order, method signatures, "+methods+" methods and "+instructions+" IL instructions unchanged after removing exactly three debug Boot calls.");
 }
}
