// Test-only isolation: skip two Unity-dependent static initializers so the exact
// original search IL can run over synthetic terrain without launching the game.
using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class PreparePathWorkspaceProbe {static void Main(string[] a){var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(a[2]);using(var asm=AssemblyDefinition.ReadAssembly(a[0],new ReaderParameters{AssemblyResolver=resolver})){foreach(var name in new[]{"GameSpace","CrplCore"}){var t=asm.MainModule.GetType(name);var m=t.Methods.SingleOrDefault(x=>x.Name==".cctor");if(m!=null){m.Body=new MethodBody(m);m.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));}}asm.Write(a[1]);}}}
