using System;using Mono.Cecil;
class VerifyEnumeratorDispose {
 static void Main(string[] args){using(var before=AssemblyDefinition.ReadAssembly(args[0]))using(var after=AssemblyDefinition.ReadAssembly(args[1])){int count=EnumeratorDisposePatch.Reverse(before.MainModule,after.MainModule),methods,instructions;AssemblyStructure.RequireSame(before,after,out methods,out instructions);Console.WriteLine("Verified "+count+" enumerator disposal boxes; all "+methods+" methods and "+instructions+" original instructions unchanged after reversal.");}}
}
