using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;

// Audited outer finally: original catch/finally blocks, return values and exceptions survive.
internal static class MissionScopePatch {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 internal static void Wrap(MethodDefinition method,MethodReference begin,MethodReference end){
  var body=method.Body;var il=body.GetILProcessor();var start=body.Instructions[0];
  Need(body.ExceptionHandlers.All(e=>e.TryEnd!=null&&e.HandlerEnd!=null),"Explicit native EH boundaries required");
  VariableDefinition result=null;if(method.ReturnType.MetadataType!=MetadataType.Void){result=new VariableDefinition(method.ReturnType);body.Variables.Add(result);}
  var finish=il.Create(OpCodes.Call,end);var exit=result==null?il.Create(OpCodes.Ret):il.Create(OpCodes.Ldloc,result);
  foreach(var ret in body.Instructions.Where(i=>i.OpCode==OpCodes.Ret).ToArray()){
   if(result==null){ret.OpCode=OpCodes.Leave;ret.Operand=exit;}
   else{ret.OpCode=OpCodes.Stloc;ret.Operand=result;il.InsertAfter(ret,il.Create(OpCodes.Leave,exit));}
  }
  il.InsertBefore(start,il.Create(OpCodes.Call,begin));il.Append(finish);il.Append(il.Create(OpCodes.Endfinally));il.Append(exit);if(result!=null)il.Append(il.Create(OpCodes.Ret));
  body.ExceptionHandlers.Add(new ExceptionHandler(ExceptionHandlerType.Finally){TryStart=start,TryEnd=finish,HandlerStart=finish,HandlerEnd=exit});
 }
 internal static void Unwrap(MethodDefinition method){
  var body=method.Body;var instructions=body.Instructions;var scope=body.ExceptionHandlers.Last();
  Need(scope.HandlerType==ExceptionHandlerType.Finally&&scope.TryStart==instructions[1]&&scope.TryEnd==scope.HandlerStart,"Mission scope boundaries");
  Need(instructions[0].OpCode==OpCodes.Call&&((MethodReference)instructions[0].Operand).FullName=="System.Void CW3Runtime::BeginMissionLoad()","Mission scope entry");
  var finish=scope.HandlerStart;var exit=scope.HandlerEnd;int index=instructions.IndexOf(finish);
  Need(finish.OpCode==OpCodes.Call&&((MethodReference)finish.Operand).FullName=="System.Void CW3Runtime::EndMissionLoad()"&&instructions[index+1].OpCode==OpCodes.Endfinally&&instructions[index+2]==exit,"Mission scope cleanup");
  bool value=method.ReturnType.MetadataType!=MetadataType.Void;var result=value?body.Variables.Last():null;
  Need(value?exit.OpCode==OpCodes.Ldloc&&exit.Operand==result&&instructions[index+3].OpCode==OpCodes.Ret&&instructions.Count==index+4:exit.OpCode==OpCodes.Ret&&instructions.Count==index+3,"Mission scope return");
  foreach(var leave in instructions.Where(i=>i.OpCode==OpCodes.Leave&&i.Operand==exit).ToArray()){
   if(value){int at=instructions.IndexOf(leave);var ret=instructions[at-1];Need(ret.OpCode==OpCodes.Stloc&&ret.Operand==result,"Mission return value");ret.OpCode=OpCodes.Ret;ret.Operand=null;instructions.Remove(leave);}
   else{leave.OpCode=OpCodes.Ret;leave.Operand=null;}
  }
  body.ExceptionHandlers.Remove(scope);while(instructions.Last()!=finish)instructions.RemoveAt(instructions.Count-1);instructions.Remove(finish);instructions.RemoveAt(0);if(value)body.Variables.Remove(result);
 }
}
