using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Xml;
using UnityEngine;

// Stable signed entry points for the native Mac player. Only this project's
// fixed, user-owned local runtime may supply the implementation.
public static class CW3Runtime {
 delegate int GridCall(int selected,GUIContent[] text,int columns,GUIStyle style,GUILayoutOption[] options);
 [DllImport("libc")]static extern int lstat(string path,byte[] info);
 [DllImport("libc",EntryPoint="lstat$INODE64")]static extern int lstat_inode64(string path,byte[] info);
 [DllImport("libc")]static extern uint geteuid();
 static readonly Dictionary<string,Delegate> calls=new Dictionary<string,Delegate>();
 static Type implementation;
 static bool attempted;
 static string failure;
 static CW3BridgeNotice notice;
 static bool defaultStat;

 static int Stat(string path,byte[] info){
  // Intel libc keeps legacy lstat's uid at 12. Request the inode64 ABI whose
  // offsets match ARM's default lstat; that suffixed symbol is absent on ARM.
  if(!defaultStat)try{return lstat_inode64(path,info);}catch(EntryPointNotFoundException){defaultStat=true;}
  return lstat(path,info);
 }

 static void Owned(string path,bool directory){
  byte[] info=new byte[256];
  if(Stat(path,info)!=0)throw new IOException("External runtime path missing or unreadable");
  if(BitConverter.ToUInt32(info,16)!=geteuid())throw new IOException("External runtime owner differs from the game user");
  // Darwin's 64-bit stat stores st_mode at 4 and st_uid at 16. Same-user
  // ownership is the local trust boundary; other users must not be able to write.
  ushort mode=BitConverter.ToUInt16(info,4);
  if((mode&0xf000)!=(directory?0x4000:0x8000))throw new IOException("External runtime path is not a plain "+(directory?"directory":"file"));
  if((mode&0x12)!=0)throw new IOException("External runtime path is writable by another user");
 }
 static void Failed(string reason){
  if(failure==null){failure=reason;Debug.LogError("CW3Localization NOT ACTIVE: "+failure);}
 }
 static void ShowFailure(){
  if(failure==null||notice!=null)return;
  try{var go=new GameObject("CW3 localization failure");UnityEngine.Object.DontDestroyOnLoad(go);notice=go.AddComponent<CW3BridgeNotice>();}
  catch(Exception e){Debug.LogError("CW3Localization failure notice unavailable: "+e.GetType().Name);}
 }
 static void CheckInterface(Type target){
  const BindingFlags flags=BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly;
  foreach(MethodInfo method in typeof(CW3Runtime).GetMethods(flags)){
   if(method.Name=="BridgeStatus")continue;
   ParameterInfo[] parameters=method.GetParameters();Type[] types=new Type[parameters.Length];
   for(int i=0;i<types.Length;i++)types[i]=parameters[i].ParameterType;
   MethodInfo found=target.GetMethod(method.Name,flags,null,types,null);
   if(found==null||found.ReturnType!=method.ReturnType)throw new MissingMethodException("External runtime interface: "+method.Name);
  }
 }
 static Type Resolve(){
  if(attempted)return implementation;
  attempted=true;
  try{
   string self=Path.GetFullPath(typeof(CW3Runtime).Assembly.Location);
   var managed=Directory.GetParent(self);var data=managed==null?null:managed.Parent;
   var resources=data==null?null:data.Parent;var contents=resources==null?null:resources.Parent;
   var app=contents==null?null:contents.Parent;var install=app==null?null:app.Parent;
   if(Path.GetFileName(self)!="CW3Runtime.dll"||managed==null||managed.Name!="Managed"||data==null||data.Name!="Data"||resources==null||resources.Name!="Resources"||contents==null||contents.Name!="Contents"||app==null||app.Name!="CW3.app"||install==null)throw new IOException("Unexpected native CW3 layout");
   string content=Path.Combine(install.FullName,"CW3Localization");
   string directory=Path.Combine(content,"Runtime");
   string external=Path.Combine(directory,"CW3ExternalRuntime.dll");
   Owned(content,true);Owned(directory,true);Owned(external,false);
   if(new FileInfo(external).Length>12000000)throw new IOException("External runtime exceeds size bound");
   Assembly assembly=Assembly.LoadFrom(external);
   if(assembly.GetName().Name!="CW3ExternalRuntime"||Path.GetFullPath(assembly.Location)!=external)throw new IOException("Unexpected external runtime assembly");
   Type target=assembly.GetType("CW3Runtime",true);CheckInterface(target);implementation=target;
  }catch(Exception e){Failed(e.GetType().Name+": "+e.Message);}
  return implementation;
 }
 static T Call<T>(string name) where T:class{
  Delegate value=null;if(calls.TryGetValue(name,out value))return value as T;
  Type target=Resolve();
  if(target!=null)try{value=Delegate.CreateDelegate(typeof(T),target.GetMethod(name,BindingFlags.Public|BindingFlags.Static));}
  catch(Exception e){Failed("Bridge method "+name+": "+e.GetType().Name);ShowFailure();}
  calls[name]=value;return value as T;
 }
 public static string BridgeStatus(){Resolve();return failure??"ready";}

