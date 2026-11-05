using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class CreeperDynamicContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}static void Reject(Action f,string why){bool rejected=false;try{f();}catch(Exception){rejected=true;}Need(rejected,why);}
 static void Main(string[]a){using(var x=AssemblyDefinition.ReadAssembly(a[0])){Reject(()=>CreeperDynamicPatch.Apply(x.MainModule),"fixture not production");Need(CreeperDynamicPatch.Rewrite(CreeperDynamicPatch.Target(x.MainModule))==1,"one initialization site");Reject(()=>CreeperDynamicPatch.Rewrite(CreeperDynamicPatch.Target(x.MainModule)),"double application");x.Write(a[1]);}
  if(a.Length>2){var r=new DefaultAssemblyResolver();r.AddSearchDirectory(a[3]);using(var before=AssemblyDefinition.ReadAssembly(a[2],new ReaderParameters{AssemblyResolver=r})){
   for(int mode=-1;mode<7;mode++)using(var s=new MemoryStream()){before.Write(s);s.Position=0;using(var after=AssemblyDefinition.ReadAssembly(s,new ReaderParameters{AssemblyResolver=r})){CreeperDynamicPatch.Apply(after.MainModule);var m=CreeperDynamicPatch.Target(after.MainModule);var hint=m.Body.Instructions.Single(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).Name=="MarkDynamic");
    if(mode==-1){after.Write(a[4]);CreeperDynamicPatch.Reverse(before,after);int methods,instructions;AssemblyStructure.RequireSame(before,after,out methods,out instructions);Need(true,"exact assembly reversal");continue;}
    if(mode==0)hint.OpCode=OpCodes.Call;
    if(mode==1)hint.Previous.OpCode=OpCodes.Pop;
    if(mode==2)((MethodReference)hint.Operand).DeclaringType=new TypeReference("UnityEngine","Mesh",after.MainModule,after.MainModule.AssemblyReferences.Single(x=>x.Name=="mscorlib"));
    if(mode==3)m.Body.InitLocals=!m.Body.InitLocals;
    if(mode==4)after.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));
    if(mode==5)m.Body.Instructions.First(i=>i.Operand is Instruction).Operand=hint;
    if(mode==6)after.MainModule.GetType("CreeperSimulation").Methods.First(x=>x.HasBody&&x!=m).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
    Reject(()=>CreeperDynamicPatch.Reverse(before,after),"unapproved method/scope/branch change");}}
   CreeperDynamicPatch.Target(before.MainModule).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));Reject(()=>CreeperDynamicPatch.Apply(before.MainModule),"unknown original layout");}}
  Console.WriteLine("Creeper dynamic patch guards="+checks);
 }
}
