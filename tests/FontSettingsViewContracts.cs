using System;
using System.Collections;
using System.IO;
using UnityEngine;

// Font rendering and the host state root are outside this view lifecycle fixture.
// The shipped view, settings transaction and policy run unchanged.
internal sealed class RuntimePaths {
 internal static readonly RuntimePaths Current=new RuntimePaths();
 internal string State;
 internal bool EnsureState(){if(State==null)return false;Directory.CreateDirectory(State);return true;}
}
internal static class TextStyles {
 internal static TextStylePolicy ActivePolicy(){return new TextStylePolicy();}
 internal static string[] FontChoices(){return new[]{"sans","serif"};}
 internal static Font FontFor(string family){return null;}
 internal static int PixelUnit(string family){return 0;}
 internal static Hashtable RoleState(string role){return new Hashtable();}
}
internal static class CW3Runtime {
 internal static Hashtable ApplySizes(TextStylePolicy policy){throw new Exception("No save was requested by this lifecycle fixture");}
}
internal static class CW3BuildInfo {internal const string Version="fixture";}
public class UICamera:Behaviour {public static bool inputHasFocus;}

class FontSettingsViewContracts {
 sealed class Rig {
  internal GameObject Panel;
  internal UICamera Enabled,Disabled;
  internal Camera Native;
 }
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static Rig Setup(string folder,bool focus){
  FontSettingsView.Scene();GameObject.Found.Clear();
  Input.Primary=Input.Secondary=Input.Escape=false;Time.frameCount=100;
  RuntimePaths.Current.State=folder;UICamera.inputHasFocus=focus;
  var root=new GameObject("UI Root (2D)");
  var rig=new Rig{Panel=new GameObject("SettingsPanel"),Enabled=root.AddComponent<UICamera>(),Disabled=root.AddComponent<UICamera>(),Native=root.AddComponent<Camera>()};
  rig.Disabled.enabled=false;return rig;
 }
 static void Captured(Rig rig){
  Need(!rig.Enabled.enabled&&!rig.Disabled.enabled&&UICamera.inputHasFocus,"Modal owns native UI focus and disables both previously enabled/disabled UI cameras");
  Need(rig.Native.enabled,"Unrelated Unity camera remains enabled");
 }
 static void Restored(Rig rig,bool oldFocus){
  Need(rig.Enabled.enabled&&!rig.Disabled.enabled&&UICamera.inputHasFocus==oldFocus,"Original camera states and input focus are restored");
  Need(rig.Native.enabled,"Release preserves the unrelated camera");
 }
 static void ClosingInput(string folder,bool oldFocus){
  var rig=Setup(folder,oldFocus);
  Need(!FontSettingsView.Open(null),"Missing panel cannot acquire focus");
  rig.Panel.SetActive(false);Need(!FontSettingsView.Open(rig.Panel),"Inactive panel cannot acquire focus");rig.Panel.SetActive(true);
  Need(FontSettingsView.Open(rig.Panel),"Visible panel opens");Captured(rig);
  Need(!FontSettingsView.Open(new GameObject("OtherPanel")),"Opening twice cannot replace the focus owner");
  FontSettingsView.Close();Captured(rig);
  Need(!FontSettingsView.Open(rig.Panel),"Reopen is blocked while the closing input is draining");
  Time.frameCount++;FontSettingsView.Tick();Captured(rig);
  Time.frameCount++;Input.Primary=true;FontSettingsView.Tick();Captured(rig);
  Input.Primary=false;Input.Secondary=true;FontSettingsView.Tick();Captured(rig);
  Input.Secondary=false;Input.Escape=true;FontSettingsView.Tick();Captured(rig);
  Input.Escape=false;FontSettingsView.Tick();Restored(rig,oldFocus);
  Need(FontSettingsView.Open(rig.Panel),"View can reopen once the closing input has been released");
  Input.Primary=Input.Escape=true;FontSettingsView.Scene();Restored(rig,oldFocus);
  FontSettingsView.Scene();Restored(rig,oldFocus);
 }
 static void OwnerExit(string folder,bool destroyed){
  var rig=Setup(folder,false);Need(FontSettingsView.Open(rig.Panel),"Open before owner exits");
  if(destroyed)UnityEngine.Object.Destroy(rig.Panel);else rig.Panel.SetActive(false);
  FontSettingsView.Tick();Captured(rig);
  Time.frameCount++;FontSettingsView.Tick();Captured(rig);
  Time.frameCount++;FontSettingsView.Tick();Restored(rig,false);
 }
 static void Main(){
  string folder=Path.Combine(Path.GetTempPath(),"cw3-settings-view-"+Guid.NewGuid().ToString("N"));
  Directory.CreateDirectory(folder);string path=Path.Combine(folder,"text-style.json");
  string original="{\n  \"format\":1,\n  \"roles\":{}\n}\n";File.WriteAllText(path,original);
  try{
   ClosingInput(folder,false);ClosingInput(folder,true);
   OwnerExit(folder,false);OwnerExit(folder,true);
   var rig=Setup(folder,false);RuntimePaths.Current.State=null;
   Need(!FontSettingsView.Open(rig.Panel),"Unavailable state cannot open settings");Restored(rig,false);
   Setup(folder,false);GameObject.Found["UI Root (2D)"]=new GameObject("UI Root (2D)");
   Need(!FontSettingsView.Open(new GameObject("SettingsPanel"))&&!UICamera.inputHasFocus,"Missing UICamera fails without retaining focus");
   Need(File.ReadAllText(path)==original,"Opening, cancelling and scene exit never rewrite settings");
   Console.WriteLine("PASS shipped settings view: open/reopen guards, delayed mouse/Escape release, inactive/destroyed owner, scene exit and exact camera/focus restoration");
  }finally{FontSettingsView.Scene();Directory.Delete(folder,true);}
 }
}
