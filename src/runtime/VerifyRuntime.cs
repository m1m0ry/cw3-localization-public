using System;
using System.Linq;
using System.Collections.Generic;
using Mono.Cecil;
using Mono.Cecil.Cil;
class Verify {
 static List<Instruction> Clean(MethodDefinition m){return m.HasBody?m.Body.Instructions.ToList():new List<Instruction>();}
 static string Op(Instruction i,List<Instruction> list){
  string name=i.OpCode.Name;if(name.EndsWith(".s")&&i.Operand is Instruction)name=name.Substring(0,name.Length-2);
  object operand=i.Operand;
  if(operand is Instruction)operand="target:"+list.IndexOf((Instruction)operand);
  else if(operand is Instruction[])operand=String.Join(",",((Instruction[])operand).Select(x=>list.IndexOf(x).ToString()).ToArray());
  else if(operand is byte[])operand=BitConverter.ToString((byte[])operand);
  return name+" "+(operand==null?"":operand.ToString());
 }
 static void Require(bool b,string msg){if(!b)throw new Exception(msg);}
 static System.Collections.Generic.IEnumerable<TypeDefinition> All(TypeDefinition t){yield return t;foreach(var n in t.NestedTypes)foreach(var u in All(n))yield return u;}
 static void Main(string[] a){
  var old=AssemblyDefinition.ReadAssembly(a[0]);var patch=AssemblyDefinition.ReadAssembly(a[1]);int methods=0,instructions=0;
  var records=System.IO.File.ReadAllLines(a[2]).Select(line=>line.Split('\t')).ToArray();
  foreach(var c in records.Where(c=>c[4]=="mission_scope"))MissionScopePatch.Unwrap((MethodDefinition)patch.MainModule.LookupToken(Int32.Parse(c[0])));
  Require(records.Count(c=>c[4]=="main_menu_click")==1,"One main menu receiver repair");MainMenuClickPatch.Reverse(old.MainModule,patch.MainModule);
  var audit=records.Where(c=>c[4]!="mission_scope"&&c[4]!="main_menu_click").GroupBy(c=>c[0]);
  foreach(var group in audit){var om=(MethodDefinition)old.MainModule.LookupToken(Int32.Parse(group.Key));var nm=patch.MainModule.Types.SelectMany(All).SelectMany(t=>t.Methods).Single(t=>t.FullName==om.FullName);var y=nm.Body.Instructions;int delta=0;foreach(var c in group.OrderBy(c=>Int32.Parse(c[1])).ThenByDescending(c=>Int32.Parse(c[2]))){int ix=Int32.Parse(c[1]),before=Int32.Parse(c[2]),after=Int32.Parse(c[3]);int at=ix+delta;for(int n=0;n<before;n++)y.RemoveAt(at);var original=om.Body.Instructions[ix];if(c[4]=="return"){Require(original.OpCode==OpCodes.Ret&&y[at].OpCode==OpCodes.Nop,"Return hook anchor");Require(after>=2&&y[at+after].OpCode==OpCodes.Ret,"Return hook exit");Require(y[at+after-1].OpCode==OpCodes.Call&&((MethodReference)y[at+after-1].Operand).DeclaringType.Name=="CW3Runtime","Return hook helper");y[at].OpCode=OpCodes.Ret;y[at].Operand=null;}else if(c[4]=="replace"){Require(((MethodReference)y[at].Operand).DeclaringType.Name=="CW3Runtime","Runtime call replacement");y[at].OpCode=original.OpCode;y[at].Operand=original.Operand;}else if(after==2&&original.OpCode==OpCodes.Ldstr){Require(y[at+1].OpCode==OpCodes.Ldstr&&(string)y[at+1].Operand==(string)original.Operand,"ldstr source fallback");y[at].Operand=original.Operand;}for(int n=0;n<after;n++)y.RemoveAt(at+1);}}
  var ot=old.MainModule.Types.SelectMany(t=>All(t)).ToList();var nt=patch.MainModule.Types.SelectMany(t=>All(t)).ToList();
  Require(ot.Count==nt.Count,"type count");
  for(int ti=0;ti<ot.Count;ti++){
   var t=ot[ti];var u=nt[ti];
   Require(t.FullName==u.FullName&&t.Attributes==u.Attributes,"type identity");
   Require(t.Fields.Select(x=>x.FullName+":"+x.Attributes).SequenceEqual(u.Fields.Select(x=>x.FullName+":"+x.Attributes)),"fields: "+t.FullName);
   Require(t.Methods.Count==u.Methods.Count,"method count");
   for(int mi=0;mi<t.Methods.Count;mi++){
    var m=t.Methods[mi];var n=u.Methods[mi];Require(m.FullName==n.FullName&&m.Attributes==n.Attributes,"method identity");
    var x=Clean(m);var y=Clean(n);
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
  Console.WriteLine("PASS: original types, field order, method signatures, "+methods+" methods and "+instructions+" IL instructions unchanged after reverting audited bridge edits the mission cleanup scope and three main menu owner receivers.");
 }
}