 public static void Boot(){var f=Call<Action>("Boot");if(f!=null)f();ShowFailure();}
 public static string Text(string id,string original){var f=Call<Func<string,string,string>>("Text");return f==null?original:f(id,original);}
 public static void PrepareLabel(object value){var f=Call<Action<object>>("PrepareLabel");if(f!=null)f(value);}
 public static string ForLabel(string text,object value){var f=Call<Func<string,object,string>>("ForLabel");return f==null?text:f(text,value);}
 public static bool LayoutButton(string text,GUILayoutOption[] options){var f=Call<Func<string,GUILayoutOption[],bool>>("LayoutButton");return f==null?GUILayout.Button(text,options):f(text,options);}
 public static bool LayoutStyledButton(string text,GUIStyle style,GUILayoutOption[] options){var f=Call<Func<string,GUIStyle,GUILayoutOption[],bool>>("LayoutStyledButton");return f==null?GUILayout.Button(text,style,options):f(text,style,options);}
 public static void SetMesh(TextMesh mesh,string original){var f=Call<Action<TextMesh,string>>("SetMesh");if(f==null)mesh.text=original;else f(mesh,original);}
 public static void SetNamedMesh(TextMesh mesh,string original,object owner){var f=Call<Action<TextMesh,string,object>>("SetNamedMesh");if(f==null)mesh.text=original;else f(mesh,original,owner);}
 public static string OriginalMesh(TextMesh mesh){var f=Call<Func<TextMesh,string>>("OriginalMesh");return f==null?mesh.text:f(mesh);}
 public static string ForName(string original,object owner){var f=Call<Func<string,object,string>>("ForName");return f==null?original:f(original,owner);}
 public static void RegisterSystemDocument(XmlDocument doc,string key,byte[] data){var f=Call<Action<XmlDocument,string,byte[]>>("RegisterSystemDocument");if(f!=null)f(doc,key,data);}
 public static void BeginMissionLoad(){var f=Call<Action>("BeginMissionLoad");if(f!=null)f();}
 public static byte[] CaptureMissionResource(byte[] data,string key){var f=Call<Func<byte[],string,byte[]>>("CaptureMissionResource");return f==null?data:f(data,key);}
 public static void RegisterMissionDocument(XmlDocument doc){var f=Call<Action<XmlDocument>>("RegisterMissionDocument");if(f!=null)f(doc);}
 public static void EndMissionLoad(){var f=Call<Action>("EndMissionLoad");if(f!=null)f();}
 public static void BindMessages(object owner,XmlNode node){var f=Call<Action<object,XmlNode>>("BindMessages");if(f!=null)f(owner,node);}
 public static void ClearMessages(object owner){var f=Call<Action<object>>("ClearMessages");if(f!=null)f(owner);}
 public static void MessageAdded(object owner){var f=Call<Action<object>>("MessageAdded");if(f!=null)f(owner);}
 public static void MessageRemoved(object owner,object message){var f=Call<Action<object,object>>("MessageRemoved");if(f!=null)f(owner,message);}
 public static string ForMessage(string original,object message){var f=Call<Func<string,object,string>>("ForMessage");return f==null?original:f(original,message);}
 public static string CaptureCrpl(string original,object core){var f=Call<Func<string,object,string>>("CaptureCrpl");return f==null?original:f(original,core);}
 public static void BindScriptConversation(int character,string text,object core){var f=Call<Action<int,string,object>>("BindScriptConversation");if(f!=null)f(character,text,core);}
 public static string ForGuiMessage(string original){var f=Call<Func<string,string>>("ForGuiMessage");return f==null?original:f(original);}
 public static void StyleLabel(string text,GUILayoutOption[] options,string role){var f=Call<Action<string,GUILayoutOption[],string>>("StyleLabel");if(f==null)GUILayout.Label(text,options);else f(text,options,role);}
 public static void StyleLabelWith(string text,GUIStyle style,GUILayoutOption[] options,string role){var f=Call<Action<string,GUIStyle,GUILayoutOption[],string>>("StyleLabelWith");if(f==null)GUILayout.Label(text,style,options);else f(text,style,options,role);}
 public static void StyleBox(string text,GUIStyle style,GUILayoutOption[] options){var f=Call<Action<string,GUIStyle,GUILayoutOption[]>>("StyleBox");if(f==null)GUILayout.Box(text,style,options);else f(text,style,options);}
 public static bool StyleContentButton(GUIContent text,GUILayoutOption[] options){var f=Call<Func<GUIContent,GUILayoutOption[],bool>>("StyleContentButton");return f==null?GUILayout.Button(text,options):f(text,options);}
 public static bool StyleContentButtonWith(GUIContent text,GUIStyle style,GUILayoutOption[] options){var f=Call<Func<GUIContent,GUIStyle,GUILayoutOption[],bool>>("StyleContentButtonWith");return f==null?GUILayout.Button(text,style,options):f(text,style,options);}
 public static bool StyleToggle(bool value,string text,GUILayoutOption[] options){var f=Call<Func<bool,string,GUILayoutOption[],bool>>("StyleToggle");return f==null?GUILayout.Toggle(value,text,options):f(value,text,options);}
 public static bool StyleToggleWith(bool value,string text,GUIStyle style,GUILayoutOption[] options){var f=Call<Func<bool,string,GUIStyle,GUILayoutOption[],bool>>("StyleToggleWith");return f==null?GUILayout.Toggle(value,text,style,options):f(value,text,style,options);}
 public static string StyleTextField(string text,GUILayoutOption[] options){var f=Call<Func<string,GUILayoutOption[],string>>("StyleTextField");return f==null?GUILayout.TextField(text,options):f(text,options);}
 public static string StyleReadOnlyField(string text,GUILayoutOption[] options){var f=Call<Func<string,GUILayoutOption[],string>>("StyleReadOnlyField");return f==null?GUILayout.TextField(text,options):f(text,options);}
 public static string StyleTextArea(string text,GUILayoutOption[] options){var f=Call<Func<string,GUILayoutOption[],string>>("StyleTextArea");return f==null?GUILayout.TextArea(text,options):f(text,options);}
 public static void StyleArea(Rect rect,string text){var f=Call<Action<Rect,string>>("StyleArea");if(f==null)GUILayout.BeginArea(rect,text);else f(rect,text);}
 public static void StyleAreaWith(Rect rect,string text,GUIStyle style){var f=Call<Action<Rect,string,GUIStyle>>("StyleAreaWith");if(f==null)GUILayout.BeginArea(rect,text,style);else f(rect,text,style);}
 public static int StyleGrid(int selected,GUIContent[] text,int columns,GUIStyle style,GUILayoutOption[] options){var f=Call<GridCall>("StyleGrid");return f==null?GUILayout.SelectionGrid(selected,text,columns,style,options):f(selected,text,columns,style,options);}
 public static bool StyleRectButton(Rect rect,string text){var f=Call<Func<Rect,string,bool>>("StyleRectButton");return f==null?GUI.Button(rect,text):f(rect,text);}
 public static bool StyleRectButtonWith(Rect rect,string text,GUIStyle style){var f=Call<Func<Rect,string,GUIStyle,bool>>("StyleRectButtonWith");return f==null?GUI.Button(rect,text,style):f(rect,text,style);}
 public static void StyleRectLabel(Rect rect,string text,GUIStyle style){var f=Call<Action<Rect,string,GUIStyle>>("StyleRectLabel");if(f==null)GUI.Label(rect,text,style);else f(rect,text,style);}
}

// Only the failure path creates this UI. Original text/GUI remain available,
// while the persistent notice prevents an English fallback from looking healthy.
internal sealed class CW3BridgeNotice:MonoBehaviour {
 GUIStyle style;
 void OnGUI(){
  if(style==null)style=new GUIStyle(GUI.skin.box){wordWrap=true,fontSize=14,alignment=TextAnchor.UpperLeft};
  int old=GUI.depth;GUI.depth=-20000;
  try{GUI.Box(new Rect(8,8,Math.Max(1,Screen.width-16),105),"CW3 Chinese localization is NOT ACTIVE.\nCheck the local CW3Localization/Runtime installation, then restart the game.\n"+CW3Runtime.BridgeStatus(),style);}
  finally{GUI.depth=old;}
 }
}
