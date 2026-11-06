// Test-only exact IL replay over source-built array/type stubs. No original
// game implementation or map data is stored in this source fixture.
using System;using System.Linq;using System.Collections.Generic;using Mono.Cecil;using Mono.Cecil.Cil;
class PrepareSprayerLosProbe {
 static ModuleDefinition dst; static Dictionary<string,TypeDefinition> ts;
 static IEnumerable<TypeDefinition> Types(TypeDefinition t){yield return t;foreach(var n in t.NestedTypes)foreach(var x in Types(n))yield return x;}
 static TypeReference T(TypeReference t){if(t is ByReferenceType)return new ByReferenceType(T(((ByReferenceType)t).ElementType));if(t is ArrayType)return new ArrayType(T(((ArrayType)t).ElementType));TypeDefinition v;if(ts.TryGetValue(t.FullName,out v))return v;return dst.ImportReference(t);}
 static MethodReference M(MethodReference m){TypeDefinition v;if(ts.TryGetValue(m.DeclaringType.FullName,out v))return v.Methods.Single(x=>x.Name==m.Name&&x.Parameters.Count==m.Parameters.Count);return dst.ImportReference(m);}
 static FieldReference F(FieldReference f){TypeDefinition v;if(ts.TryGetValue(f.DeclaringType.FullName,out v))return v.Fields.Single(x=>x.Name==f.Name);return dst.ImportReference(f);}
 static void Clone(MethodDefinition s,MethodDefinition d,bool staticSelf){d.Body=new MethodBody(d){InitLocals=s.Body.InitLocals,MaxStackSize=s.Body.MaxStackSize+6};var vs=new Dictionary<VariableDefinition,VariableDefinition>();foreach(var v in s.Body.Variables){var n=new VariableDefinition(T(v.VariableType));vs[v]=n;d.Body.Variables.Add(n);}var map=new Dictionary<Instruction,Instruction>();foreach(var i in s.Body.Instructions){var n=Instruction.Create(OpCodes.Nop);n.OpCode=i.OpCode;map[i]=n;d.Body.Instructions.Add(n);}foreach(var i in s.Body.Instructions){object o=i.Operand;if(o is Instruction)o=map[(Instruction)o];else if(o is Instruction[])o=((Instruction[])o).Select(x=>map[x]).ToArray();else if(o is VariableDefinition)o=vs[(VariableDefinition)o];else if(o is ParameterDefinition)o=d.Parameters[((ParameterDefinition)o).Index+(staticSelf?1:0)];else if(o is MethodReference)o=M((MethodReference)o);else if(o is FieldReference)o=F((FieldReference)o);else if(o is TypeReference)o=T((TypeReference)o);map[i].Operand=o;}if(s.Body.ExceptionHandlers.Count!=0)throw new Exception("Unexpected EH in "+s.FullName);}
 static void Main(string[]a){using(var original=AssemblyDefinition.ReadAssembly(a[0]))using(var patched=AssemblyDefinition.ReadAssembly(a[1]))using(var skeleton=AssemblyDefinition.ReadAssembly(a[2])){
 dst=skeleton.MainModule;ts=dst.Types.SelectMany(Types).ToDictionary(t=>t.FullName);
 Clone(original.MainModule.GetType("SprayerBarrelManager").Methods.Single(m=>m.Name=="FindNearestEnemies"),ts["SprayerQueries"].Methods.Single(m=>m.Name=="Original"),true);
 Clone(patched.MainModule.GetType("SprayerBarrelManager").Methods.Single(m=>m.Name=="FindNearestEnemies"),ts["SprayerQueries"].Methods.Single(m=>m.Name=="Candidate"),true);
 foreach(var m in original.MainModule.GetType("Util").Methods.Where(m=>m.Name=="hasLOS"||m.Name=="heightOK"))Clone(m,ts["Util"].Methods.Single(x=>x.Name==m.Name&&x.Parameters.Count==m.Parameters.Count),false);
 skeleton.Write(a[3]);
 }}
}
