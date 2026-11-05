using System;
using System.Linq;
using System.Collections.Generic;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Old compiler output boxes a BCL struct enumerator solely to call IDisposable.
// Dispose a stack-local COPY instead: do not mutate the original enumerator local,
// change collection traversal, omit disposal, or add a persistent runtime cache.
internal static class EnumeratorDisposePatch {
 static readonly HashSet<string> Supported=new HashSet<string>{
  "System.Collections.Generic.List`1/Enumerator", "System.Collections.Generic.HashSet`1/Enumerator",
  "System.Collections.Generic.Dictionary`2/Enumerator", "System.Collections.Generic.Queue`1/Enumerator",
  "System.Collections.Generic.Stack`1/Enumerator", "System.Collections.Generic.Dictionary`2/KeyCollection/Enumerator",
  "System.Collections.Generic.Dictionary`2/ValueCollection/Enumerator"};
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static IEnumerable<MethodDefinition> Methods(ModuleDefinition module){return module.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody);}
 static bool Candidate(Instruction i){
  var type=i.Operand as GenericInstanceType;var call=i.Next==null?null:i.Next.Operand as MethodReference;
  return i.OpCode==OpCodes.Box&&type!=null&&Supported.Contains(type.ElementType.FullName)
   &&(type.Scope.Name=="mscorlib"||type.Scope.Name=="System.Core")
   &&i.Next.OpCode==OpCodes.Callvirt&&call!=null&&call.FullName=="System.Void System.IDisposable::Dispose()"
   &&call.DeclaringType.Scope.Name=="mscorlib";
 }
 static void CheckValueDisposal(TypeReference type){
  var definition=type.Resolve();
  Need(definition!=null&&definition.IsValueType,"Expected BCL value enumerator: "+type);
  Need(definition.Interfaces.Any(i=>i.InterfaceType.FullName=="System.IDisposable"),"Enumerator must implement IDisposable: "+type);
  Need(definition.Methods.Any(m=>m.Name=="Dispose"&&!m.IsStatic&&m.Parameters.Count==0&&m.ReturnType.FullName=="System.Void"),"Expected struct Dispose implementation: "+type);
 }
 static void CheckDisposalBoundary(MethodDefinition method,Instruction box){
  var dispose=box.Next;
  // A prefix and its call form one instruction for branch/EH entry. Refuse an
  // unusual input that can enter the old call without passing through the box.
  foreach(var i in method.Body.Instructions){
   Need(i.Operand!=dispose&&(!(i.Operand is Instruction[])||!((Instruction[])i.Operand).Contains(dispose)),"Branch enters Dispose call: "+method.FullName);
  }
  foreach(var h in method.Body.ExceptionHandlers)Need(h.TryStart!=dispose&&h.TryEnd!=dispose&&h.HandlerStart!=dispose&&h.HandlerEnd!=dispose&&h.FilterStart!=dispose,"EH boundary splits Dispose prefix: "+method.FullName);
 }
 static void ExpandBranches(MethodDefinition method){
  var longForms=new Dictionary<Code,OpCode>{{Code.Br_S,OpCodes.Br},{Code.Brfalse_S,OpCodes.Brfalse},{Code.Brtrue_S,OpCodes.Brtrue},
   {Code.Beq_S,OpCodes.Beq},{Code.Bge_S,OpCodes.Bge},{Code.Bgt_S,OpCodes.Bgt},{Code.Ble_S,OpCodes.Ble},{Code.Blt_S,OpCodes.Blt},
   {Code.Bne_Un_S,OpCodes.Bne_Un},{Code.Bge_Un_S,OpCodes.Bge_Un},{Code.Bgt_Un_S,OpCodes.Bgt_Un},{Code.Ble_Un_S,OpCodes.Ble_Un},
   {Code.Blt_Un_S,OpCodes.Blt_Un},{Code.Leave_S,OpCodes.Leave}};
  foreach(var i in method.Body.Instructions){OpCode op;if(longForms.TryGetValue(i.OpCode.Code,out op))i.OpCode=op;}
 }
 internal static int Apply(ModuleDefinition module){
  int count=0;
  // Resolve and validate every type before making changes. Game input hashes are
  // checked by the build pipeline; unknown enumerators are deliberately excluded.
  var sites=Methods(module).SelectMany(m=>m.Body.Instructions.Where(Candidate).Select(i=>new{Method=m,Instruction=i})).ToArray();
  foreach(var type in sites.Select(s=>(TypeReference)s.Instruction.Operand).GroupBy(t=>t.FullName).Select(g=>g.First()))CheckValueDisposal(type);
  foreach(var site in sites)CheckDisposalBoundary(site.Method,site.Instruction);
  Need(sites.Length>0,"No supported boxed enumerator disposal sites");
  foreach(var site in sites){
   var method=site.Method;var instruction=site.Instruction;var type=(TypeReference)instruction.Operand;
   var copy=new VariableDefinition(type);method.Body.Variables.Add(copy);var il=method.Body.GetILProcessor();
   // Preserve this instruction identity because it can be a branch/EH boundary.
   instruction.OpCode=OpCodes.Stloc;instruction.Operand=copy;
   var address=il.Create(OpCodes.Ldloca,copy);il.InsertAfter(instruction,address);il.InsertAfter(address,il.Create(OpCodes.Constrained,type));count++;
  }
  foreach(var method in sites.Select(s=>s.Method).Distinct())ExpandBranches(method);
  return count;
 }
 static string TypeIdentity(TypeReference type){
  if(type==null)return "";
  var generic=type as GenericInstanceType;
  return type.FullName+"@"+type.Scope+ (generic==null?"":"["+String.Join(",",generic.GenericArguments.Select(TypeIdentity).ToArray())+"]");
 }
 internal static int Reverse(ModuleDefinition original,ModuleDefinition patched){
  Need(original.AssemblyReferences.Select(r=>r.FullName).SequenceEqual(patched.AssemblyReferences.Select(r=>r.FullName)),"Assembly references changed");
  var all=Methods(patched).ToDictionary(m=>m.FullName);int count=0;
  foreach(var before in Methods(original)){
   var sites=before.Body.Instructions.Select((i,index)=>new{Instruction=i,Index=index}).Where(s=>Candidate(s.Instruction)).ToArray();if(sites.Length==0)continue;
   MethodDefinition after;Need(all.TryGetValue(before.FullName,out after),"Missing method: "+before.FullName);
   var xs=after.Body.Instructions;int baseLocals=before.Body.Variables.Count;
   Need(after.Body.InitLocals==before.Body.InitLocals,"Local initialization changed");
   Need(after.Body.Variables.Count==baseLocals+sites.Length,"Enumerator copy local count: "+before.FullName);
   // Descend so original instruction indexes are restored after each removal.
   for(int n=sites.Length-1;n>=0;n--){
    var site=sites[n];int at=site.Index+2*n;var type=(TypeReference)site.Instruction.Operand;var local=after.Body.Variables[baseLocals+n];
    Need(TypeIdentity(local.VariableType)==TypeIdentity(type),"Enumerator copy local type");
    Need(at+3<xs.Count&&xs[at].OpCode==OpCodes.Stloc&&xs[at].Operand==local,"Enumerator copy store");
    Need(xs[at+1].OpCode==OpCodes.Ldloca&&xs[at+1].Operand==local,"Enumerator copy address");
    Need(xs[at+2].OpCode==OpCodes.Constrained&&TypeIdentity(xs[at+2].Operand as TypeReference)==TypeIdentity(type),"Enumerator constrained dispatch");
    Need(xs[at+3].OpCode==OpCodes.Callvirt&&xs[at+3].Operand.ToString()==site.Instruction.Next.Operand.ToString(),"Enumerator Dispose call");
    xs[at].OpCode=OpCodes.Box;xs[at].Operand=local.VariableType;xs.RemoveAt(at+2);xs.RemoveAt(at+1);after.Body.Variables.RemoveAt(baseLocals+n);count++;
   }
  }
  Need(count>0,"No verified enumerator disposal sites");return count;
 }
}
