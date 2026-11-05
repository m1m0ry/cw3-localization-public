using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Path distance is evaluated repeatedly during packet routing. Unity transform
// getters cross into native code; x/y of each endpoint use the same position.
// Reuse only the first Vector3 local in this call. No graph or cross-call cache.
internal static class PathDistancePatch {
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
 internal static MethodDefinition Target(ModuleDefinition m){return m.GetType("Path").Methods.Single(x=>x.Name=="GetDistance");}
 internal static int Apply(ModuleDefinition module){
  var m=Target(module);var hash=Fingerprint(m);
  Need(hash=="654b16dd40840050db60eb9bbbe39d1e0a0a5213a8e564f244237f56f0513b3e","Unsupported path-distance method layout: "+hash);
  return Rewrite(m);
 }
 static VariableDefinition StoredLocal(MethodDefinition m,Instruction i){
  if(i.OpCode==OpCodes.Stloc_0)return m.Body.Variables[0];if(i.OpCode==OpCodes.Stloc_1)return m.Body.Variables[1];if(i.OpCode==OpCodes.Stloc_2)return m.Body.Variables[2];if(i.OpCode==OpCodes.Stloc_3)return m.Body.Variables[3];
  Need(i.OpCode==OpCodes.Stloc||i.OpCode==OpCodes.Stloc_S,"Expected captured position local");return (VariableDefinition)i.Operand;
 }
 static Instruction[] Reads(MethodDefinition m){
  var reads=m.Body.Instructions.Where(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).FullName=="UnityEngine.Vector3 UnityEngine.Transform::get_localPosition()").ToArray();
  Need(reads.Length==6,"Expected six original position reads");
  for(int n=0;n<reads.Length;n++){
   var position=reads[n];var transform=position.Previous;var endpoint=transform.Previous;var receiver=endpoint.Previous;var p=(MethodReference)position.Operand;var t=transform.Operand as MethodReference;var f=endpoint.Operand as FieldReference;
   Need(position.OpCode==OpCodes.Callvirt&&p.DeclaringType.Scope.Name=="UnityEngine"&&p.HasThis&&p.Parameters.Count==0,"Expected native position getter");
   Need(transform.OpCode==OpCodes.Callvirt&&t!=null&&t.FullName=="UnityEngine.Transform UnityEngine.Component::get_transform()"&&t.DeclaringType.Scope.Name=="UnityEngine"&&t.HasThis&&t.Parameters.Count==0,"Expected native transform getter");
   Need(receiver.OpCode==OpCodes.Ldarg_0&&endpoint.OpCode==OpCodes.Ldfld&&f!=null&&f.DeclaringType.FullName==m.DeclaringType.FullName&&f.FieldType.FullName=="UnitManager"&&f.Name==((n==3||n==5)?"startUnit":"endUnit"),"Unexpected endpoint access order");
   var local=StoredLocal(m,position.Next);Need(local.VariableType.FullName=="UnityEngine.Vector3"&&local.VariableType.Scope.Name=="UnityEngine","Expected Vector3 local");
  }
  return reads;
 }
 // A behavior fixture uses the same six-read pattern; production additionally
 // requires the complete method fingerprint, including references and EH.
 internal static int Rewrite(MethodDefinition m){
  Need(m.HasThis&&m.ReturnType.FullName=="System.Single"&&m.Parameters.Count==0&&m.Body.InitLocals&&m.Body.ExceptionHandlers.Count==0,"Unexpected distance signature");
  var reads=Reads(m);int[] repeated={1,4,5},first={0,2,3};
  for(int n=0;n<repeated.Length;n++){
   var position=reads[repeated[n]];var begin=position.Previous.Previous.Previous;
   // Keep every instruction object and original Vector3 local, so branches,
   // arithmetic precision and the first end/start access order stay unchanged.
   begin.OpCode=OpCodes.Ldloc;begin.Operand=StoredLocal(m,reads[first[n]].Next);
   for(var i=begin.Next;i!=position.Next;i=i.Next){i.OpCode=OpCodes.Nop;i.Operand=null;}
  }
  return repeated.Length;
 }
 internal static int Reverse(AssemblyDefinition before,AssemblyDefinition after){
  Need(before.MainModule.AssemblyReferences.Select(x=>x.FullName).SequenceEqual(after.MainModule.AssemblyReferences.Select(x=>x.FullName)),"Assembly references changed");
  using(var stream=new MemoryStream()){
   before.Write(stream);stream.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(stream)){
    Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,after,out methods,out instructions);
    var a=expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);
    var b=after.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);
    Need(a.SequenceEqual(b),"Method initialization, references or exception contract changed");
   }
  }
  var source=Target(before.MainModule);var target=Target(after.MainModule);var reads=Reads(source);
  foreach(int n in new[]{1,4,5}){
   int end=source.Body.Instructions.IndexOf(reads[n]);
   for(int j=end-3;j<=end;j++){
    var old=source.Body.Instructions[j];var current=target.Body.Instructions[j];current.OpCode=old.OpCode;
    var field=old.Operand as FieldReference;var method=old.Operand as MethodReference;
    current.Operand=field!=null?(object)target.DeclaringType.Fields.Single(f=>f.Name==field.Name):method!=null?(object)after.MainModule.ImportReference(method):old.Operand;
   }
  }
  return 3;
 }
}
