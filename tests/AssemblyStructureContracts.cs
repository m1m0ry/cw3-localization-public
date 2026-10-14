using System;
using Mono.Cecil;
using Mono.Cecil.Cil;

class AssemblyStructureContracts {
 static AssemblyDefinition Fixture(){
  var asm=AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("Fixture",new Version(1,0)),"Fixture",ModuleKind.Dll);
  var module=asm.MainModule;var type=new TypeDefinition("","Original",TypeAttributes.Public,module.TypeSystem.Object);module.Types.Add(type);
  type.Fields.Add(new FieldDefinition("First",FieldAttributes.Public,module.TypeSystem.Int32));
  type.Fields.Add(new FieldDefinition("Second",FieldAttributes.Public,module.TypeSystem.Int32));
  var method=new MethodDefinition("Execute",MethodAttributes.Public|MethodAttributes.Static,module.TypeSystem.Void);type.Methods.Add(method);
  var il=method.Body.GetILProcessor();var finish=il.Create(OpCodes.Ret);var target=il.Create(OpCodes.Nop);var handler=il.Create(OpCodes.Pop);
  il.Append(il.Create(OpCodes.Nop));il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Brtrue_S,target));
  il.Append(il.Create(OpCodes.Ldc_I4_0));il.Append(il.Create(OpCodes.Switch,new[]{target}));il.Append(target);
  il.Append(il.Create(OpCodes.Leave_S,finish));il.Append(handler);il.Append(il.Create(OpCodes.Leave_S,finish));il.Append(finish);
  method.Body.Variables.Add(new VariableDefinition(module.TypeSystem.Int32));
  method.Body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Catch){CatchType=module.TypeSystem.Object,TryStart=method.Body.Instructions[0],TryEnd=handler,HandlerStart=handler,HandlerEnd=finish});
  var nested=new TypeDefinition("","Nested",TypeAttributes.NestedPublic|TypeAttributes.Abstract,module.TypeSystem.Object);type.NestedTypes.Add(nested);
  nested.Methods.Add(new MethodDefinition("Bodyless",MethodAttributes.Public|MethodAttributes.Abstract|MethodAttributes.Virtual,module.TypeSystem.Void));
  return asm;
 }
 static MethodDefinition Method(AssemblyDefinition asm){return asm.MainModule.Types[1].Methods[0];}
 static void Rejected(string description,Action<AssemblyDefinition> change){
  using(var before=Fixture())using(var after=Fixture()){
   change(after);int methods,instructions;bool refused=false;
   try{AssemblyStructure.RequireSame(before,after,out methods,out instructions);}catch(Exception){refused=true;}
   if(!refused)throw new Exception("Accepted "+description);
  }
 }
 static void Main(){
  using(var before=Fixture())using(var after=Fixture()){
   var body=Method(after).Body;body.Instructions[2].OpCode=OpCodes.Brtrue;body.Instructions[6].OpCode=OpCodes.Leave;body.Instructions[8].OpCode=OpCodes.Leave;
   int methods,instructions;AssemblyStructure.RequireSame(before,after,out methods,out instructions);
   if(methods!=2||instructions!=10)throw new Exception("Nested/bodyless methods or normalized branches lost");
  }
  Rejected("nested type removal",a=>a.MainModule.Types[1].NestedTypes.Clear());
  Rejected("type identity",a=>a.MainModule.Types[1].Name="Changed");
  Rejected("field order",a=>{var fields=a.MainModule.Types[1].Fields;var first=fields[0];fields.RemoveAt(0);fields.Add(first);});
  Rejected("method signature",a=>Method(a).ReturnType=a.MainModule.TypeSystem.Int32);
  Rejected("branch target",a=>Method(a).Body.Instructions[2].Operand=Method(a).Body.Instructions[9]);
  Rejected("switch target",a=>Method(a).Body.Instructions[4].Operand=new[]{Method(a).Body.Instructions[9]});
  Rejected("opcode",a=>Method(a).Body.Instructions[1].OpCode=OpCodes.Ldc_I4_1);
  Rejected("local type",a=>Method(a).Body.Variables[0].VariableType=a.MainModule.TypeSystem.String);
  Rejected("exception handler count",a=>Method(a).Body.ExceptionHandlers.Clear());
  Rejected("exception range",a=>Method(a).Body.ExceptionHandlers[0].TryStart=Method(a).Body.Instructions[1]);
  Console.WriteLine("PASS shared assembly comparison: normalized branches, nested/bodyless methods and structural/IL rejection boundaries");
 }
}
