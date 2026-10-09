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
  foreach(string name in new[]{"UILabel","UISprite","UITexture","UIDrawCall"}){var method=patch.MainModule.GetType(name).Methods.Single(x=>x.Name==(name=="UIDrawCall"?"OnWillRenderObject":"get_material"));var ins=method.Body.Instructions;int found=0;for(int k=0;k<ins.Count-2;k++){var mr=ins[k+1].Operand as MethodReference;if(ins[k].OpCode==OpCodes.Ldarg_0&&ins[k+1].OpCode==OpCodes.Call&&mr!=null&&mr.DeclaringType.FullName=="CW3Rendering"&&mr.Name==(name=="UIDrawCall"?"SyncDrawCall":"Ordered")&&ins[k+2].OpCode==OpCodes.Ret){ins[k].OpCode=OpCodes.Ret;ins[k].Operand=null;ins.RemoveAt(k+2);ins.RemoveAt(k+1);found++;}}Require(found>0,"missing render wrapper");}
  var shield=patch.MainModule.GetType("SystemManager").Methods.Single(x=>x.Name=="ShowStorySystemMessageForPlanet");var names=patch.MainModule.GetType("PlanetManager").Methods.Single(x=>x.Name=="get_planetName");int fixedNames=0;foreach(var i in shield.Body.Instructions){var mr=i.Operand as MethodReference;if(mr!=null&&mr.DeclaringType.Name=="GalObjectManager"&&mr.Name=="get_GUID"){i.Operand=names;fixedNames++;}}Require(fixedNames==12,"shield dispatch count");
  foreach(var line in System.IO.File.ReadAllLines(a[2])){
   var c=line.Split('\t');var originalMethod=(MethodDefinition)old.MainModule.LookupToken(Int32.Parse(c[0]));var m=patch.MainModule.Types.SelectMany(t=>All(t)).SelectMany(t=>t.Methods).Single(t=>t.FullName==originalMethod.FullName);var i=m.Body.Instructions[Int32.Parse(c[1])];
   string src=System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(c[2]));string dst=System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(c[3]));
   Require(i.OpCode==OpCodes.Ldstr&&(string)i.Operand==dst,"translated display site mismatch");i.Operand=src;
  }
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
  Console.WriteLine("PASS: original types, field order, method signatures, "+methods+" methods and "+instructions+" IL instructions unchanged after reversing exact rendering wrappers, 12 GUID dispatches and listed display strings.");
 }
}
