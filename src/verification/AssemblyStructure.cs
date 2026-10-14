using System;
using System.Linq;
using System.Collections.Generic;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Compare only after each stage has reversed its own explicitly allowed edits.
// No exclusions belong here: rendering, runtime and debug own their reversal rules.
internal static class AssemblyStructure {
 internal static IEnumerable<TypeDefinition> Types(TypeDefinition t){yield return t;foreach(var n in t.NestedTypes)foreach(var u in Types(n))yield return u;}
 static List<Instruction> Instructions(MethodDefinition m){return m.HasBody?m.Body.Instructions.ToList():new List<Instruction>();}
 static string Op(Instruction i,List<Instruction> list){
  string name=i.OpCode.Name;if(name.EndsWith(".s")&&i.Operand is Instruction)name=name.Substring(0,name.Length-2);
  object operand=i.Operand;
  if(operand is Instruction)operand="target:"+list.IndexOf((Instruction)operand);
  else if(operand is Instruction[])operand=String.Join(",",((Instruction[])operand).Select(x=>list.IndexOf(x).ToString()).ToArray());
  else if(operand is byte[])operand=BitConverter.ToString((byte[])operand);
  return name+" "+(operand==null?"":operand.ToString());
 }
 static void Require(bool b,string msg){if(!b)throw new Exception(msg);}
 internal static void RequireSame(AssemblyDefinition old,AssemblyDefinition patch,out int methods,out int instructions){
  methods=0;instructions=0;
  var ot=old.MainModule.Types.SelectMany(Types).ToList();var nt=patch.MainModule.Types.SelectMany(Types).ToList();
  Require(ot.Count==nt.Count,"type count");
  for(int ti=0;ti<ot.Count;ti++){
   var t=ot[ti];var u=nt[ti];
   Require(t.FullName==u.FullName&&t.Attributes==u.Attributes,"type identity");
   Require(t.Fields.Select(x=>x.FullName+":"+x.Attributes).SequenceEqual(u.Fields.Select(x=>x.FullName+":"+x.Attributes)),"fields: "+t.FullName);
   Require(t.Methods.Count==u.Methods.Count,"method count");
   for(int mi=0;mi<t.Methods.Count;mi++){
    var m=t.Methods[mi];var n=u.Methods[mi];Require(m.FullName==n.FullName&&m.Attributes==n.Attributes,"method identity");
    var x=Instructions(m);var y=Instructions(n);
    Require(x.Select(i=>Op(i,x)).SequenceEqual(y.Select(i=>Op(i,y))),"logic changed: "+m.FullName);
    if(m.HasBody){Require(m.Body.ExceptionHandlers.Count==n.Body.ExceptionHandlers.Count,"EH count");
     for(int ei=0;ei<m.Body.ExceptionHandlers.Count;ei++){
      var e=m.Body.ExceptionHandlers[ei];var f=n.Body.ExceptionHandlers[ei];
      Require(e.HandlerType==f.HandlerType&&x.IndexOf(e.TryStart)==y.IndexOf(f.TryStart)&&x.IndexOf(e.TryEnd)==y.IndexOf(f.TryEnd)&&x.IndexOf(e.HandlerStart)==y.IndexOf(f.HandlerStart)&&x.IndexOf(e.HandlerEnd)==y.IndexOf(f.HandlerEnd),"EH ranges");
     }
     Require(m.Body.Variables.Select(v=>v.VariableType.FullName).SequenceEqual(n.Body.Variables.Select(v=>v.VariableType.FullName)),"locals");
    }
    methods++;instructions+=x.Count;
   }
  }
 }
}
