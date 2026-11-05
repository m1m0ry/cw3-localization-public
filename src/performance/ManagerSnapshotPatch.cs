using System;
using System.Linq;
using System.Collections.Generic;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Preserve the public fresh-array API. Only audited synchronous update loops
// borrow a bounded per-pool buffer, with explicit counts and finally release.
internal static class ManagerSnapshotPatch {
 internal const int CapacityLimit=16384;
 internal const string Prefix="__cw3Snapshot";
 static void Need(bool value,string label){if(!value)throw new Exception(label);}
 internal static readonly string[] HotMethods={"System.Void EffectManager::EffectsUpdate()","System.Void GameSpace::PacketsUpdate()","System.Void GameSpace::MistUpdate()"};
 // Full original-loop contracts reject branches, escapes, writes and exits that
 // the lease rewrite was not designed to handle. The fixture emits these same loops.
 static readonly string[] LoopHashes={"eb85aa7a1078ed1f06d6117762f1e2b35f8ce02f76b834de241ca25baae85a7d","cc56c307a1b321cd5236a15cddf5629355e4f6ed368987fbbcc0cb7354de35ef","38c26aaa10642050f3b26c28cb433e556ea3e3c1572e6dc789d0684b6a1c6aab"};
 static string LoopHash(MethodDefinition m){var xs=m.Body.Instructions;var canonical=String.Join("\n",m.Body.Variables.Select(v=>v.VariableType.FullName).Concat(xs.Select(i=>{string op=i.OpCode.Name;if(op.EndsWith(".s")&&i.Operand is Instruction)op=op.Substring(0,op.Length-2);string value=i.Operand is Instruction?"target:"+xs.IndexOf((Instruction)i.Operand):(i.Operand==null?"":i.Operand.ToString());return op+" "+value;})).ToArray());using(var sha=System.Security.Cryptography.SHA256.Create())return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(canonical))).Replace("-","").ToLowerInvariant();}
 static IEnumerable<MethodDefinition> Methods(ModuleDefinition m){return m.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(x=>x.HasBody);}
 static bool Snapshot(Instruction i){var r=i.Operand as MethodReference;return i.OpCode==OpCodes.Callvirt&&r!=null&&r.Name=="GetActiveManagers"&&(r.DeclaringType.Name=="ManagerPool`1"||r.DeclaringType.Name=="MultiManagerPool`1");}
 static VariableDefinition Local(MethodDefinition m,Instruction i,bool store){
  var c=i.OpCode.Code;int n=-1;
  if(store){if(c==Code.Stloc_0)n=0;else if(c==Code.Stloc_1)n=1;else if(c==Code.Stloc_2)n=2;else if(c==Code.Stloc_3)n=3;else if(c==Code.Stloc||c==Code.Stloc_S)return (VariableDefinition)i.Operand;}
  else{if(c==Code.Ldloc_0)n=0;else if(c==Code.Ldloc_1)n=1;else if(c==Code.Ldloc_2)n=2;else if(c==Code.Ldloc_3)n=3;else if(c==Code.Ldloc||c==Code.Ldloc_S)return (VariableDefinition)i.Operand;}
  return n<0?null:m.Body.Variables[n];
 }
 static MethodReference Bound(MethodDefinition method,TypeReference owner){var r=new MethodReference(method.Name,method.ReturnType,owner){HasThis=true};foreach(var p in method.Parameters)r.Parameters.Add(new ParameterDefinition(p.ParameterType));return r;}
 sealed class PoolMethods {internal MethodDefinition Borrow,Release;}
 static PoolMethods AddPoolMethods(ModuleDefinition module,TypeDefinition pool,MethodReference clear){
  Need(!pool.Fields.Any(f=>f.Name.StartsWith(Prefix))&&!pool.Methods.Any(m=>m.Name.StartsWith(Prefix)),"Snapshot patch already present");
  var original=pool.Methods.Single(m=>m.Name=="GetActiveManagers"&&m.Parameters.Count==0);var active=pool.Fields.Single(f=>f.Name=="activeManagers");
  string producerHash=pool.Name=="ManagerPool`1"?"77323540230987160297fe306f828e3b7e1fcdf26569fd0280e0770d8c7b6d1d":"9af7e40ae3296456883af3a8c4663a9bc430bcfe82361fa179a14ede3d09fee1";
  Need(original.Body.InitLocals&&original.Body.ExceptionHandlers.Count==0&&LoopHash(original)==producerHash,"Unsupported public snapshot producer");
  Need(!active.IsStatic&&active.FieldType.FullName=="System.Collections.Generic.HashSet`1<T>"&&active.FieldType.Scope.Name=="System.Core","Expected original BCL active set");
  var count=original.Body.Instructions.Select(i=>i.Operand as MethodReference).Single(mr=>mr!=null&&mr.Name=="get_Count");var copy=original.Body.Instructions.Select(i=>i.Operand as MethodReference).Single(mr=>mr!=null&&mr.Name=="CopyTo");
  var parameter=pool.GenericParameters.Single();var array=new ArrayType(parameter);var owner=new GenericInstanceType(pool);owner.GenericArguments.Add(parameter);
  var buffer=new FieldDefinition(Prefix+"Buffer",FieldAttributes.Private,array);var busy=new FieldDefinition(Prefix+"Busy",FieldAttributes.Private,module.TypeSystem.Boolean);pool.Fields.Add(buffer);pool.Fields.Add(busy);
  var bufferRef=new FieldReference(buffer.Name,array,owner);var busyRef=new FieldReference(busy.Name,module.TypeSystem.Boolean,owner);var activeRef=new FieldReference(active.Name,active.FieldType,owner);
  var release=new MethodDefinition(Prefix+"Release",MethodAttributes.Assembly|MethodAttributes.HideBySig,module.TypeSystem.Void);release.Parameters.Add(new ParameterDefinition("snapshot",ParameterAttributes.None,array));release.Parameters.Add(new ParameterDefinition("count",ParameterAttributes.None,module.TypeSystem.Int32));pool.Methods.Add(release);
  var r=release.Body.GetILProcessor();var end=r.Create(OpCodes.Ret);
  r.Append(r.Create(OpCodes.Ldarg_0));r.Append(r.Create(OpCodes.Ldfld,busyRef));r.Append(r.Create(OpCodes.Brfalse,end));
  r.Append(r.Create(OpCodes.Ldarg_1));r.Append(r.Create(OpCodes.Brfalse,end));r.Append(r.Create(OpCodes.Ldarg_1));r.Append(r.Create(OpCodes.Ldarg_0));r.Append(r.Create(OpCodes.Ldfld,bufferRef));r.Append(r.Create(OpCodes.Bne_Un,end));
  r.Append(r.Create(OpCodes.Ldarg_1));r.Append(r.Create(OpCodes.Ldc_I4_0));r.Append(r.Create(OpCodes.Ldarg_2));r.Append(r.Create(OpCodes.Call,clear));r.Append(r.Create(OpCodes.Ldarg_0));r.Append(r.Create(OpCodes.Ldc_I4_0));r.Append(r.Create(OpCodes.Stfld,busyRef));r.Append(end);
  var borrow=new MethodDefinition(Prefix+"Borrow",MethodAttributes.Assembly|MethodAttributes.HideBySig,array);borrow.Parameters.Add(new ParameterDefinition("count",ParameterAttributes.Out,new ByReferenceType(module.TypeSystem.Int32)));pool.Methods.Add(borrow);borrow.Body.InitLocals=true;
  var capacity=new VariableDefinition(module.TypeSystem.Int32);borrow.Body.Variables.Add(capacity);var il=borrow.Body.GetILProcessor();
  var nonempty=il.Create(OpCodes.Ldarg_0);var fallback=il.Create(OpCodes.Ldarg_0);var ready=il.Create(OpCodes.Ldarg_0);var grow=il.Create(OpCodes.Ldc_I4,16);var loop=il.Create(OpCodes.Ldloc,capacity);var sizeCheck=il.Create(OpCodes.Ldloc,capacity);var copyStart=il.Create(OpCodes.Ldarg_0);var failed=il.Create(OpCodes.Pop);var done=il.Create(OpCodes.Ldarg_0);
  il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldfld,activeRef));il.Append(il.Create(OpCodes.Callvirt,count));il.Append(il.Create(OpCodes.Stind_I4));
  il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldind_I4));il.Append(il.Create(OpCodes.Brtrue,nonempty));il.Append(il.Create(OpCodes.Ldnull));il.Append(il.Create(OpCodes.Ret));
  il.Append(nonempty);il.Append(il.Create(OpCodes.Ldfld,busyRef));il.Append(il.Create(OpCodes.Brtrue,fallback));il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldind_I4));il.Append(il.Create(OpCodes.Ldc_I4,CapacityLimit));il.Append(il.Create(OpCodes.Bgt,fallback));
  il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldfld,bufferRef));il.Append(il.Create(OpCodes.Brfalse,grow));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldfld,bufferRef));il.Append(il.Create(OpCodes.Ldlen));il.Append(il.Create(OpCodes.Conv_I4));il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldind_I4));il.Append(il.Create(OpCodes.Bge,ready));
  il.Append(grow);il.Append(il.Create(OpCodes.Stloc,capacity));il.Append(il.Create(OpCodes.Br,sizeCheck));il.Append(loop);il.Append(il.Create(OpCodes.Ldc_I4_2));il.Append(il.Create(OpCodes.Mul));il.Append(il.Create(OpCodes.Stloc,capacity));il.Append(sizeCheck);il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldind_I4));il.Append(il.Create(OpCodes.Blt,loop));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldloc,capacity));il.Append(il.Create(OpCodes.Newarr,parameter));il.Append(il.Create(OpCodes.Stfld,bufferRef));
  il.Append(ready);il.Append(il.Create(OpCodes.Ldc_I4_1));il.Append(il.Create(OpCodes.Stfld,busyRef));
  il.Append(copyStart);il.Append(il.Create(OpCodes.Ldfld,activeRef));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldfld,bufferRef));il.Append(il.Create(OpCodes.Callvirt,copy));il.Append(il.Create(OpCodes.Leave,done));
  il.Append(failed);il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldfld,bufferRef));il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Ldind_I4));il.Append(il.Create(OpCodes.Call,Bound(release,owner)));il.Append(il.Create(OpCodes.Rethrow));
  il.Append(done);il.Append(il.Create(OpCodes.Ldfld,bufferRef));il.Append(il.Create(OpCodes.Ret));
  il.Append(fallback);il.Append(il.Create(OpCodes.Call,Bound(original,owner)));il.Append(il.Create(OpCodes.Ret));
  borrow.Body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Catch){TryStart=copyStart,TryEnd=failed,HandlerStart=failed,HandlerEnd=done,CatchType=new TypeReference("System","Exception",module,module.TypeSystem.Object.Scope)});
  return new PoolMethods{Borrow=borrow,Release=release};
 }
 static void ExpandBranches(MethodDefinition method){foreach(var i in method.Body.Instructions){if(i.OpCode==OpCodes.Br_S)i.OpCode=OpCodes.Br;else if(i.OpCode==OpCodes.Brtrue_S)i.OpCode=OpCodes.Brtrue;else if(i.OpCode==OpCodes.Brfalse_S)i.OpCode=OpCodes.Brfalse;else if(i.OpCode==OpCodes.Blt_S)i.OpCode=OpCodes.Blt;else if(i.OpCode==OpCodes.Bge_S)i.OpCode=OpCodes.Bge;}}
 internal static int Apply(ModuleDefinition module){
  var methods=Methods(module).Where(m=>HotMethods.Contains(m.FullName)).ToArray();Need(methods.Length==3,"Missing fixed update methods");
  var plans=new List<Tuple<MethodDefinition,Instruction,Instruction>>();
  foreach(var m in methods){Need(LoopHash(m)==LoopHashes[Array.IndexOf(HotMethods,m.FullName)],"Unsupported update-loop layout: "+m.FullName);Need(m.Body.ExceptionHandlers.Count==0&&m.Body.InitLocals,"Unexpected update exception/local layout");var calls=m.Body.Instructions.Where(Snapshot).ToArray();Need(calls.Length==(m.Name=="PacketsUpdate"?3:1),"Unexpected snapshot call count");
   foreach(var c in calls){var stored=Local(m,c.Next,true);Need(stored!=null&&Local(m,c.Next.Next,false)==stored,"Expected snapshot local copy");var alias=Local(m,c.Next.Next.Next,true);Need(alias!=null,"Expected foreach snapshot alias");
    var bound=m.Body.Instructions.SkipWhile(i=>i!=c).TakeWhile(i=>i==c||!Snapshot(i)).Where(i=>i.OpCode==OpCodes.Ldlen&&Local(m,i.Previous,false)==alias).ToArray();Need(bound.Length==1&&bound[0].Next.OpCode==OpCodes.Conv_I4,"Expected one array loop bound");
    var branch=bound[0].Next.Next;Need(branch.OpCode==OpCodes.Blt||branch.OpCode==OpCodes.Blt_S,"Expected foreach tail branch");
    // No external control transfer may enter the loop after acquisition.
    int start=m.Body.Instructions.IndexOf(c),end=m.Body.Instructions.IndexOf(branch);
    foreach(var i in m.Body.Instructions){var targets=i.Operand is Instruction[]?(Instruction[])i.Operand:i.Operand is Instruction?new[]{(Instruction)i.Operand}:new Instruction[0];foreach(var target in targets){int at=m.Body.Instructions.IndexOf(target),from=m.Body.Instructions.IndexOf(i);Need(!(at>=start&&at<=end&&(from<start||from>end)),"External branch enters borrowed loop");}}
    plans.Add(Tuple.Create(m,c,bound[0]));
   }
  }
  var clear=Methods(module).SelectMany(m=>m.Body.Instructions).Select(i=>i.Operand as MethodReference).FirstOrDefault(r=>r!=null&&r.FullName=="System.Void System.Array::Clear(System.Array,System.Int32,System.Int32)");Need(clear!=null&&clear.DeclaringType.Scope.Name=="mscorlib","Missing original BCL Array.Clear reference");
  var poolNames=plans.Select(p=>((MethodReference)p.Item2.Operand).DeclaringType.Name).Distinct().ToArray();var pools=poolNames.ToDictionary(n=>n,n=>AddPoolMethods(module,module.Types.Single(t=>t.Name==n),clear));
  foreach(var plan in plans){var method=plan.Item1;var call=plan.Item2;var length=plan.Item3;var old=(MethodReference)call.Operand;var pool=pools[old.DeclaringType.Name];var il=method.Body.GetILProcessor();var owner=new VariableDefinition(old.DeclaringType);var array=new VariableDefinition(new ArrayType(((GenericInstanceType)old.DeclaringType).GenericArguments[0]));var count=new VariableDefinition(module.TypeSystem.Int32);method.Body.Variables.Add(owner);method.Body.Variables.Add(array);method.Body.Variables.Add(count);
   // Acquire inside its own protected region. Stack already contains the pool;
   // keep exactly that owner even when a callback replaces the global field.
   il.InsertBefore(call,il.Create(OpCodes.Stloc,owner));var start=il.Create(OpCodes.Ldloc,owner);il.InsertBefore(call,start);il.InsertBefore(call,il.Create(OpCodes.Ldloca,count));call.Operand=Bound(pool.Borrow,old.DeclaringType);var save=il.Create(OpCodes.Dup);il.InsertAfter(call,save);il.InsertAfter(save,il.Create(OpCodes.Stloc,array));
   length.Previous.OpCode=OpCodes.Ldloc;length.Previous.Operand=count;length.OpCode=OpCodes.Nop;length.Operand=null;length.Next.OpCode=OpCodes.Nop;length.Next.Operand=null;
   var exit=length.Next.Next.Next;var finallyStart=il.Create(OpCodes.Ldloc,owner);var finallyEnd=il.Create(OpCodes.Endfinally);il.InsertBefore(exit,il.Create(OpCodes.Leave,exit));il.InsertBefore(exit,finallyStart);il.InsertBefore(exit,il.Create(OpCodes.Brfalse,finallyEnd));il.InsertBefore(exit,il.Create(OpCodes.Ldloc,owner));il.InsertBefore(exit,il.Create(OpCodes.Ldloc,array));il.InsertBefore(exit,il.Create(OpCodes.Ldloc,count));il.InsertBefore(exit,il.Create(OpCodes.Callvirt,Bound(pool.Release,old.DeclaringType)));il.InsertBefore(exit,finallyEnd);
   method.Body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Finally){TryStart=start,TryEnd=finallyStart,HandlerStart=finallyStart,HandlerEnd=exit});
  }
  foreach(var m in methods)ExpandBranches(m);return plans.Count;
 }
 internal static int Reverse(AssemblyDefinition original,AssemblyDefinition patched){
  Need(original.MainModule.AssemblyReferences.Select(r=>r.FullName).SequenceEqual(patched.MainModule.AssemblyReferences.Select(r=>r.FullName)),"Assembly references changed");
  // First verify all helper bodies, leases, EH ranges and untouched content
  // against the deterministic transform; then reverse only its explicit edits.
  using(var stream=new System.IO.MemoryStream()){
   original.Write(stream);stream.Position=0;
   using(var expected=AssemblyDefinition.ReadAssembly(stream)){
    Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,patched,out methods,out instructions);
    var xs=Methods(expected.MainModule).ToArray();var ys=Methods(patched.MainModule).ToArray();
    for(int n=0;n<xs.Length;n++){
     Need(xs[n].Body.InitLocals==ys[n].Body.InitLocals,"Local initialization changed");
     for(int h=0;h<xs[n].Body.ExceptionHandlers.Count;h++){
      var a=xs[n].Body.ExceptionHandlers[h];var b=ys[n].Body.ExceptionHandlers[h];
      Need((a.CatchType==null?null:a.CatchType.FullName)==(b.CatchType==null?null:b.CatchType.FullName)&&a.FilterStart==null&&b.FilterStart==null,"Exception catch/filter changed");
     }
    }
   }
  }
  int total=0;
  foreach(var before in Methods(original.MainModule).Where(m=>HotMethods.Contains(m.FullName))){
   var after=Methods(patched.MainModule).Single(m=>m.FullName==before.FullName);var sites=before.Body.Instructions.Select((i,n)=>new{Instruction=i,Index=n}).Where(x=>Snapshot(x.Instruction)).ToArray();
   for(int n=sites.Length-1;n>=0;n--){
    var old=sites[n];var c=after.Body.Instructions[old.Index+13*n+3];
    var alias=Local(before,old.Instruction.Next.Next.Next,true);
    var length=after.Body.Instructions.SkipWhile(i=>i!=c).First(i=>i.OpCode==OpCodes.Nop&&i.Previous.OpCode==OpCodes.Ldloc&&i.Previous.Operand==after.Body.Variables[before.Body.Variables.Count+3*n+2]);
    var originalLength=before.Body.Instructions.SkipWhile(i=>i!=old.Instruction).First(i=>i.OpCode==OpCodes.Ldlen&&Local(before,i.Previous,false)==alias);
    length.Previous.OpCode=originalLength.Previous.OpCode;length.Previous.Operand=originalLength.Previous.Operand is VariableDefinition?after.Body.Variables[((VariableDefinition)originalLength.Previous.Operand).Index]:originalLength.Previous.Operand;length.OpCode=OpCodes.Ldlen;length.Operand=null;length.Next.OpCode=OpCodes.Conv_I4;length.Next.Operand=null;
    var tail=length.Next.Next.Next;for(int k=0;k<8;k++){var next=tail.Next;after.Body.Instructions.Remove(tail);tail=next;}
    var added=c.Next;for(int k=0;k<2;k++){var next=added.Next;after.Body.Instructions.Remove(added);added=next;}
    for(int k=0;k<3;k++)after.Body.Instructions.Remove(c.Previous);
    c.Operand=old.Instruction.Operand;
    for(int k=0;k<3;k++)after.Body.Variables.RemoveAt(after.Body.Variables.Count-1);
    total++;
   }
   after.Body.ExceptionHandlers.Clear();
  }
  foreach(var pool in patched.MainModule.Types.Where(t=>t.Name=="ManagerPool`1"||t.Name=="MultiManagerPool`1")){
   foreach(var f in pool.Fields.Where(f=>f.Name.StartsWith(Prefix)).ToArray())pool.Fields.Remove(f);
   foreach(var m in pool.Methods.Where(m=>m.Name.StartsWith(Prefix)).ToArray())pool.Methods.Remove(m);
  }
  return total;
 }

}
