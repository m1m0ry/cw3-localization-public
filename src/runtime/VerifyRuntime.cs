using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;
class Verify {
 static void Require(bool b,string msg){if(!b)throw new Exception(msg);}
 static void Main(string[] a){
  var old=AssemblyDefinition.ReadAssembly(a[0]);var patch=AssemblyDefinition.ReadAssembly(a[1]);int methods=0,instructions=0;
  var records=System.IO.File.ReadAllLines(a[2]).Select(line=>line.Split('\t')).ToArray();
  foreach(var c in records.Where(c=>c[4]=="mission_scope"))MissionScopePatch.Unwrap((MethodDefinition)patch.MainModule.LookupToken(Int32.Parse(c[0])));
  Require(records.Count(c=>c[4]=="main_menu_click")==1,"One main menu receiver repair");MainMenuClickPatch.Reverse(old.MainModule,patch.MainModule);
  var audit=records.Where(c=>c[4]!="mission_scope"&&c[4]!="main_menu_click").GroupBy(c=>c[0]);
  foreach(var group in audit){var om=(MethodDefinition)old.MainModule.LookupToken(Int32.Parse(group.Key));var nm=patch.MainModule.Types.SelectMany(AssemblyStructure.Types).SelectMany(t=>t.Methods).Single(t=>t.FullName==om.FullName);var y=nm.Body.Instructions;int delta=0;foreach(var c in group.OrderBy(c=>Int32.Parse(c[1])).ThenByDescending(c=>Int32.Parse(c[2]))){int ix=Int32.Parse(c[1]),before=Int32.Parse(c[2]),after=Int32.Parse(c[3]);int at=ix+delta;for(int n=0;n<before;n++)y.RemoveAt(at);var original=om.Body.Instructions[ix];if(c[4]=="return"){Require(original.OpCode==OpCodes.Ret&&y[at].OpCode==OpCodes.Nop,"Return hook anchor");Require(after>=2&&y[at+after].OpCode==OpCodes.Ret,"Return hook exit");Require(y[at+after-1].OpCode==OpCodes.Call&&((MethodReference)y[at+after-1].Operand).DeclaringType.Name=="CW3Runtime","Return hook helper");y[at].OpCode=OpCodes.Ret;y[at].Operand=null;}else if(c[4]=="replace"){Require(((MethodReference)y[at].Operand).DeclaringType.Name=="CW3Runtime","Runtime call replacement");y[at].OpCode=original.OpCode;y[at].Operand=original.Operand;}else if(after==2&&original.OpCode==OpCodes.Ldstr){Require(y[at+1].OpCode==OpCodes.Ldstr&&(string)y[at+1].Operand==(string)original.Operand,"ldstr source fallback");y[at].Operand=original.Operand;}for(int n=0;n<after;n++)y.RemoveAt(at+1);}}
  AssemblyStructure.RequireSame(old,patch,out methods,out instructions);
  Console.WriteLine("PASS: original types, field order, method signatures, "+methods+" methods and "+instructions+" IL instructions unchanged after reverting audited bridge edits the mission cleanup scope and three main menu owner receivers.");
 }
}
