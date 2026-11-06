using System;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;

// Native Mac's old Mono copies four temporary Vector2 values in this hot helper.
// Keep all cells, float operations and upload calls; only write the same x/y fields
// directly and reuse right/top within this one call. Native full-UV comparison,
// including owned Mesh uploads, measured 4.051 -> 3.067 ms on a 256x256 heavy map.
// Windows is not enabled without its own JIT evidence. Revoke if bit/partial-write
// parity or the pinned Vector2 constructor/layout no longer holds.
internal static class CreeperUVPatch {
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
 internal static MethodDefinition Target(ModuleDefinition m){return m.GetType("CreeperSimulation").Methods.Single(x=>x.Name=="setUVs");}
 internal static int Apply(ModuleDefinition module){
  var m=Target(module);var hash=Fingerprint(m);
  Need(hash=="e69a585975afd3eec0c6b68896d4ebd1fd330f951b599a0225b5bd3c5065622d","Unsupported Creeper setUVs layout: "+hash);
  Vector(m,true);return Rewrite(m);
 }
 static MethodReference Vector(MethodDefinition m,bool production){
  var calls=m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Newobj).Select(i=>i.Operand as MethodReference).ToArray();
  Need(calls.Length==4&&calls.All(x=>x!=null&&x.FullName=="System.Void UnityEngine.Vector2::.ctor(System.Single,System.Single)"&&x.HasThis&&!x.ExplicitThis&&x.CallingConvention==MethodCallingConvention.Default&&x.GenericParameters.Count==0),"Expected four original Vector2 constructors");
  var ctor=calls[0];var reference=ctor.DeclaringType.Scope as AssemblyNameReference;
  Need(reference!=null&&reference.Name=="UnityEngine"&&calls.All(x=>Scope(x.DeclaringType)==Scope(ctor.DeclaringType)),"Unexpected Vector2 constructor scope");
  var definition=ctor.Resolve();var vector=definition.DeclaringType;
  Need(reference.FullName==vector.Module.Assembly.Name.FullName&&vector.FullName=="UnityEngine.Vector2"&&vector.IsPublic&&vector.IsValueType&&vector.IsSequentialLayout&&vector.PackingSize==-1&&vector.ClassSize==-1,"Unexpected resolved Vector2 identity/layout");
  Need(!vector.Methods.Any(v=>v.IsConstructor&&v.IsStatic),"Unexpected Vector2 static initializer");
  var fields=vector.Fields.Where(f=>!f.IsStatic).ToArray();
  Need(fields.Length==2&&fields[0].Name=="x"&&fields[1].Name=="y"&&fields.All(f=>f.IsPublic&&!f.IsInitOnly&&f.FieldType.FullName=="System.Single"),"Unexpected Vector2 fields");
  Need(definition.HasBody&&definition.Body.Variables.Count==0&&definition.Body.ExceptionHandlers.Count==0&&!definition.Body.InitLocals,"Unexpected Vector2 constructor body");
  var xs=definition.Body.Instructions;var codes=new[]{OpCodes.Ldarg_0,OpCodes.Ldarg_1,OpCodes.Stfld,OpCodes.Ldarg_0,OpCodes.Ldarg_2,OpCodes.Stfld,OpCodes.Ret};
  Need(xs.Select(i=>i.OpCode).SequenceEqual(codes)&&((FieldReference)xs[2].Operand).Resolve()==fields[0]&&((FieldReference)xs[5].Operand).Resolve()==fields[1],"Vector2 constructor must only assign x then y");
  if(production)Need(Fingerprint(definition)=="38aeba8b62752627eab7e774b7ddce2459e1011a0be5bee070e56070223cc48c","Unsupported real Vector2 constructor fingerprint");
  var array=m.Parameters[1].ParameterType as ArrayType;
  Need(array!=null&&array.IsVector&&Scope(array.ElementType)==Scope(ctor.DeclaringType),"Vector2 array/constructor scope mismatch");return ctor;
 }
 static MethodBody OriginalBody(MethodDefinition m,MethodReference ctor){
  var body=new MethodBody(m){InitLocals=true};var il=body.GetILProcessor();
  for(int n=0;n<4;n++){
   il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldarg_0));
   if(n>0){il.Append(il.Create(n==1?OpCodes.Ldc_I4_1:n==2?OpCodes.Ldc_I4_2:OpCodes.Ldc_I4_3));il.Append(il.Create(OpCodes.Add));}
   il.Append(il.Create(OpCodes.Ldelema,ctor.DeclaringType));il.Append(il.Create(OpCodes.Ldarg_2));
   if(n==1||n==2){il.Append(il.Create(OpCodes.Ldarg_S,m.Parameters[4]));il.Append(il.Create(OpCodes.Add));}
   il.Append(il.Create(OpCodes.Ldarg_3));
   if(n==2||n==3){il.Append(il.Create(OpCodes.Ldarg_S,m.Parameters[5]));il.Append(il.Create(OpCodes.Add));}
   il.Append(il.Create(OpCodes.Newobj,ctor));il.Append(il.Create(OpCodes.Stobj,ctor.DeclaringType));
  }
  il.Append(il.Create(OpCodes.Ret));return body;
 }
 // Structural entry point for the isolated fixture. Apply also pins both complete
 // real method fingerprints, including signatures, scopes, locals, and EH.
 internal static int Rewrite(MethodDefinition m){
  Need(m.IsStatic&&!m.HasThis&&m.ReturnType.FullName=="System.Void"&&m.Parameters.Count==6&&m.Parameters[0].ParameterType.FullName=="System.Int32"&&m.Parameters.Skip(2).All(p=>p.ParameterType.FullName=="System.Single")&&m.Body.InitLocals&&m.Body.Variables.Count==0&&m.Body.ExceptionHandlers.Count==0,"Unexpected setUVs signature/body");
  var ctor=Vector(m,false);var source=m.Body;string actual=Fingerprint(m);string expected;
  try{m.Body=OriginalBody(m,ctor);expected=Fingerprint(m);}finally{m.Body=source;}
  Need(actual==expected,"Unexpected original UV write order or arithmetic");
  var vector=ctor.DeclaringType;var x=new FieldReference("x",m.Module.TypeSystem.Single,vector);var y=new FieldReference("y",m.Module.TypeSystem.Single,vector);
  m.Body=new MethodBody(m){InitLocals=true,MaxStackSize=3};m.Body.Variables.Add(new VariableDefinition(m.Module.TypeSystem.Single));m.Body.Variables.Add(new VariableDefinition(m.Module.TypeSystem.Single));var il=m.Body.GetILProcessor();
  // These are the exact opcodes of the tested SetUVsLocal, including repeated
  // ldelema checks. Do not combine pointers or move any array access earlier.
  Action<int,FieldReference,OpCode> store=(offset,field,value)=>{
   il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldarg_0));
   if(offset>0){il.Append(il.Create(offset==1?OpCodes.Ldc_I4_1:offset==2?OpCodes.Ldc_I4_2:OpCodes.Ldc_I4_3));il.Append(il.Create(OpCodes.Add));}
   il.Append(il.Create(OpCodes.Ldelema,vector));il.Append(il.Create(value));il.Append(il.Create(OpCodes.Stfld,field));
  };
  store(0,x,OpCodes.Ldarg_2);store(0,y,OpCodes.Ldarg_3);
  il.Append(il.Create(OpCodes.Ldarg_2));il.Append(il.Create(OpCodes.Ldarg_S,m.Parameters[4]));il.Append(il.Create(OpCodes.Add));il.Append(il.Create(OpCodes.Stloc_0));
  store(1,x,OpCodes.Ldloc_0);store(1,y,OpCodes.Ldarg_3);
  il.Append(il.Create(OpCodes.Ldarg_3));il.Append(il.Create(OpCodes.Ldarg_S,m.Parameters[5]));il.Append(il.Create(OpCodes.Add));il.Append(il.Create(OpCodes.Stloc_1));
  store(2,x,OpCodes.Ldloc_0);store(2,y,OpCodes.Ldloc_1);store(3,x,OpCodes.Ldarg_2);store(3,y,OpCodes.Ldloc_1);il.Append(il.Create(OpCodes.Ret));return 1;
 }
 static string[] DeclaredScopes(AssemblyDefinition assembly){return assembly.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>new[]{t.FullName+":"+Scope(t.BaseType)}.Concat(t.Fields.Select(f=>f.FullName+":"+Scope(f.FieldType))).Concat(t.Methods.Select(m=>m.FullName+":"+OperandScope(m)))).ToArray();}
 internal static int Reverse(AssemblyDefinition before,AssemblyDefinition after){
  Need(before.MainModule.AssemblyReferences.Select(r=>r.FullName).SequenceEqual(after.MainModule.AssemblyReferences.Select(r=>r.FullName)),"Assembly dependencies changed");
  Need(DeclaredScopes(before).SequenceEqual(DeclaredScopes(after)),"Declared type/member scopes changed");
  using(var bytes=new MemoryStream()){before.Write(bytes);bytes.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(bytes,new ReaderParameters{AssemblyResolver=before.MainModule.AssemblyResolver})){
   Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,after,out methods,out instructions);
   Need(expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint).SequenceEqual(after.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint)),"Method scope/initialization/exception contract changed");
  }}
  var source=Target(before.MainModule);var target=Target(after.MainModule);var ctor=(MethodReference)source.Body.Instructions.First(i=>i.OpCode==OpCodes.Newobj).Operand;
  target.Body=OriginalBody(target,after.MainModule.ImportReference(ctor));target.Body.InitLocals=source.Body.InitLocals;target.Body.MaxStackSize=source.Body.MaxStackSize;return 1;
 }
}
