using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class PathDistanceContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}static void Reject(Action f,string why){bool yes=false;try{f();}catch(Exception){yes=true;}Need(yes,why);}
 static void Main(string[] a){
  using(var fixture=AssemblyDefinition.ReadAssembly(a[0])){
   Reject(()=>PathDistancePatch.Apply(fixture.MainModule),"fixture not production whitelist");Need(PathDistancePatch.Rewrite(PathDistancePatch.Target(fixture.MainModule))==3,"three repeated endpoint reads replaced");Reject(()=>PathDistancePatch.Rewrite(PathDistancePatch.Target(fixture.MainModule)),"double application rejected");fixture.Write(a[1]);
  }
  for(int mode=0;mode<4;mode++)using(var x=AssemblyDefinition.ReadAssembly(a[0])){
   var m=PathDistancePatch.Target(x.MainModule);var getters=m.Body.Instructions.Where(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).Name=="get_localPosition").ToArray();
   if(mode==0)m.Body.InitLocals=false;
   if(mode==1)getters[4].Previous.OpCode=OpCodes.Call;
   if(mode==2)getters[4].Previous.Previous.Operand=getters[5].Previous.Previous.Operand;
   if(mode==3)getters[4].Next.OpCode=OpCodes.Pop;
   Reject(()=>PathDistancePatch.Rewrite(m),"structural mutation rejected before rewrite");
  }
  if(a.Length>2){
   var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(a[3]);
   using(var before=AssemblyDefinition.ReadAssembly(a[2],new ReaderParameters{AssemblyResolver=resolver})){
    using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var after=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=resolver})){
     Need(PathDistancePatch.Apply(after.MainModule)==3,"three production sites");after.Write(a[4]);PathDistancePatch.Reverse(before,after);int m,i;AssemblyStructure.RequireSame(before,after,out m,out i);Need(true,"exact full assembly reversal");
     using(var restored=new MemoryStream()){after.Write(restored);restored.Position=0;using(var roundtrip=AssemblyDefinition.ReadAssembly(restored)){AssemblyStructure.RequireSame(before,roundtrip,out m,out i);Need(PathDistancePatch.Fingerprint(PathDistancePatch.Target(before.MainModule))==PathDistancePatch.Fingerprint(PathDistancePatch.Target(roundtrip.MainModule)),"serialized reversal preserves scopes and locals");}}
    }}
    for(int mode=0;mode<8;mode++)using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var x=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=resolver})){
     PathDistancePatch.Apply(x.MainModule);var m=PathDistancePatch.Target(x.MainModule);var load=m.Body.Instructions.First(i=>i.OpCode==OpCodes.Ldloc);
     if(mode==0)load.Operand=m.Body.Variables[0];
     if(mode==1)load.Next.OpCode=OpCodes.Dup;
     if(mode==2)m.Body.InitLocals=false;
     if(mode==3)x.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));
     if(mode==4)m.Body.Instructions.First(i=>i.Operand is Instruction).Operand=load.Next;
     if(mode==5)m.Body.Variables[2].VariableType=new TypeReference("UnityEngine","Vector3",x.MainModule,x.MainModule.AssemblyReferences.Single(r=>r.Name=="mscorlib"));
     if(mode==6)((MethodReference)m.Body.Instructions.First(i=>i.Operand is MethodReference).Operand).HasThis=false;
     if(mode==7)x.MainModule.GetType("Path").Methods.First(v=>v.HasBody&&v!=m).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
     Reject(()=>PathDistancePatch.Reverse(before,x),"unapproved IL/local/reference/other-method mutation rejected");
    }}
    var original=PathDistancePatch.Target(before.MainModule);original.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));Reject(()=>PathDistancePatch.Apply(before.MainModule),"unknown whole-method contract rejected");
   }
  }
  Console.WriteLine("Path distance transform checks="+checks);
 }
}
