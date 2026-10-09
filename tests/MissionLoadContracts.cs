using System;using System.IO;using System.Linq;using System.Reflection;using Mono.Cecil;

class MissionLoadContracts {
 static void Main(string[] args){
  string output=Path.Combine(args[1],"MissionLoadFixture.patched.dll");var assembly=AssemblyDefinition.ReadAssembly(args[0]);var runtime=assembly.MainModule.GetType("CW3Runtime");var fixture=assembly.MainModule.GetType("MissionLoadFixture");
  foreach(var method in fixture.Methods.Where(m=>m.Name=="Load"||m.Name=="VoidLoad"))MissionScopePatch.Wrap(method,runtime.Methods.Single(m=>m.Name=="BeginMissionLoad"),runtime.Methods.Single(m=>m.Name=="EndMissionLoad"));
  assembly.Write(output);Assembly.LoadFile(Path.GetFullPath(output)).GetType("MissionLoadFixture").GetMethod("Verify").Invoke(null,null);
  // Also exercise the exact inverse used by the original-game semantic gate.
  var patched=AssemblyDefinition.ReadAssembly(output);foreach(var method in patched.MainModule.GetType("MissionLoadFixture").Methods.Where(m=>m.Name=="Load"||m.Name=="VoidLoad"))MissionScopePatch.Unwrap(method);
  string reverted=Path.Combine(args[1],"MissionLoadFixture.reverted.dll");patched.Write(reverted);
 }
}
