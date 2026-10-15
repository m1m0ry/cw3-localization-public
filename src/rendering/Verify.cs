using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;
class Verify {
 static void Require(bool b,string msg){if(!b)throw new Exception(msg);}
 static void Main(string[] a){
  var old=AssemblyDefinition.ReadAssembly(a[0]);var patch=AssemblyDefinition.ReadAssembly(a[1]);int methods=0,instructions=0;
  foreach(string name in new[]{"UILabel","UISprite","UITexture","UIDrawCall"}){var method=patch.MainModule.GetType(name).Methods.Single(x=>x.Name==(name=="UIDrawCall"?"OnWillRenderObject":"get_material"));var ins=method.Body.Instructions;int found=0;for(int k=0;k<ins.Count-2;k++){var mr=ins[k+1].Operand as MethodReference;if(ins[k].OpCode==OpCodes.Ldarg_0&&ins[k+1].OpCode==OpCodes.Call&&mr!=null&&mr.DeclaringType.FullName=="CW3Rendering"&&mr.Name==(name=="UIDrawCall"?"SyncDrawCall":"Ordered")&&ins[k+2].OpCode==OpCodes.Ret){ins[k].OpCode=OpCodes.Ret;ins[k].Operand=null;ins.RemoveAt(k+2);ins.RemoveAt(k+1);found++;}}Require(found>0,"missing render wrapper");}
  var shield=patch.MainModule.GetType("SystemManager").Methods.Single(x=>x.Name=="ShowStorySystemMessageForPlanet");var names=patch.MainModule.GetType("PlanetManager").Methods.Single(x=>x.Name=="get_planetName");int fixedNames=0;foreach(var i in shield.Body.Instructions){var mr=i.Operand as MethodReference;if(mr!=null&&mr.DeclaringType.Name=="GalObjectManager"&&mr.Name=="get_GUID"){i.Operand=names;fixedNames++;}}Require(fixedNames==12,"shield dispatch count");
  AssemblyStructure.RequireSame(old,patch,out methods,out instructions);
  Console.WriteLine("PASS: original types, field order, method signatures, "+methods+" methods and "+instructions+" IL instructions unchanged after reversing exact rendering wrappers, 12 GUID dispatches.");
 }
}
