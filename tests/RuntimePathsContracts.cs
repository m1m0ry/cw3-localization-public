using System;using System.IO;
namespace UnityEngine {public static class Application {public static string persistentDataPath;}}
internal static class CW3BuildInfo {internal const bool NativeMac=false;}
class RuntimePathsContracts {
 static void Need(bool condition,string reason){if(!condition)throw new Exception(reason);}
 static void Reject(Action action){try{action();}catch(FormatException){return;}throw new Exception("Unknown installation layout accepted");}
 static void Main(string[] args){
  string root=Path.Combine(Path.GetFullPath(args[0]),"runtime-paths-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
  try{
   string win=Path.Combine(root,"Windows 游戏"),mac=Path.Combine(root,"Mac 游戏"),app=Path.Combine(mac,"CW3.app");
   string winHelper=Path.Combine(win,"CW3_Data/Managed/CW3Runtime.dll"),macHelper=Path.Combine(mac,"CW3Localization/Runtime/CW3ExternalRuntime.dll");
   var windows=RuntimePaths.Resolve(winHelper,false,null);
   Need(windows.Data==Path.Combine(win,"CW3_Data")&&windows.Content==Path.Combine(win,"CW3Localization")&&windows.State==windows.Content,"Windows keeps its existing sidecar contract");
   string user=Path.Combine(root,"User Data");var native=RuntimePaths.Resolve(macHelper,true,user);
   Need(native.Data==Path.Combine(app,"Contents/Resources/Data")&&native.Content==Path.Combine(mac,"CW3Localization")&&native.State==Path.Combine(user,"CW3Localization"),"Native Data, sibling content and user state are distinct");
   Need(!Directory.Exists(native.State)&&!Directory.Exists(mac),"Resolving paths never creates installation or state files");
   Need(native.EnsureState(),"Native external state can be created");File.WriteAllText(Path.Combine(native.State,"probe.json"),"state");
   Need(!Directory.Exists(app)&&!Directory.Exists(native.Content),"State writes never create bundle or package content");
   Reject(()=>RuntimePaths.Resolve(macHelper,false,user));Reject(()=>RuntimePaths.Resolve(winHelper,true,user));
   Reject(()=>RuntimePaths.Resolve(Path.Combine(app,"Contents/Managed/CW3Runtime.dll"),true,user));
   Reject(()=>RuntimePaths.Resolve(Path.Combine(mac,"Other/Runtime/CW3ExternalRuntime.dll"),true,user));
   Reject(()=>RuntimePaths.Resolve("CW3_Data/Managed/CW3Runtime.dll",false,user));
   foreach(string invalid in new[]{null,"relative",app,Path.Combine(app,"Contents"),app.ToUpperInvariant(),mac}){
    var unavailable=RuntimePaths.Resolve(macHelper,true,invalid);Need(unavailable.State==null&&!unavailable.EnsureState(),"Unsafe or missing state has no writable fallback");
    Need(unavailable.Data==native.Data&&unavailable.Content==native.Content,"State failure preserves read-only roots");
   }
   string blocked=Path.Combine(root,"blocked");File.WriteAllText(blocked,"keep");var denied=RuntimePaths.Resolve(macHelper,true,blocked);
   Need(!denied.EnsureState()&&File.ReadAllText(blocked)=="keep"&&!Directory.Exists(app)&&!Directory.Exists(native.Content),"State creation failure cannot overwrite its blocker or fall back into the installation");
   Console.WriteLine("PASS runtime roots: exact Windows/Mac layouts, platform mismatch rejection, external state and no bundle fallback");
  }finally{Directory.Delete(root,true);}
 }
}
