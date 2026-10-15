using System;using System.IO;using UnityEngine;

// Native implementation is outside the signed app; Windows keeps Data/Managed.
internal sealed class RuntimePaths {
 internal readonly string Data,Content,State;
 internal readonly bool NativeMac;
 static RuntimePaths current;
 RuntimePaths(string data,string content,string state,bool nativeMac){Data=data;Content=content;State=state;NativeMac=nativeMac;}
 internal static RuntimePaths Current {get{
  if(current==null){bool nativeMac=CW3BuildInfo.NativeMac;string persistent=null;
   if(nativeMac)try{persistent=Application.persistentDataPath;}catch(Exception){/* Keep read-only content usable if Unity cannot supply a state root. */}
   current=Resolve(typeof(RuntimePaths).Assembly.Location,nativeMac,persistent);
  }return current;
 }}
 internal static RuntimePaths Resolve(string helper,bool nativeMac,string persistent){
  if(String.IsNullOrEmpty(helper)||!Path.IsPathRooted(helper))throw new FormatException("Runtime helper path");
  helper=Path.GetFullPath(helper);DirectoryInfo install,bundle=null,data;string content;
  if(nativeMac){
   var runtime=Directory.GetParent(helper);var sidecar=runtime==null?null:runtime.Parent;install=sidecar==null?null:sidecar.Parent;
   if(Path.GetFileName(helper)!="CW3ExternalRuntime.dll"||runtime==null||runtime.Name!="Runtime"||sidecar==null||sidecar.Name!="CW3Localization"||install==null)throw new FormatException("Native external runtime layout");
   bundle=new DirectoryInfo(Path.Combine(install.FullName,"CW3.app"));
   data=new DirectoryInfo(Path.Combine(bundle.FullName,"Contents/Resources/Data"));content=sidecar.FullName;
  }else{
   var managed=Directory.GetParent(helper);data=managed==null?null:managed.Parent;
   if(Path.GetFileName(helper)!="CW3Runtime.dll"||managed==null||managed.Name!="Managed"||data==null)throw new FormatException("Runtime Managed layout");
   if(data.Name!="CW3_Data"||data.Parent==null)throw new FormatException("Windows Data layout");
   install=data.Parent;content=Path.Combine(install.FullName,"CW3Localization");
  }
  string state=content;
  if(nativeMac){
   state=null;
   try{
    if(!String.IsNullOrEmpty(persistent)&&Path.IsPathRooted(persistent)){
     string candidate=Path.GetFullPath(Path.Combine(persistent,"CW3Localization"));
     if(!Within(candidate,bundle.FullName)&&!Within(candidate,content)){NoLinks(candidate);state=candidate;}
    }
   }catch(Exception){/* An unavailable state directory must not disable default translation. */}
  }
  return new RuntimePaths(data.FullName,content,state,nativeMac);
 }
 static bool Within(string path,string root){return String.Equals(path,root,StringComparison.OrdinalIgnoreCase)||path.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase);}
 static void NoLinks(string path){for(var at=new DirectoryInfo(path);at!=null;at=at.Parent)if((Directory.Exists(at.FullName)||File.Exists(at.FullName))&&(File.GetAttributes(at.FullName)&FileAttributes.ReparsePoint)!=0)throw new IOException("State path link");}
 internal bool EnsureState(){
  if(State==null)return false;
  try{if(NativeMac)NoLinks(State);Directory.CreateDirectory(State);return true;}catch(Exception){return false;}
 }
}
