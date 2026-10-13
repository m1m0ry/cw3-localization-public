using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
// Only Unity observation getters are replaced. No Unity player is loaded.
class ScriptOutputEngine {
 static void Main(string[] args){using(var assembly=AssemblyDefinition.ReadAssembly(args[0])){
  foreach(string name in new[]{"get_frameCount","get_loadedLevelName","get_dataPath"}){
   bool time=name=="get_frameCount";var method=assembly.MainModule.GetType(time?"UnityEngine.Time":"UnityEngine.Application").Methods.Single(m=>m.Name==name);
   if(!method.IsInternalCall)throw new Exception("Expected native observation boundary");
   method.ImplAttributes=MethodImplAttributes.IL|MethodImplAttributes.Managed;method.Body=new MethodBody(method);
   var il=method.Body.GetILProcessor();il.Append(time?il.Create(OpCodes.Ldc_I4,1):il.Create(OpCodes.Ldstr,name=="get_dataPath"?"/unused-fixture":"Game"));il.Append(il.Create(OpCodes.Ret));
  }assembly.Write(args[1]);
 }}
}
