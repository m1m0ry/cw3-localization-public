using System;using Mono.Cecil;
class PatchEnumeratorDispose {
 static void Main(string[] args){var resolver=new DefaultAssemblyResolver();resolver.AddSearchDirectory(args[2]);using(var asm=AssemblyDefinition.ReadAssembly(args[0],new ReaderParameters{AssemblyResolver=resolver})){int count=EnumeratorDisposePatch.Apply(asm.MainModule);asm.Write(args[1]);Console.WriteLine("Removed "+count+" BCL enumerator disposal boxes; traversal and original enumerator locals preserved.");}}
}
