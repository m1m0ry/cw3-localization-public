using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class ManagerSnapshotContracts {
 static int checks;static void Need(bool b,string s){checks++;if(!b)throw new Exception(s);}
 static MethodDefinition Hot(AssemblyDefinition a){return a.MainModule.GetType("GameSpace").Methods.Single(m=>m.Name=="PacketsUpdate");}
 static Instruction Call(MethodDefinition m){return m.Body.Instructions.First(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).Name=="GetActiveManagers");}
 static void RejectInput(string p,Action<AssemblyDefinition> edit){using(var a=AssemblyDefinition.ReadAssembly(p)){edit(a);bool rejected=false;try{ManagerSnapshotPatch.Apply(a.MainModule);}catch(Exception){rejected=true;}Need(rejected,"reject unknown original layout");}}
 static void RejectOutput(string p,string q,Action<AssemblyDefinition> edit){using(var a=AssemblyDefinition.ReadAssembly(p))using(var b=AssemblyDefinition.ReadAssembly(q)){edit(b);bool rejected=false;try{ManagerSnapshotPatch.Reverse(a,b);int m,i;AssemblyStructure.RequireSame(a,b,out m,out i);}catch(Exception){rejected=true;}Need(rejected,"reject tampered patch");}}
 static void Main(string[] a){using(var input=AssemblyDefinition.ReadAssembly(a[0])){Need(ManagerSnapshotPatch.Apply(input.MainModule)==5,"five sites");input.Write(a[1]);bool second=false;try{ManagerSnapshotPatch.Apply(input.MainModule);}catch(Exception){second=true;}Need(second,"not twice");}
 using(var x=AssemblyDefinition.ReadAssembly(a[0]))using(var y=AssemblyDefinition.ReadAssembly(a[1])){Need(ManagerSnapshotPatch.Reverse(x,y)==5,"five reversed");int m,i;AssemblyStructure.RequireSame(x,y,out m,out i);Need(m>30,"whole fixture structure");}
 RejectInput(a[0],x=>{var m=Hot(x);var c=Call(m);m.Body.GetILProcessor().InsertBefore(c,Instruction.Create(OpCodes.Br,c));});
 RejectInput(a[0],x=>Call(Hot(x)).Next.OpCode=OpCodes.Ret);
 RejectInput(a[0],x=>{var m=Hot(x);m.Body.GetILProcessor().InsertBefore(m.Body.Instructions.Last(),Instruction.Create(OpCodes.Ldloc_0));});
 RejectInput(a[0],x=>Hot(x).Body.Instructions.First(i=>i.OpCode==OpCodes.Ldelem_Ref).OpCode=OpCodes.Stelem_Ref);
 RejectInput(a[0],x=>Hot(x).Body.InitLocals=false);
 RejectInput(a[0],x=>{var m=x.MainModule.GetType("ManagerPool`1").Methods.Single(t=>t.Name=="GetActiveManagers");m.Body.GetILProcessor().InsertBefore(m.Body.Instructions.Last(),Instruction.Create(OpCodes.Nop));});
 RejectOutput(a[0],a[1],x=>Hot(x).Body.ExceptionHandlers.Clear());
 RejectOutput(a[0],a[1],x=>x.MainModule.GetType("ManagerPool`1").Methods.Single(m=>m.Name=="__cw3SnapshotBorrow").Body.Instructions.Single(i=>i.OpCode==OpCodes.Ldc_I4&&(int)i.Operand==16384).Operand=32768);
 RejectOutput(a[0],a[1],x=>x.MainModule.GetType("ManagerPool`1").Methods.Single(m=>m.Name=="GetActiveManagers").Body.Instructions[0].OpCode=OpCodes.Ldnull);
 RejectOutput(a[0],a[1],x=>x.MainModule.GetType("ManagerPool`1").Methods.Single(m=>m.Name=="__cw3SnapshotBorrow").Body.ExceptionHandlers[0].CatchType=x.MainModule.TypeSystem.Object);
 RejectOutput(a[0],a[1],x=>x.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0))));
 // Controlled fault AFTER CopyTo has populated the buffer checks catch cleanup.
 using(var x=AssemblyDefinition.ReadAssembly(a[1])){var m=x.MainModule.GetType("ManagerPool`1").Methods.Single(t=>t.Name=="__cw3SnapshotBorrow");var c=m.Body.Instructions.Single(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).Name=="CopyTo");var il=m.Body.GetILProcessor();var message=il.Create(OpCodes.Ldstr,"copy fault");var create=il.Create(OpCodes.Newobj,x.MainModule.ImportReference(typeof(InvalidOperationException).GetConstructor(new[]{typeof(string)})));il.InsertAfter(c,message);il.InsertAfter(message,create);il.InsertAfter(create,il.Create(OpCodes.Throw));x.Write(a[2]);}
 Console.WriteLine("PASS "+checks+" snapshot patch/reversal/rejection contracts");}
}
