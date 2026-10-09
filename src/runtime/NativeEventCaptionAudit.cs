using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
// CW3 2.12 ShowEvent has separate locals: V_2 is the icon key, V_3/V_4 are captions.
internal static class NativeEventCaptionAudit {
 internal static void Require(MethodDefinition m,Instruction source){CaptionConsumer(m,source);}
 internal static Instruction CaptionConsumer(MethodDefinition m,Instruction source){return Consumer(m,source,true);}
 internal static Instruction IconConsumer(MethodDefinition m,Instruction source){return Consumer(m,source,false);}
 static Instruction Consumer(MethodDefinition m,Instruction source,bool caption){
  if(m.FullName!="System.Void GameEventManager::ShowEvent(GameEventManager/GAME_EVENT,System.String,UnityEngine.Vector2)")throw new Exception("Native event caption method");
  var xs=m.Body.Instructions;int at=xs.IndexOf(source);if(at<0||at+1>=xs.Count||source.OpCode!=OpCodes.Ldstr)throw new Exception("Native event caption literal");
  var store=xs[at+1];bool display=store.OpCode==OpCodes.Stloc_3||store.OpCode==OpCodes.Stloc_S&&((VariableDefinition)store.Operand).Index==4;
  if(caption?!display:store.OpCode!=OpCodes.Stloc_2)throw new Exception("Native event caption/icon local mismatch");
  var calls=xs.Where(i=>i.Operand is MethodReference&&((MethodReference)i.Operand).FullName=="System.Void GameEventManager::ShowEvent(UnityEngine.Color,UnityEngine.Color,System.String,System.String,System.String,UnityEngine.Vector2)").ToArray();
  if(calls.Length!=1)throw new Exception("Native event consumer count");int call=xs.IndexOf(calls[0]);
  if(call<4||xs[call-4].OpCode!=OpCodes.Ldloc_2||xs[call-3].OpCode!=OpCodes.Ldloc_3||!(xs[call-2].Operand is VariableDefinition)||xs[call-2].OpCode!=OpCodes.Ldloc_S||((VariableDefinition)xs[call-2].Operand).Index!=4)throw new Exception("Native event caption arguments");
  return calls[0];
 }
}
