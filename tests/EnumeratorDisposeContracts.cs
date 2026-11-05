using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;
class EnumeratorDisposeContracts {
 static int checks;
 static void Need(bool value,string label){checks++;if(!value)throw new Exception(label);}
 static void Verify(string before,string after){using(var a=AssemblyDefinition.ReadAssembly(before))using(var b=AssemblyDefinition.ReadAssembly(after)){int n=EnumeratorDisposePatch.Reverse(a.MainModule,b.MainModule),methods,instructions;Need(n>=7,"all supported types covered");AssemblyStructure.RequireSame(a,b,out methods,out instructions);}}
 static void Rejected(string before,string after,Action<AssemblyDefinition> mutate){using(var a=AssemblyDefinition.ReadAssembly(before))using(var b=AssemblyDefinition.ReadAssembly(after)){mutate(b);bool failed=false;try{EnumeratorDisposePatch.Reverse(a.MainModule,b.MainModule);int methods,instructions;AssemblyStructure.RequireSame(a,b,out methods,out instructions);}catch(Exception){failed=true;}Need(failed,"tampered optimization must fail");}}
 static Instruction Constraint(AssemblyDefinition a){return a.MainModule.Types.SelectMany(t=>t.Methods).Where(m=>m.HasBody).SelectMany(m=>m.Body.Instructions).First(i=>i.OpCode==OpCodes.Constrained);}
 static void InvalidEntryRejected(string path,bool exceptionBoundary){using(var a=AssemblyDefinition.ReadAssembly(path)){
  var method=a.MainModule.Types.SelectMany(t=>t.Methods).First(m=>m.HasBody&&m.Body.Instructions.Any(i=>i.OpCode==OpCodes.Box&&i.Operand.ToString().StartsWith("System.Collections.Generic.List")));
  var call=method.Body.Instructions.First(i=>i.OpCode==OpCodes.Box&&i.Operand.ToString().StartsWith("System.Collections.Generic.List")).Next;
  if(exceptionBoundary)method.Body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Finally){TryStart=method.Body.Instructions[0],TryEnd=call,HandlerStart=call,HandlerEnd=method.Body.Instructions.Last()});
  else method.Body.GetILProcessor().InsertBefore(method.Body.Instructions[0],Instruction.Create(OpCodes.Br,call));
  bool failed=false;try{EnumeratorDisposePatch.Apply(a.MainModule);}catch(Exception){failed=true;}Need(failed,"reject branch/EH entry into prefixed call");
 }}
 static void Main(string[] args){var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(args[0]));int count;
  using(var a=AssemblyDefinition.ReadAssembly(args[0],new ReaderParameters{AssemblyResolver=resolver})){
   count=EnumeratorDisposePatch.Apply(a.MainModule);Need(count>=7,"nonempty rewrite");
   var calls=a.MainModule.Types.SelectMany(t=>t.Methods).Where(m=>m.HasBody).SelectMany(m=>m.Body.Instructions).ToArray();
   Need(calls.Any(i=>i.OpCode==OpCodes.Box&&i.Operand.ToString().Contains("CustomEnumerator")),"exclude custom enumerator");
   bool refused=false;try{EnumeratorDisposePatch.Apply(a.MainModule);}catch(Exception){refused=true;}Need(refused,"reject accidental second patch");a.Write(args[1]);
  }
  Verify(args[0],args[1]);InvalidEntryRejected(args[0],false);InvalidEntryRejected(args[0],true);
  Rejected(args[0],args[1],a=>Constraint(a).Previous.OpCode=OpCodes.Ldloc);
  Rejected(args[0],args[1],a=>Constraint(a).Operand=a.MainModule.TypeSystem.Int32);
  Rejected(args[0],args[1],a=>Constraint(a).Next.OpCode=OpCodes.Call);
  Rejected(args[0],args[1],a=>a.MainModule.Types.Single(t=>t.Name=="EnumeratorDisposeFixture").Fields[0].Name="changed");
  Rejected(args[0],args[1],a=>a.MainModule.AssemblyReferences.Add(new AssemblyNameReference("UnexpectedRuntime",new Version(1,0))));
  Rejected(args[0],args[1],a=>{var method=a.MainModule.Types.SelectMany(t=>t.Methods).First(m=>m.HasBody&&m.Body.Instructions.Any(i=>i.OpCode==OpCodes.Constrained));method.Body.InitLocals=!method.Body.InitLocals;});
  Console.WriteLine("PASS "+checks+" patch boundary/reversal checks; "+count+" boxes removed");
 }
}
