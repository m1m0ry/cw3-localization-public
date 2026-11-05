using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class UnitSortCapacityContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}static void Reject(Action f,string why){bool yes=false;try{f();}catch(Exception){yes=true;}Need(yes,why);}
 static void Main(string[] a){
  var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(Path.GetDirectoryName(a[0]));var productionResolver=new DefaultAssemblyResolver();if(a.Length>2)productionResolver.AddSearchDirectory(a[3]);
  using(var fixture=AssemblyDefinition.ReadAssembly(a[0],new ReaderParameters{AssemblyResolver=resolver})){
   Reject(()=>UnitSortCapacityPatch.Apply(fixture.MainModule),"fixture not production whitelist");Need(UnitSortCapacityPatch.Rewrite(UnitSortCapacityPatch.Target(fixture.MainModule))==1,"fixture transformed");Reject(()=>UnitSortCapacityPatch.Rewrite(UnitSortCapacityPatch.Target(fixture.MainModule)),"double application rejected");fixture.Write(a[1]);
  }
  for(int mode=0;mode<3;mode++)using(var x=AssemblyDefinition.ReadAssembly(a[0])){var m=UnitSortCapacityPatch.Target(x.MainModule);var ctor=m.Body.Instructions.Single(i=>i.OpCode==OpCodes.Newobj&&((MethodReference)i.Operand).DeclaringType.Name.StartsWith("SortedList"));if(mode==0)m.Body.InitLocals=false;if(mode==1)ctor.Previous.Previous.Previous.Operand="OtherTag";if(mode==2)m.Body.Instructions.Insert(m.Body.Instructions.IndexOf(ctor),Instruction.Create(OpCodes.Nop));Reject(()=>UnitSortCapacityPatch.Rewrite(m),"structural mutation rejected");}
  if(a.Length>2)using(var before=AssemblyDefinition.ReadAssembly(a[2],new ReaderParameters{AssemblyResolver=productionResolver})){
   using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var after=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=productionResolver})){Need(UnitSortCapacityPatch.Apply(after.MainModule)==1,"one production site");after.Write(a[4]);UnitSortCapacityPatch.Reverse(before,after);int m,i;AssemblyStructure.RequireSame(before,after,out m,out i);Need(true,"exact whole-assembly reversal");using(var restored=new MemoryStream()){after.Write(restored);restored.Position=0;using(var roundtrip=AssemblyDefinition.ReadAssembly(restored)){AssemblyStructure.RequireSame(before,roundtrip,out m,out i);Need(UnitSortCapacityPatch.Fingerprint(UnitSortCapacityPatch.Target(before.MainModule))==UnitSortCapacityPatch.Fingerprint(UnitSortCapacityPatch.Target(roundtrip.MainModule)),"serialized reversal retains exact scopes");}}}}
   for(int mode=0;mode<10;mode++)using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var x=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=productionResolver})){
    UnitSortCapacityPatch.Apply(x.MainModule);var m=UnitSortCapacityPatch.Target(x.MainModule);var ctor=m.Body.Instructions.Single(i=>i.OpCode==OpCodes.Newobj&&((MethodReference)i.Operand).DeclaringType.Name.StartsWith("SortedList"));
    if(mode==0)ctor.Previous.OpCode=OpCodes.Conv_U4;if(mode==1)m.Body.InitLocals=false;if(mode==2)x.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));if(mode==3)m.Body.ExceptionHandlers[0].FilterStart=m.Body.Instructions[0];if(mode==4)m.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
    if(mode==5){var c=(MethodReference)ctor.Operand;var old=(GenericInstanceType)c.DeclaringType;var wrong=new GenericInstanceType(new TypeReference(old.Namespace,old.Name,x.MainModule,x.MainModule.AssemblyReferences.Single(r=>r.Name=="mscorlib")));foreach(var p in old.GenericArguments)wrong.GenericArguments.Add(p);c.DeclaringType=wrong;}
    if(mode==6){var v=m.Body.Variables.Single(p=>p.VariableType.FullName=="UnityEngine.GameObject[]"&&p.Index==14);v.VariableType=new ArrayType(new TypeReference("UnityEngine","GameObject",x.MainModule,x.MainModule.AssemblyReferences.Single(r=>r.Name=="mscorlib")));}
    if(mode==7)((MethodReference)ctor.Operand).HasThis=false;if(mode==8)((MethodReference)ctor.Operand).ExplicitThis=true;if(mode==9)((MethodReference)ctor.Operand).CallingConvention=MethodCallingConvention.VarArg;
    Reject(()=>UnitSortCapacityPatch.Reverse(before,x),"tampered body/reference/EH rejected");
   }}
   var target=UnitSortCapacityPatch.Target(before.MainModule);target.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));Reject(()=>UnitSortCapacityPatch.Apply(before.MainModule),"unknown whole-method contract rejected");
  }
  Console.WriteLine("Unit capacity transform checks="+checks);
 }
}
