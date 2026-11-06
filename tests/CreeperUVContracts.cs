using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class CreeperUVContracts {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}static void Reject(Action action,string why){bool rejected=false;try{action();}catch(Exception){rejected=true;}Need(rejected,why);}
 static string Body(MethodDefinition m){return String.Join("\n",m.Body.Instructions.Select(i=>i.OpCode.Name+" "+(i.Operand is ParameterDefinition?"arg:"+((ParameterDefinition)i.Operand).Index:i.Operand==null?"":i.Operand.ToString())).ToArray());}
 static ReaderParameters Parameters(string directory){var r=new DefaultAssemblyResolver();r.AddSearchDirectory(directory);return new ReaderParameters{AssemblyResolver=r};}
 static void Main(string[]a){
  using(var x=AssemblyDefinition.ReadAssembly(a[0],Parameters(Path.GetDirectoryName(a[0])))){
   Reject(()=>CreeperUVPatch.Apply(x.MainModule),"synthetic fixture is not production");var m=CreeperUVPatch.Target(x.MainModule);Need(CreeperUVPatch.Rewrite(m)==1,"one helper rewritten");var oracle=m.DeclaringType.Methods.Single(v=>v.Name=="TestedLocal");Need(Body(m)==Body(oracle)&&m.Body.InitLocals==oracle.Body.InitLocals&&m.Body.Variables.Select(v=>v.VariableType.FullName).SequenceEqual(oracle.Body.Variables.Select(v=>v.VariableType.FullName)),"exact tested direct-write IL");Reject(()=>CreeperUVPatch.Rewrite(m),"double application");x.Write(a[1]);
  }
  for(int mode=0;mode<6;mode++)using(var x=AssemblyDefinition.ReadAssembly(a[0],Parameters(Path.GetDirectoryName(a[0])))){
   var m=CreeperUVPatch.Target(x.MainModule);var ctor=(MethodReference)m.Body.Instructions.First(i=>i.OpCode==OpCodes.Newobj).Operand;
   if(mode==0)m.Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
   if(mode==1)m.Body.InitLocals=false;
   if(mode==2)ctor.DeclaringType=new TypeReference("UnityEngine","Vector2",x.MainModule,x.MainModule.AssemblyReferences.Single(r=>r.Name=="mscorlib"),true);
   if(mode==3)ctor.Resolve().Body.Instructions[1].OpCode=OpCodes.Ldarg_2;
   if(mode==4)ctor.Resolve().DeclaringType.Fields.Add(new FieldDefinition("unexpected",FieldAttributes.Public,x.MainModule.TypeSystem.Single));
   if(mode==5){var cctor=new MethodDefinition(".cctor",MethodAttributes.Private|MethodAttributes.Static|MethodAttributes.SpecialName|MethodAttributes.RTSpecialName,x.MainModule.TypeSystem.Void);cctor.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));ctor.Resolve().DeclaringType.Methods.Add(cctor);}
   Reject(()=>CreeperUVPatch.Rewrite(m),"unknown method/constructor/scope/layout rejected");
  }
  if(a.Length>2)using(var before=AssemblyDefinition.ReadAssembly(a[2],Parameters(a[3]))){
   for(int mode=-1;mode<8;mode++)using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var after=AssemblyDefinition.ReadAssembly(bytes,Parameters(a[3]))){
    CreeperUVPatch.Apply(after.MainModule);var m=CreeperUVPatch.Target(after.MainModule);
    if(mode==-1){after.Write(a[4]);CreeperUVPatch.Reverse(before,after);int methods,instructions;AssemblyStructure.RequireSame(before,after,out methods,out instructions);Need(CreeperUVPatch.Fingerprint(CreeperUVPatch.Target(before.MainModule))==CreeperUVPatch.Fingerprint(m),"exact assembly and method reversal");continue;}
    if(mode==0)m.Body.Instructions[0].OpCode=OpCodes.Ldarg_0;
    if(mode==1)m.Body.InitLocals=false;
    if(mode==2)m.Body.Variables[0].VariableType=after.MainModule.TypeSystem.Double;
    if(mode==3)((FieldReference)m.Body.Instructions.First(i=>i.OpCode==OpCodes.Stfld).Operand).DeclaringType=new TypeReference("UnityEngine","Vector2",after.MainModule,after.MainModule.AssemblyReferences.Single(r=>r.Name=="mscorlib"),true);
    if(mode==4)after.MainModule.AssemblyReferences.Add(new AssemblyNameReference("Unexpected",new Version(1,0)));
    if(mode==5)m.DeclaringType.Methods.First(v=>v.HasBody&&v!=m).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));
    if(mode==6)m.DeclaringType.Fields.First(f=>f.FieldType.FullName=="System.Int32").FieldType=new TypeReference("System","Int32",after.MainModule,new AssemblyNameReference("Unexpected",new Version(1,0)),true);
    if(mode==7)((FieldReference)m.Body.Instructions.First(i=>i.OpCode==OpCodes.Stfld).Operand).Name="y";
    Reject(()=>CreeperUVPatch.Reverse(before,after),"unapproved method/local/field/scope/dependency change");
   }}
   CreeperUVPatch.Target(before.MainModule).Body.Instructions.Insert(0,Instruction.Create(OpCodes.Nop));Reject(()=>CreeperUVPatch.Apply(before.MainModule),"unknown complete production method");
  }
  Console.WriteLine("Creeper UV transform guards="+checks);
 }
}
