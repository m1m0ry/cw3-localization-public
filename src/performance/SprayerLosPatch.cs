using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;

// Same-call Sprayer LOS subsumption, not target caching. If only Creeper can
// improve and its elevation penalty is zero, the Creeper-blocking ray already
// includes the ordinary wall/height test. Keep Digitalis's independent result.
// Native Mac full-query ABBA: eight live Sprayers averaged 1.011 -> 0.411 ms.
// Preserve target ordering, float operations, simulation and the 30-FPS target.
internal static class SprayerLosPatch {
 static string Scope(TypeReference t){
  if(t==null)return "null";var g=t as GenericInstanceType;if(g!=null)return Scope(g.ElementType)+"<"+String.Join(",",g.GenericArguments.Select(Scope).ToArray())+">";
  var shape=t as TypeSpecification;if(shape!=null)return t.FullName+"@"+Scope(shape.ElementType);
  return t.FullName+"@"+(t.Scope==null?"none":t.Scope.ToString());
 }
 static string OperandScope(object o){
  var method=o as MethodReference;if(method!=null)return "this="+method.HasThis+",explicit="+method.ExplicitThis+",calling="+method.CallingConvention+",arity="+method.GenericParameters.Count+":"+Scope(method.DeclaringType)+":"+Scope(method.ReturnType)+"("+String.Join(",",method.Parameters.Select(p=>Scope(p.ParameterType)).ToArray())+")"+(method is GenericInstanceMethod?String.Join(",",((GenericInstanceMethod)method).GenericArguments.Select(Scope).ToArray()):"");
  var field=o as FieldReference;if(field!=null)return Scope(field.DeclaringType)+":"+Scope(field.FieldType);
  var type=o as TypeReference;if(type!=null)return Scope(type);return "";
 }
 internal static string Fingerprint(MethodDefinition m){
  var xs=m.Body.Instructions;Func<Instruction,string> at=i=>i==null?"end":xs.IndexOf(i).ToString();
  var lines=new[]{m.FullName,"signature:"+OperandScope(m),"init:"+m.Body.InitLocals}.Concat(m.Body.Variables.Select(v=>Scope(v.VariableType))).Concat(xs.Select(i=>{
   string op=i.OpCode.Name;if(op.EndsWith(".s")&&i.Operand is Instruction)op=op.Substring(0,op.Length-2);
   string value=i.Operand is Instruction?"target:"+at((Instruction)i.Operand):i.Operand is Instruction[]?String.Join(",",((Instruction[])i.Operand).Select(at).ToArray()):i.Operand==null?"":i.Operand.ToString();return op+" "+value+" scopes:"+OperandScope(i.Operand);
  })).Concat(m.Body.ExceptionHandlers.Select(h=>h.HandlerType+":"+at(h.TryStart)+":"+at(h.TryEnd)+":"+at(h.HandlerStart)+":"+at(h.HandlerEnd)+":"+at(h.FilterStart)+":"+Scope(h.CatchType)));
  using(var sha=System.Security.Cryptography.SHA256.Create())return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(String.Join("\n",lines.ToArray())))).Replace("-","").ToLowerInvariant();
 }

 static void Need(bool ok,string why){if(!ok)throw new Exception(why);}
 internal static MethodDefinition Target(ModuleDefinition m){return m.GetType("SprayerBarrelManager").Methods.Single(x=>x.Name=="FindNearestEnemies");}
 static MethodDefinition Los(ModuleDefinition m,int count){return m.GetType("Util").Methods.Single(x=>x.Name=="hasLOS"&&x.Parameters.Count==count);}
 internal static void RequireOriginal(ModuleDefinition module){
  var methods=new[]{Target(module),Los(module,6),Los(module,7),Los(module,9),module.GetType("Util").Methods.Single(m=>m.Name=="heightOK")};
  var hashes=new[]{"a74c11929f21f7c65b38fb302ec0eefe8b6303d7d168238c5063adbe57d43a64","c57bbf0a5fbf2858fb37263e458803e0a7f5217d88e9c15e0eacea9d1856faf9","9a3455b7c0e8590f31fac17bd31d2e43f3f20d7ba308e95b6558afc207ae4023","1ae8de1c4220107e3317cf0e8769c49d3382ad35fa87f9519a1729e003f5e4dd","ad697add22822c968ce5edc3636c689983f8d5257d03ec75be07f702a8991b68"};
  for(int n=0;n<methods.Length;n++)Need(Fingerprint(methods[n])==hashes[n],"Unsupported Sprayer LOS contract: "+methods[n].FullName+" "+Fingerprint(methods[n]));
 }
 static Instruction Call(MethodDefinition m,int count){return m.Body.Instructions.Single(i=>i.OpCode==OpCodes.Call&&i.Operand is MethodReference&&((MethodReference)i.Operand).DeclaringType.FullName=="Util"&&((MethodReference)i.Operand).Name=="hasLOS"&&((MethodReference)i.Operand).Parameters.Count==count);}
 static Instruction Before(Instruction i,int count){while(count-->0)i=i.Previous;return i;}
 internal static int Apply(ModuleDefinition module){
  RequireOriginal(module);var m=Target(module);var firstCall=Call(m,6);var secondCall=Call(m,9);var first=Before(firstCall,6);var second=Before(secondCall,9);var accept=secondCall.Next.Next;
  Need(m.HasThis&&!m.IsStatic&&m.ReturnType.FullName=="System.Void"&&m.Parameters.Count==8&&m.Body.InitLocals&&m.Body.Variables.Count==17&&m.Body.ExceptionHandlers.Count==0,"Unexpected Sprayer query signature/locals");
  Need(first.OpCode==OpCodes.Ldarg_1&&second.OpCode==OpCodes.Ldarg_1&&secondCall.Next.OpCode==OpCodes.Brfalse&&!m.Body.Instructions.Any(i=>i.Operand==second),"Unexpected LOS argument/control-flow boundary");
  var il=m.Body.GetILProcessor();var flag=new VariableDefinition(module.TypeSystem.Boolean);m.Body.Variables.Add(flag);
  // Exact predicate from the measured prototype. Zero is the numeric penalty,
  // not a terrain-equality shortcut (range 3 can also give a zero penalty).
  var guard=new[]{il.Create(OpCodes.Ldloc,m.Body.Variables[4]),il.Create(OpCodes.Ldc_R4,0f),il.Create(OpCodes.Ceq),
   il.Create(OpCodes.Ldloc,m.Body.Variables[16]),il.Create(OpCodes.Ldc_I4_0),il.Create(OpCodes.Cgt),
   il.Create(OpCodes.Ldloc,m.Body.Variables[3]),il.Create(OpCodes.Conv_R4),il.Create(OpCodes.Ldloc,m.Body.Variables[6]),il.Create(OpCodes.Clt),
   il.Create(OpCodes.And),il.Create(OpCodes.Ldc_I4_0),il.Create(OpCodes.Ceq),il.Create(OpCodes.And),il.Create(OpCodes.Stloc,flag)};
  foreach(var i in guard)il.InsertBefore(first,i);foreach(var i in m.Body.Instructions)if(i.Operand==first)i.Operand=guard[0];
  // Existing ignoreElevation/strictElevation remain false. Append the original
  // onlySuperWalls/alsoInspectFauxElevation defaults and the creeperblocks flag.
  il.InsertBefore(firstCall,il.Create(OpCodes.Ldc_I4_0));il.InsertBefore(firstCall,il.Create(OpCodes.Ldc_I4_0));il.InsertBefore(firstCall,il.Create(OpCodes.Ldloc,flag));firstCall.Operand=secondCall.Operand;
  il.InsertBefore(second,il.Create(OpCodes.Ldloc,flag));il.InsertBefore(second,il.Create(OpCodes.Brtrue,accept));
  return 1;
 }
 static string[] DeclaredScopes(AssemblyDefinition assembly){return assembly.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>new[]{t.FullName+":"+Scope(t.BaseType)}.Concat(t.Fields.Select(f=>f.FullName+":"+Scope(f.FieldType))).Concat(t.Methods.Select(m=>m.FullName+":"+OperandScope(m)))).ToArray();}
 internal static int Reverse(AssemblyDefinition before,AssemblyDefinition after){
  Need(before.MainModule.AssemblyReferences.Select(r=>r.FullName).SequenceEqual(after.MainModule.AssemblyReferences.Select(r=>r.FullName)),"Assembly dependencies changed");
  Need(DeclaredScopes(before).SequenceEqual(DeclaredScopes(after)),"Declared type/member scopes changed");
  using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=before.MainModule.AssemblyResolver})){
   Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,after,out methods,out instructions);
   Need(expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint).SequenceEqual(after.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint)),"Method scope/initialization/exception contract changed");
  }}
  var source=Target(before.MainModule);var target=Target(after.MainModule);var xs=target.Body.Instructions;
  int index=source.Body.Instructions.IndexOf(Before(Call(source,6),6));var guard=xs[index];var originalFirst=xs[index+15];foreach(var i in xs)if(i.Operand==guard)i.Operand=originalFirst;
  for(int n=0;n<15;n++)xs.RemoveAt(index);
  var firstCall=xs.First(i=>i.OpCode==OpCodes.Call&&i.Operand is MethodReference&&((MethodReference)i.Operand).Name=="hasLOS");
  for(int n=0;n<3;n++)xs.Remove(firstCall.Previous);firstCall.Operand=Los(after.MainModule,6);
  var second=Before(Call(target,9),9);xs.Remove(second.Previous);xs.Remove(second.Previous);
  target.Body.Variables.RemoveAt(17);target.Body.InitLocals=source.Body.InitLocals;target.Body.MaxStackSize=source.Body.MaxStackSize;return 1;
 }
}
