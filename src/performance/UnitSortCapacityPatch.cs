using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

// UnitsUpdate already captures every tagged object before constructing its private
// sorted table. Reserve exactly that count; keep Add order and both consumers.
// This removes growth arrays, not discovery, sorting or the per-step snapshot.
internal static class UnitSortCapacityPatch {
 const string Table="System.Collections.Generic.SortedList`2<System.Int32,UnitManager>";
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
 internal static MethodDefinition Target(ModuleDefinition m){return m.GetType("GameSpace").Methods.Single(x=>x.Name=="UnitsUpdate");}
 internal static int Apply(ModuleDefinition module){
  var m=Target(module);var hash=Fingerprint(m);
  Need(hash=="21cbfde84b0ea1a34ad098d48f98c1f6c9a576e1f5a7ff5d799e64e2b8a95151"||hash=="b68fc9614e63f540f8da84b6790f7ca7a9fb55c7f7f8e957f371475129a97638","Unsupported unit-update method layout: "+hash);
  return Rewrite(m);
 }
 // Separate structural transform permits an intentionally small behavior fixture.
 // Production must pass the complete known-method fingerprint above first.
 internal static int Rewrite(MethodDefinition m){
  Need(m.HasThis&&m.ReturnType.FullName=="System.Void"&&m.Parameters.Count==0&&m.Body.InitLocals,"Unexpected unit-update signature");
  var xs=m.Body.Instructions;var hits=xs.Where(i=>i.OpCode==OpCodes.Newobj&&i.Operand is MethodReference&&((MethodReference)i.Operand).DeclaringType.FullName==Table).ToArray();
  Need(hits.Length==1,"Expected one private sorted table");var site=hits[0];var old=(MethodReference)site.Operand;
  Need(old.Name==".ctor"&&old.HasThis&&old.Parameters.Count==0&&old.DeclaringType.Scope.Name=="System","Expected original System SortedList constructor");
  int index=xs.IndexOf(site);Need(index>=3,"Missing captured unit array");
  var tag=xs[index-3];var find=xs[index-2];var store=xs[index-1];
  Need(tag.OpCode==OpCodes.Ldstr&&(string)tag.Operand=="UnitTag","Expected original unit tag");
  var discovery=find.Operand as MethodReference;
  Need(find.OpCode==OpCodes.Call&&discovery!=null&&discovery.FullName=="UnityEngine.GameObject[] UnityEngine.GameObject::FindGameObjectsWithTag(System.String)"&&discovery.DeclaringType.Scope.Name=="UnityEngine","Expected original Unity tag snapshot");
  var array=store.Operand as VariableDefinition;
  if(store.OpCode==OpCodes.Stloc_0)array=m.Body.Variables[0];else if(store.OpCode==OpCodes.Stloc_1)array=m.Body.Variables[1];else if(store.OpCode==OpCodes.Stloc_2)array=m.Body.Variables[2];else if(store.OpCode==OpCodes.Stloc_3)array=m.Body.Variables[3];else Need(store.OpCode==OpCodes.Stloc||store.OpCode==OpCodes.Stloc_S,"Expected captured tag array local");
  Need(array!=null&&array.VariableType.FullName=="UnityEngine.GameObject[]"&&array.VariableType.Scope.Name=="UnityEngine","Expected Unity object-array local");
  var capacity=new MethodReference(".ctor",m.Module.TypeSystem.Void,old.DeclaringType){HasThis=true,CallingConvention=old.CallingConvention};capacity.Parameters.Add(new ParameterDefinition(m.Module.TypeSystem.Int32));
  // Reuse the original instruction object so branch/EH targets enter the whole
  // replacement, never its new constructor with an absent capacity argument.
  site.OpCode=OpCodes.Ldloc;site.Operand=array;var il=m.Body.GetILProcessor();var len=il.Create(OpCodes.Ldlen);var conv=il.Create(OpCodes.Conv_I4);var ctor=il.Create(OpCodes.Newobj,capacity);il.InsertAfter(site,len);il.InsertAfter(len,conv);il.InsertAfter(conv,ctor);return 1;
 }
 internal static int Reverse(AssemblyDefinition before,AssemblyDefinition after){
  Need(before.MainModule.AssemblyReferences.Select(x=>x.FullName).SequenceEqual(after.MainModule.AssemblyReferences.Select(x=>x.FullName)),"Assembly references changed");
  using(var stream=new MemoryStream()){
   before.Write(stream);stream.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(stream)){
    Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,after,out methods,out instructions);
    var a=expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);
    var b=after.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).Select(Fingerprint);
    Need(a.SequenceEqual(b),"Method initialization or exception contract changed");
   }
  }
  var old=Target(before.MainModule).Body.Instructions.Single(i=>i.OpCode==OpCodes.Newobj&&i.Operand is MethodReference&&((MethodReference)i.Operand).DeclaringType.FullName==Table);
  var body=Target(after.MainModule).Body;int index=Target(before.MainModule).Body.Instructions.IndexOf(old);var first=body.Instructions[index];
  var capacity=(MethodReference)body.Instructions[index+3].Operand;
  first.OpCode=OpCodes.Newobj;first.Operand=new MethodReference(".ctor",capacity.ReturnType,capacity.DeclaringType){HasThis=capacity.HasThis,CallingConvention=capacity.CallingConvention};
  // Targets still point at the retained first instruction. The expected-layout
  // check above proves no target/EH boundary was added inside these three nodes.
  for(int n=0;n<3;n++)body.Instructions.RemoveAt(index+1);return 1;
 }
}
