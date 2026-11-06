using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class SprayerLosContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static void Reject(Action action,string why){bool rejected=false;try{action();}catch(Exception){rejected=true;}Need(rejected,why);}
 static AssemblyDefinition Copy(AssemblyDefinition source){var bytes=new MemoryStream();source.Write(bytes);bytes.Position=0;return AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=source.MainModule.AssemblyResolver});}
 static void Main(string[]a){var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(a[2]);using(var before=AssemblyDefinition.ReadAssembly(a[0],new ReaderParameters{AssemblyResolver=resolver})){
  using(var after=Copy(before)){
   Need(SprayerLosPatch.Apply(after.MainModule)==1,"one query changed");after.Write(a[1]);Reject(()=>SprayerLosPatch.Apply(after.MainModule),"double application rejected");
   Need(SprayerLosPatch.Reverse(before,after)==1,"one query reversed");int m,i;AssemblyStructure.RequireSame(before,after,out m,out i);
   Need(SprayerLosPatch.Fingerprint(SprayerLosPatch.Target(before.MainModule))==SprayerLosPatch.Fingerprint(SprayerLosPatch.Target(after.MainModule)),"exact original query restored");
   using(var roundtrip=Copy(after)){AssemblyStructure.RequireSame(before,roundtrip,out m,out i);Need(SprayerLosPatch.Fingerprint(SprayerLosPatch.Target(before.MainModule))==SprayerLosPatch.Fingerprint(SprayerLosPatch.Target(roundtrip.MainModule)),"serialized restoration");}
  }
  for(int mode=0;mode<7;mode++)using(var changed=Copy(before)){
   var m=SprayerLosPatch.Target(changed.MainModule);var los=changed.MainModule.GetType("Util").Methods.Single(x=>x.Name=="hasLOS"&&x.Parameters.Count==(mode==4?6:9));
   if(mode==0)m.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   if(mode==1)m.Body.InitLocals=false;
   if(mode==2)m.Body.Variables[4].VariableType=changed.MainModule.TypeSystem.Double;
   if(mode==3)m.Body.Instructions.First(x=>x.OpCode==OpCodes.Bge_Un).OpCode=OpCodes.Bgt_Un;
   if(mode==4||mode==5)los.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   if(mode==6)changed.MainModule.GetType("Util").Methods.Single(x=>x.Name=="heightOK").Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   Reject(()=>SprayerLosPatch.Apply(changed.MainModule),"unknown query or read-only LOS dependency rejected");Need(m.Body.Variables.Count==17,"failed guard did not add locals");
  }
  for(int mode=0;mode<10;mode++)using(var changed=Copy(before)){
   SprayerLosPatch.Apply(changed.MainModule);var m=SprayerLosPatch.Target(changed.MainModule);var xs=m.Body.Instructions;var call=xs.First(x=>x.Operand is MethodReference&&((MethodReference)x.Operand).Name=="hasLOS");
   if(mode==0)xs.First(x=>x.OpCode==OpCodes.Ceq).OpCode=OpCodes.Cgt;
   if(mode==1)call.Previous.OpCode=OpCodes.Ldc_I4_1;
   if(mode==2)m.Body.InitLocals=false;
   if(mode==3)m.Body.Variables[17].VariableType=changed.MainModule.TypeSystem.Int32;
   if(mode==4)xs.First(x=>x.OpCode==OpCodes.Brtrue).Operand=call;
   if(mode==5)((MethodReference)call.Operand).HasThis=true;
   if(mode==6)changed.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));
   if(mode==7)m.DeclaringType.Methods.First(x=>x.HasBody&&x!=m).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   if(mode==8)changed.MainModule.GetType("Util").Methods.Single(x=>x.Name=="heightOK").Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   if(mode==9)m.DeclaringType.Fields.First().FieldType=new TypeReference("System","Int32",changed.MainModule,new AssemblyNameReference("Unexpected",new Version(1,0)),true);
   Reject(()=>SprayerLosPatch.Reverse(before,changed),"unapproved predicate/flag/control-flow/local/scope/dependency change rejected");
  }
 }Console.WriteLine("Sprayer LOS transform guards="+checks);}
}
