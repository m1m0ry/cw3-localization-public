using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;

// Native Mac: use dynamic buffers for the mesh whose UVs change every simulation step.
// Hint only at section initialization, after the actual per-section mesh clone exists.
internal static class CreeperDynamicPatch {
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
 internal static MethodDefinition Target(ModuleDefinition module){return module.GetType("CreeperSimulation").Methods.Single(m=>m.Name=="Start");}
 internal static int Apply(ModuleDefinition module){var method=Target(module);string hash=Fingerprint(method);Need(hash=="f13abbc6fe51cc826087a3e96a2b602e70ed3c2f2da58b77cd7b5c89cad17799","Unsupported Creeper Start layout: "+hash);return Rewrite(method);}
 static Instruction Getter(MethodDefinition method){
  Need(method.HasThis&&method.Parameters.Count==0&&method.ReturnType.FullName=="System.Void"&&method.Body.ExceptionHandlers.Count==0,"Unexpected section initialization signature");
  var fields=method.Body.Instructions.Where(i=>i.OpCode==OpCodes.Ldfld&&i.Operand is FieldReference&&((FieldReference)i.Operand).Name=="sectionMeshes").ToArray();Need(fields.Length==1,"Expected unique creeper mesh array store");
  var field=(FieldReference)fields[0].Operand;var array=field.FieldType as ArrayType;Need(field.DeclaringType.FullName=="CreeperSimulation"&&array!=null&&array.ElementType.FullName=="UnityEngine.Mesh"&&array.ElementType.Scope.Name=="UnityEngine","Expected game-owned Creeper mesh array");
  Instruction getter=null;for(var i=fields[0].Next;i!=null&&i.OpCode!=OpCodes.Stelem_Ref;i=i.Next){var call=i.Operand as MethodReference;if(call!=null&&call.Name=="get_mesh"){Need(getter==null,"Multiple mesh getters before store");getter=i;}}
  var m=getter==null?null:getter.Operand as MethodReference;Need(m!=null&&getter.OpCode==OpCodes.Callvirt&&m.FullName=="UnityEngine.Mesh UnityEngine.MeshFilter::get_mesh()"&&m.DeclaringType.Scope.Name=="UnityEngine"&&m.HasThis&&m.Parameters.Count==0&&getter.Next.OpCode==OpCodes.Stelem_Ref,"Expected exact per-section mesh getter/store");return getter;
 }
 internal static int Rewrite(MethodDefinition method){var getter=Getter(method);var mesh=((MethodReference)getter.Operand).ReturnType;var mark=new MethodReference("MarkDynamic",method.Module.TypeSystem.Void,mesh){HasThis=true};var il=method.Body.GetILProcessor();var dup=il.Create(OpCodes.Dup);il.InsertAfter(getter,dup);il.InsertAfter(dup,il.Create(OpCodes.Callvirt,mark));method.Body.MaxStackSize++;return 1;}
 internal static int Reverse(AssemblyDefinition before,AssemblyDefinition after){
  Need(before.MainModule.AssemblyReferences.Select(r=>r.FullName).SequenceEqual(after.MainModule.AssemblyReferences.Select(r=>r.FullName)),"Assembly dependencies changed");
  using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(bytes)){Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,after,out methods,out instructions);
   var a=expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);var b=after.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);Need(a.SequenceEqual(b),"Method scope/initialization/exception contract changed");}}
  var source=Target(before.MainModule);var method=Target(after.MainModule);int index=source.Body.Instructions.IndexOf(Getter(source));var getter=method.Body.Instructions[index];var il=method.Body.GetILProcessor();il.Remove(getter.Next.Next);il.Remove(getter.Next);method.Body.MaxStackSize=source.Body.MaxStackSize;return 1;
 }
}
