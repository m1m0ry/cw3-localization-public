using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
// Native macOS: honor the game's existing custom data path before its legacy
// Documents rename probe. A failed custom path must not silently reopen Documents.
internal static class CustomSavePathPatch {
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static MethodDefinition Method(ModuleDefinition m,string type,string name){return m.GetType(type).Methods.Single(x=>x.Name==name);}
 static bool Calls(Instruction i,string type,string name){var r=i.Operand as MethodReference;return i.OpCode==OpCodes.Call&&r!=null&&r.DeclaringType.FullName==type&&r.Name==name;}
 static FieldDefinition Field(ModuleDefinition m,string name){return m.GetType("GameSettings").Fields.Single(x=>x.Name==name);}
 static Instruction[] Prefix(ModuleDefinition m,MethodDefinition method,bool migrate){
  var il=method.Body.GetILProcessor();var first=method.Body.Instructions[0];var start=new[]{il.Create(OpCodes.Ldsfld,Field(m,"useCustomDataPath")),il.Create(OpCodes.Brfalse,first)};
  if(migrate)return start.Concat(new[]{il.Create(OpCodes.Ret)}).ToArray();
  var trim=(MethodReference)method.Body.Instructions.Single(x=>x.OpCode==OpCodes.Callvirt&&((MethodReference)x.Operand).Name=="Trim").Operand;
  var concat=(MethodReference)method.Body.Instructions.First(x=>Calls(x,"System.String","Concat")).Operand;
  var create=(MethodReference)method.Body.Instructions.First(x=>Calls(x,"System.IO.Directory","CreateDirectory")).Operand;
  return start.Concat(new[]{il.Create(OpCodes.Ldsfld,Field(m,"customDataPath")),il.Create(OpCodes.Callvirt,trim),il.Create(OpCodes.Ldstr,"/creeperworld3/"),il.Create(OpCodes.Call,concat),il.Create(OpCodes.Dup),il.Create(OpCodes.Call,create),il.Create(OpCodes.Pop),il.Create(OpCodes.Ret)}).ToArray();
 }
 internal static void Apply(ModuleDefinition m){
  var awake=Method(m,"SplashManager","Awake");var xs=awake.Body.Instructions;
  var migrate=xs.Single(x=>Calls(x,"FileManager","MigrateToLowerCase"));var read=xs.Single(x=>Calls(x,"GameSettings","Read"));
  Need(xs.IndexOf(read)>xs.IndexOf(migrate),"Expected original settings read after migration");
  var mm=Method(m,"FileManager","MigrateToLowerCase");Need(Calls(mm.Body.Instructions[0],"FileManager","GetDocumentsDir"),"Original Documents migration entry");
  var data=Method(m,"FileManager","GetBaseDataDir");Need(data.Body.Instructions[0].OpCode==OpCodes.Ldsfld,"Original custom data selector");
  foreach(var method in new[]{mm,data}){var prefix=Prefix(m,method,method==mm);var il=method.Body.GetILProcessor();var first=method.Body.Instructions[0];foreach(var i in prefix)il.InsertBefore(first,i);}
  xs.Remove(read);awake.Body.GetILProcessor().InsertBefore(migrate,read);
 }
 static string Operand(Instruction i){var x=i.Operand;var member=x as MemberReference;return member!=null?member.FullName:x==null?"":x.ToString();}
 internal static void Reverse(ModuleDefinition original,ModuleDefinition patched){
  foreach(string name in new[]{"MigrateToLowerCase","GetBaseDataDir"}){
   var om=Method(original,"FileManager",name);var nm=Method(patched,"FileManager",name);var expected=Prefix(original,om,name=="MigrateToLowerCase");var ys=nm.Body.Instructions;
   Need(ys.Count==om.Body.Instructions.Count+expected.Length,"Custom path instruction count");
   for(int n=0;n<expected.Length;n++){Need(ys[n].OpCode==expected[n].OpCode,"Custom path opcode");if(n==1)Need(ys[n].Operand==ys[expected.Length],"Custom path original branch");else Need(Operand(ys[n])==Operand(expected[n]),"Custom path operand");}
   for(int n=0;n<expected.Length;n++)ys.RemoveAt(0);
  }
  var oa=Method(original,"SplashManager","Awake");var pa=Method(patched,"SplashManager","Awake");var read=pa.Body.Instructions.Single(x=>Calls(x,"GameSettings","Read"));var migrate=pa.Body.Instructions.Single(x=>Calls(x,"FileManager","MigrateToLowerCase"));
  Need(read.Next==migrate,"Settings must precede legacy migration");pa.Body.Instructions.Remove(read);
  int oldIndex=oa.Body.Instructions.IndexOf(oa.Body.Instructions.Single(x=>Calls(x,"GameSettings","Read")));pa.Body.Instructions.Insert(oldIndex,read);
 }
}
