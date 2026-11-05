using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class PathWorkspaceContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static void Reject(Action action,string why){bool rejected=false;try{action();}catch(Exception){rejected=true;}Need(rejected,why);}
 static void Main(string[] a){
  using(var fixture=AssemblyDefinition.ReadAssembly(a[0])){var t=fixture.MainModule.GetType("CrplCore");PathWorkspacePatch.AddHelpers(fixture.MainModule,t);Reject(()=>PathWorkspacePatch.AddHelpers(fixture.MainModule,t),"duplicate helpers");fixture.Write(a[1]);}
  if(a.Length>2){var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(a[3]);using(var before=AssemblyDefinition.ReadAssembly(a[2],new ReaderParameters{AssemblyResolver=resolver})){
   using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var after=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=resolver})){Need(PathWorkspacePatch.Apply(after.MainModule)==3,"three scoring maps");after.Write(a[4]);PathWorkspacePatch.Reverse(before,after);int methods,instructions;AssemblyStructure.RequireSame(before,after,out methods,out instructions);Need(true,"exact reverse");}}
   for(int mode=0;mode<4;mode++)using(var bytes=new MemoryStream()){
    before.Write(bytes);bytes.Position=0;using(var changed=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=resolver})){
     PathWorkspacePatch.Apply(changed.MainModule);var body=PathWorkspacePatch.Target(changed.MainModule);
     if(mode==0)body.Body.InitLocals=false;
     if(mode==1)body.DeclaringType.Methods.Single(x=>x.Name=="__cw3PathBorrow").Body.InitLocals=false;
     if(mode==2)changed.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));
     if(mode==3)body.Body.ExceptionHandlers.Last().FilterStart=body.Body.Instructions[0];
     Reject(()=>PathWorkspacePatch.Reverse(before,changed),"tampered zero-init/reference/EH rejected");
    }
   }
   var m=PathWorkspacePatch.Target(before.MainModule);m.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));Reject(()=>PathWorkspacePatch.Apply(before.MainModule),"unknown body rejected");
  }}
  Console.WriteLine("Path workspace transform checks="+checks);
 }
}
