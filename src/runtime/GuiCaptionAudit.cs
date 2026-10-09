using System;using System.Collections.Generic;using Mono.Cecil;using Mono.Cecil.Cil;
// Follow a declared ldstr to its consumer. Reject model writes, comparisons and unknown consumers.
internal static class GuiCaptionAudit {
 static int Count(StackBehaviour b){string s=b.ToString();if(s=="Pop0"||s=="Push0")return 0;if(s=="Varpop"||s=="Varpush"||s=="PopAll")throw new Exception("Unknown stack effect");return s.Split('_').Length;}
 static int Local(Instruction i,bool write){
  string op=i.OpCode.Name;if(!op.StartsWith(write?"stloc":"ldloc")||op.StartsWith("ldloca"))return -1;
  var v=i.Operand as VariableDefinition;if(v!=null)return v.Index;int n;return Int32.TryParse(op.Substring(6),out n)?n:-1;
 }
 internal static string Require(MethodDefinition method,Instruction source){return Consumer(method,source).Operand.ToString();}
 internal static Instruction Consumer(MethodDefinition method,Instruction source){
  var stack=new List<bool>();for(int n=0;n<32;n++)stack.Add(false);stack.Add(true);
  Func<int,List<bool>> pop=n=>{if(stack.Count<n)throw new Exception("Stack underflow");var v=stack.GetRange(stack.Count-n,n);stack.RemoveRange(stack.Count-n,n);return v;};
  var xs=method.Body.Instructions;int start=xs.IndexOf(source);
  bool captionArray=false;if(start>=2&&xs[start-1].OpCode.Name.StartsWith("ldc.i4")&&xs[start-2].OpCode==OpCodes.Dup)for(int k=start-3;k>=0&&k>=start-40;k--)if(xs[k].OpCode==OpCodes.Newarr){string type=((TypeReference)xs[k].Operand).FullName;captionArray=type=="System.Object"||type=="System.String";break;}
  for(int at=start+1;at<xs.Count&&at<start+180;at++){
   var i=xs[at];if(i.OpCode==OpCodes.Dup){stack.Add(stack[stack.Count-1]);continue;}
   var call=i.Operand as MethodReference;
   if(call!=null&&(i.OpCode==OpCodes.Call||i.OpCode==OpCodes.Callvirt||i.OpCode==OpCodes.Newobj)){
    int n=call.Parameters.Count+((call.HasThis&&i.OpCode!=OpCodes.Newobj)?1:0);var args=pop(n);bool used=args.Contains(true);
    if(used){
     if(call.DeclaringType.FullName=="System.String"&&call.Name=="Concat"){stack.Add(true);continue;}
     if(call.DeclaringType.FullName=="System.String"&&call.Name=="Format"&&args[0]&&!args.GetRange(1,args.Count-1).Contains(true)){stack.Add(true);continue;}
     bool gui=call.DeclaringType.FullName=="UnityEngine.GUI"||call.DeclaringType.FullName=="UnityEngine.GUILayout";bool label=call.DeclaringType.FullName=="UILabel"&&call.Name=="set_text"||call.DeclaringType.FullName=="InfoPanel"&&call.Name=="ShowInfoMessage";
     if(label||gui&&(call.Name=="Label"||call.Name=="Button"||call.Name=="Toggle"||call.Name=="Box"||call.Name=="Window")){
      int offset=call.HasThis?1:0;for(int k=0;k<call.Parameters.Count;k++)if(args[k+offset]&&call.Parameters[k].ParameterType.FullName!="System.String")throw new Exception("Not a caption parameter");if(stack.Contains(true))throw new Exception("Caption source has another consumer");return i;
     }
     throw new Exception("Literal consumed by "+call.FullName);
    }
    if(i.OpCode==OpCodes.Newobj||call.ReturnType.FullName!="System.Void")stack.Add(false);continue;
   }
   if(i.OpCode.FlowControl==FlowControl.Branch||i.OpCode.FlowControl==FlowControl.Cond_Branch||i.OpCode.FlowControl==FlowControl.Return||i.OpCode.FlowControl==FlowControl.Throw)throw new Exception("Control flow before caption consumer");
   int take=Count(i.OpCode.StackBehaviourPop);var consumed=pop(take);
   if(consumed.Contains(true)){
    int local=Local(i,true);
    if(local>=0){
     int read=-1;for(int k=0;k<xs.Count;k++)if(Local(xs[k],false)==local){if(read>=0)throw new Exception("Caption local has multiple readers");read=k;}
     if(read<=at)throw new Exception("Caption local reader not forward");
     for(int k=at+1;k<read;k++){if(xs[k].OpCode==OpCodes.Nop)continue;if(xs[k].OpCode.FlowControl==FlowControl.Branch&&Object.ReferenceEquals(xs[k].Operand,xs[read]))break;throw new Exception("Caption local has intervening logic");}
     stack.Add(true);at=read;continue;
    }
    if(captionArray&&i.OpCode==OpCodes.Stelem_Ref){
     if(consumed[2]){if(at!=start+1||stack.Count==0)throw new Exception("Caption array store pattern");stack[stack.Count-1]=true;}
     else if(!consumed[0])throw new Exception("Caption array identity");
     continue;
    }
    throw new Exception("Literal escapes caption into "+i.OpCode.Name);
   }
   for(int n=0;n<Count(i.OpCode.StackBehaviourPush);n++)stack.Add(false);
  }
  throw new Exception("No caption consumer");
 }
}
