using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Dense scratch scores are valid only for an audited rectangular grid. The
// original search order, arithmetic and returned predecessor dictionary remain.
// Unsupported inputs and a busy cache retain the original dictionary method.
internal static class PathWorkspacePatch {
 internal const int CellLimit=65536;
 internal const string Prefix="__cw3Path";
 internal static string Fingerprint(MethodDefinition m){
  var xs=m.Body.Instructions;
  Func<Instruction,string> at=i=>i==null?"end":xs.IndexOf(i).ToString();
  var lines=new[]{m.FullName,"init:"+m.Body.InitLocals}.Concat(m.Body.Variables.Select(v=>v.VariableType.FullName)).Concat(xs.Select(i=>{
   string op=i.OpCode.Name;if(op.EndsWith(".s")&&i.Operand is Instruction)op=op.Substring(0,op.Length-2);
   string value=i.Operand is Instruction?"target:"+at((Instruction)i.Operand):i.Operand is Instruction[]?String.Join(",",((Instruction[])i.Operand).Select(at).ToArray()):i.Operand==null?"":i.Operand.ToString();return op+" "+value;
  })).Concat(m.Body.ExceptionHandlers.Select(h=>h.HandlerType+":"+at(h.TryStart)+":"+at(h.TryEnd)+":"+at(h.HandlerStart)+":"+at(h.HandlerEnd)+":"+at(h.FilterStart)+":"+h.CatchType));
  using(var sha=System.Security.Cryptography.SHA256.Create())return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(String.Join("\n",lines.ToArray())))).Replace("-","").ToLowerInvariant();
 }
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 internal static MethodDefinition Target(ModuleDefinition m){return m.GetType("CrplCore").Methods.Single(x=>x.Name=="PathFindTerrain");}
 internal static MethodDefinition[] AddHelpers(ModuleDefinition module,TypeDefinition owner){
  Need(!owner.Fields.Any(f=>f.Name.StartsWith(Prefix))&&!owner.Methods.Any(m=>m.Name.StartsWith(Prefix)),"Path workspace already present");
  var vector=new ArrayType(module.TypeSystem.Single);var array=new ArrayType(vector);var cache=new FieldDefinition(Prefix+"Cache",FieldAttributes.Private|FieldAttributes.Static,array);var busy=new FieldDefinition(Prefix+"Busy",FieldAttributes.Private|FieldAttributes.Static,module.TypeSystem.Boolean);owner.Fields.Add(cache);owner.Fields.Add(busy);
  var space=module.GetType("GameSpace");var terrain=module.GetType("Terrain");var instance=space.Fields.Single(f=>f.Name=="instance");var terrainField=space.Fields.Single(f=>f.Name=="terrain");var data=terrain.Fields.Single(f=>f.Name=="mapData");var width=space.Fields.Single(f=>f.Name=="GAMESPACE_WIDTH");var height=space.Fields.Single(f=>f.Name=="GAMESPACE_HEIGHT");
  var borrow=new MethodDefinition(Prefix+"Borrow",MethodAttributes.Private|MethodAttributes.Static|MethodAttributes.HideBySig,array);borrow.Parameters.Add(new ParameterDefinition("start",ParameterAttributes.None,module.TypeSystem.Int32));borrow.Parameters.Add(new ParameterDefinition("end",ParameterAttributes.None,module.TypeSystem.Int32));owner.Methods.Add(borrow);borrow.Body.InitLocals=true;
  var map=new VariableDefinition(data.FieldType);var length=new VariableDefinition(module.TypeSystem.Int32);var capacity=new VariableDefinition(module.TypeSystem.Int32);borrow.Body.Variables.Add(map);borrow.Body.Variables.Add(length);borrow.Body.Variables.Add(capacity);var il=borrow.Body.GetILProcessor();var fallback=il.Create(OpCodes.Ldnull);var ready=il.Create(OpCodes.Ldc_I4_1);var grow=il.Create(OpCodes.Ldc_I4,16);var loop=il.Create(OpCodes.Ldloc,capacity);var test=il.Create(OpCodes.Ldloc,capacity);
  il.Append(il.Create(OpCodes.Ldsfld,busy));il.Append(il.Create(OpCodes.Brtrue,fallback));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldarg_1));il.Append(il.Create(OpCodes.Beq,fallback));
  il.Append(il.Create(OpCodes.Ldsfld,instance));il.Append(il.Create(OpCodes.Ldfld,terrainField));il.Append(il.Create(OpCodes.Ldfld,data));il.Append(il.Create(OpCodes.Stloc,map));il.Append(il.Create(OpCodes.Ldloc,map));il.Append(il.Create(OpCodes.Brfalse,fallback));il.Append(il.Create(OpCodes.Ldloc,map));il.Append(il.Create(OpCodes.Ldlen));il.Append(il.Create(OpCodes.Conv_I4));il.Append(il.Create(OpCodes.Stloc,length));
  il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Ble,fallback));il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Ldc_I4,CellLimit));il.Append(il.Create(OpCodes.Bgt,fallback));
  foreach(var dimension in new[]{width,height}){il.Append(il.Create(OpCodes.Ldsfld,dimension));il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Ble,fallback));}
  il.Append(il.Create(OpCodes.Ldsfld,width));il.Append(il.Create(OpCodes.Conv_I8));il.Append(il.Create(OpCodes.Ldsfld,height));il.Append(il.Create(OpCodes.Conv_I8));il.Append(il.Create(OpCodes.Mul));il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Conv_I8));il.Append(il.Create(OpCodes.Bne_Un,fallback));
  for(int n=0;n<2;n++){il.Append(il.Create(OpCodes.Ldarg,borrow.Parameters[n]));il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Bge_Un,fallback));}
  il.Append(il.Create(OpCodes.Ldsfld,cache));il.Append(il.Create(OpCodes.Brfalse,grow));il.Append(il.Create(OpCodes.Ldsfld,cache));il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Ldelem_Ref));il.Append(il.Create(OpCodes.Ldlen));il.Append(il.Create(OpCodes.Conv_I4));il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Bge,ready));
  il.Append(grow);il.Append(il.Create(OpCodes.Stloc,capacity));il.Append(il.Create(OpCodes.Br,test));il.Append(loop);il.Append(il.Create(OpCodes.Ldc_I4_2));il.Append(il.Create(OpCodes.Mul));il.Append(il.Create(OpCodes.Stloc,capacity));il.Append(test);il.Append(il.Create(OpCodes.Ldloc,length));il.Append(il.Create(OpCodes.Blt,loop));
  // Publish only after all primitive arrays exist; failed allocation cannot lock it.
  il.Append(il.Create(OpCodes.Ldc_I4_3));il.Append(il.Create(OpCodes.Newarr,vector));for(int n=0;n<3;n++){il.Append(il.Create(OpCodes.Dup));il.Append(il.Create(OpCodes.Ldc_I4,n));il.Append(il.Create(OpCodes.Ldloc,capacity));il.Append(il.Create(OpCodes.Newarr,module.TypeSystem.Single));il.Append(il.Create(OpCodes.Stelem_Ref));}il.Append(il.Create(OpCodes.Stsfld,cache));
  il.Append(ready);il.Append(il.Create(OpCodes.Stsfld,busy));il.Append(il.Create(OpCodes.Ldsfld,cache));il.Append(il.Create(OpCodes.Ret));il.Append(fallback);il.Append(il.Create(OpCodes.Ret));
  var release=new MethodDefinition(Prefix+"Release",MethodAttributes.Private|MethodAttributes.Static|MethodAttributes.HideBySig,module.TypeSystem.Void);release.Parameters.Add(new ParameterDefinition("lease",ParameterAttributes.None,array));owner.Methods.Add(release);il=release.Body.GetILProcessor();var done=il.Create(OpCodes.Ret);
  il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Brfalse,done));il.Append(il.Create(OpCodes.Ldarg_0));il.Append(il.Create(OpCodes.Ldsfld,cache));il.Append(il.Create(OpCodes.Bne_Un,done));il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Stsfld,busy));il.Append(done);
  return new[]{borrow,release};
 }
 static MethodDefinition CloneSearch(MethodDefinition source,string name){
  var target=new MethodDefinition(name,MethodAttributes.Private|MethodAttributes.HideBySig,source.ReturnType);foreach(var p in source.Parameters)target.Parameters.Add(new ParameterDefinition(p.Name,p.Attributes,p.ParameterType));source.DeclaringType.Methods.Add(target);target.Body=new MethodBody(target){InitLocals=source.Body.InitLocals,MaxStackSize=source.Body.MaxStackSize};
  foreach(var v in source.Body.Variables)target.Body.Variables.Add(new VariableDefinition(v.VariableType));
  var map=source.Body.Instructions.ToDictionary(i=>i,i=>Instruction.Create(OpCodes.Nop));
  foreach(var old in source.Body.Instructions){var copy=map[old];copy.OpCode=old.OpCode;object x=old.Operand;if(x is Instruction)x=map[(Instruction)x];else if(x is Instruction[])x=((Instruction[])x).Select(i=>map[i]).ToArray();else if(x is VariableDefinition)x=target.Body.Variables[((VariableDefinition)x).Index];else if(x is ParameterDefinition)x=target.Parameters[((ParameterDefinition)x).Index];copy.Operand=x;target.Body.Instructions.Add(copy);}
  Func<Instruction,Instruction> at=i=>i==null?null:map[i];foreach(var h in source.Body.ExceptionHandlers)target.Body.ExceptionHandlers.Add(new ExceptionHandler(h.HandlerType){TryStart=at(h.TryStart),TryEnd=at(h.TryEnd),HandlerStart=at(h.HandlerStart),HandlerEnd=at(h.HandlerEnd),FilterStart=at(h.FilterStart),CatchType=h.CatchType});return target;
 }
 internal static int Apply(ModuleDefinition module){
  var m=Target(module);var hash=Fingerprint(m);Need(hash=="172406257c65e2e08f5af0098e6b673811fb190b11146ccaab2fb6d65c14fd25"||hash=="1027f438426b5f06a9fc4017d629e200c50e1d0c8fcd3a3bcfe33738fcfa4266","Unsupported pathfinding method layout: "+hash);
  Need(m.HasThis&&m.Body.InitLocals&&m.Parameters.Count==6&&m.ReturnType.FullName=="System.Collections.Generic.Dictionary`2<System.Int32,System.Int32>","Unsupported pathfinding signature");
  var helpers=AddHelpers(module,m.DeclaringType);var original=CloneSearch(m,Prefix+"Original");var dense=CloneSearch(m,Prefix+"Dense");var array=new ParameterDefinition("scores",ParameterAttributes.None,helpers[0].ReturnType);dense.Parameters.Add(array);const string scores="System.Collections.Generic.Dictionary`2<System.Int32,System.Single>";
  var locals=dense.Body.Variables.Where(v=>v.VariableType.FullName==scores).ToArray();Need(locals.Length==3,"Expected three score locals");foreach(var v in locals)v.VariableType=new ArrayType(module.TypeSystem.Single);
  int made=0,read=0,wrote=0;var il=dense.Body.GetILProcessor();foreach(var i in dense.Body.Instructions.ToArray()){
   var call=i.Operand as MethodReference;if(call==null||call.DeclaringType.FullName!=scores)continue;Need(call.DeclaringType.Scope.Name=="mscorlib","Expected original score BCL");
   if(i.OpCode==OpCodes.Newobj&&call.Parameters.Count==0){i.OpCode=OpCodes.Ldarg;i.Operand=array;var index=il.Create(OpCodes.Ldc_I4,made++);il.InsertAfter(i,index);il.InsertAfter(index,il.Create(OpCodes.Ldelem_Ref));}
   else if(i.OpCode==OpCodes.Callvirt&&call.Name=="get_Item"){i.OpCode=OpCodes.Ldelem_R4;i.Operand=null;read++;}
   else if(i.OpCode==OpCodes.Callvirt&&call.Name=="set_Item"){i.OpCode=OpCodes.Stelem_R4;i.Operand=null;wrote++;}
   else throw new Exception("Unsupported score operation: "+i);
  }Need(made==3&&read==6&&wrote==8,"Unexpected score operation counts: "+made+"/"+read+"/"+wrote);
  m.Body=new MethodBody(m){InitLocals=true};var lease=new VariableDefinition(helpers[0].ReturnType);var result=new VariableDefinition(m.ReturnType);m.Body.Variables.Add(lease);m.Body.Variables.Add(result);il=m.Body.GetILProcessor();var fallback=il.Create(OpCodes.Ldarg_0);var start=il.Create(OpCodes.Ldarg_0);var end=il.Create(OpCodes.Ldloc,result);var cleanup=il.Create(OpCodes.Ldloc,lease);
  il.Append(il.Create(OpCodes.Ldarg,m.Parameters[0]));il.Append(il.Create(OpCodes.Ldarg,m.Parameters[1]));il.Append(il.Create(OpCodes.Call,helpers[0]));il.Append(il.Create(OpCodes.Stloc,lease));il.Append(il.Create(OpCodes.Ldloc,lease));il.Append(il.Create(OpCodes.Brfalse,fallback));
  il.Append(start);foreach(var p in m.Parameters)il.Append(il.Create(OpCodes.Ldarg,p));il.Append(il.Create(OpCodes.Ldloc,lease));il.Append(il.Create(OpCodes.Call,dense));il.Append(il.Create(OpCodes.Stloc,result));il.Append(il.Create(OpCodes.Leave,end));il.Append(cleanup);il.Append(il.Create(OpCodes.Call,helpers[1]));il.Append(il.Create(OpCodes.Endfinally));il.Append(end);il.Append(il.Create(OpCodes.Ret));
  il.Append(fallback);foreach(var p in m.Parameters)il.Append(il.Create(OpCodes.Ldarg,p));il.Append(il.Create(OpCodes.Call,original));il.Append(il.Create(OpCodes.Ret));m.Body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Finally){TryStart=start,TryEnd=cleanup,HandlerStart=cleanup,HandlerEnd=end});return 3;
 }
 internal static int Reverse(AssemblyDefinition original,AssemblyDefinition patched){
  Need(original.MainModule.AssemblyReferences.Select(x=>x.FullName).SequenceEqual(patched.MainModule.AssemblyReferences.Select(x=>x.FullName)),"Assembly references changed");
  using(var bytes=new System.IO.MemoryStream()){
   original.Write(bytes);bytes.Position=0;using(var expected=AssemblyDefinition.ReadAssembly(bytes)){
    Apply(expected.MainModule);int methods,instructions;AssemblyStructure.RequireSame(expected,patched,out methods,out instructions);
    var xs=expected.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).ToArray();var ys=patched.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Where(m=>m.HasBody).ToArray();
    Need(xs.Length==ys.Length,"Method body count changed");
    for(int n=0;n<xs.Length;n++){
     Need(xs[n].Body.InitLocals==ys[n].Body.InitLocals,"Local initialization changed");
     for(int h=0;h<xs[n].Body.ExceptionHandlers.Count;h++){
      var a=xs[n].Body.ExceptionHandlers[h];var b=ys[n].Body.ExceptionHandlers[h];
      Need((a.CatchType==null?null:a.CatchType.FullName)==(b.CatchType==null?null:b.CatchType.FullName)&&xs[n].Body.Instructions.IndexOf(a.FilterStart)==ys[n].Body.Instructions.IndexOf(b.FilterStart),"Exception catch/filter changed");
     }
    }
   }
  }
  var before=Target(original.MainModule);var after=Target(patched.MainModule);after.Body=before.Body;
  foreach(var field in after.DeclaringType.Fields.Where(x=>x.Name.StartsWith(Prefix)).ToArray())after.DeclaringType.Fields.Remove(field);
  foreach(var method in after.DeclaringType.Methods.Where(x=>x.Name.StartsWith(Prefix)).ToArray())after.DeclaringType.Methods.Remove(method);
  return 3;
 }
}
