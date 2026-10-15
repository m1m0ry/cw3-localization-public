using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

// Native Mac diagnostics live in the regular runtime DLL. An exact local marker
// activates this fixed interface at launch; an absent marker creates no updater.
internal sealed class MacDiagnostics : MonoBehaviour {
 const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static;
 static MacDiagnostics instance;
 string root,expected;
 bool preview;
 float next;

 static bool Plain(string path){return File.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)==0;}
 static bool DirectoryPlain(string path){return Directory.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)==0;}
 static string Hash(string path){using(var stream=File.OpenRead(path))using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();}
 static string Q(object value){return "\""+(value==null?"":value.ToString()).Replace("\\","\\\\").Replace("\"","\\\"").Replace("\r","\\r").Replace("\n","\\n").Replace("\t","\\t")+"\"";}
 static string Json(object value){
  if(value==null)return "null";
  if(value is bool)return (bool)value?"true":"false";
  if(value is int)return value.ToString();
  var map=value as IDictionary;if(map!=null){var rows=new System.Collections.Generic.List<string>();foreach(DictionaryEntry row in map)rows.Add(Q(row.Key)+":"+Json(row.Value));return "{"+String.Join(",",rows.ToArray())+"}";}
  var list=value as IList;if(list!=null){var rows=new System.Collections.Generic.List<string>();foreach(object row in list)rows.Add(Json(row));return "["+String.Join(",",rows.ToArray())+"]";}
  return Q(value);
 }

 internal static void Boot(){
  if(instance!=null)return;
  try{
   var paths=RuntimePaths.Current;
   if(!paths.NativeMac||paths.State==null||!paths.EnsureState())return;
   string folder=Path.Combine(paths.State,"cw3-debug"),marker=Path.Combine(folder,"enabled.txt");
   if(!DirectoryPlain(folder)||!Plain(marker)||new FileInfo(marker).Length>80)return;
   string actual=Hash(typeof(MacDiagnostics).Assembly.Location);
   if(File.ReadAllText(marker).Trim()!=actual)return;
   string ready=Path.Combine(folder,"ready.json");
   if(File.Exists(ready)&&!Plain(ready))return;
   var go=new GameObject("CW3 Mac diagnostics (local)");DontDestroyOnLoad(go);
   instance=go.AddComponent<MacDiagnostics>();instance.root=folder;instance.expected=actual;
   File.WriteAllText(ready,"{\"enabled\":true,\"runtime_sha256\":"+Q(actual)+"}");
  }catch(Exception e){Debug.LogWarning("CW3 Mac diagnostics unavailable: "+e.GetType().Name);}
 }

 void Update(){
  if(Time.realtimeSinceStartup<next)return;
  next=Time.realtimeSinceStartup+0.5f;
  try{
   string marker=Path.Combine(root,"enabled.txt");
   if(!DirectoryPlain(root)||!Plain(marker)||File.ReadAllText(marker).Trim()!=expected){Destroy(gameObject);instance=null;return;}
   string request=Path.Combine(root,"request.txt");if(!File.Exists(request))return;
   if(!Plain(request)||new FileInfo(request).Length>512)throw new IOException("Unsafe diagnostics request");
   string row=File.ReadAllText(request).Trim();File.Delete(request);
   string[] fields=row.Split('\t');string id=fields.Length>0?fields[0]:"invalid";
   if(fields.Length<2||fields.Length>3||id.Length!=32)throw new FormatException("Request format");
   foreach(char ch in id)if(!Uri.IsHexDigit(ch))throw new FormatException("Request id");
   string command=fields[1],arg=fields.Length==3?fields[2]:"";
   string response;
   try{response="{\"id\":"+Q(id)+",\"ok\":true,\"result\":"+Execute(command,arg,id)+"}";}
   catch(Exception e){response="{\"id\":"+Q(id)+",\"ok\":false,\"error\":"+Q(e.InnerException==null?e.Message:e.InnerException.Message)+"}";}
   string output=Path.Combine(root,"response.json");if(File.Exists(output)&&!Plain(output))throw new IOException("Unsafe diagnostics response");
   File.WriteAllText(output,response);
  }catch(Exception e){Debug.LogWarning("CW3 Mac diagnostics request refused: "+e.GetType().Name);}
 }

 static bool Choice(string arg){
  string[] parts=arg.Split('|');if(parts.Length!=3)return false;
  if(Array.IndexOf(TextStylePolicy.Roles,parts[0])<0||!(parts[1]=="sans"||parts[1]=="serif"))return false;
  int percent;return Int32.TryParse(parts[2],out percent)&&percent>=75&&percent<=150&&percent%5==0;
 }
 static string NativeSettingsOpen(){
  if(Application.loadedLevelName!="MainMenu")throw new InvalidOperationException("MainMenu only");
  long start=DateTime.UtcNow.Ticks;
  Type settings=Type.GetType("GameSettings, Assembly-CSharp",true),input=Type.GetType("InputManager, Assembly-CSharp",true);
  settings.GetMethod("Read",Flags).Invoke(null,null);
  var root=GameObject.Find("UI Root (2D)");
  var panel=root==null?null:root.transform.Find("Camera/Anchor/SettingsPanel");
  if(panel==null)throw new InvalidOperationException("SettingsPanel missing");
  panel.gameObject.SetActiveRecursively(true);
  input.GetMethod("SetGUI",Flags).Invoke(null,null);
  return Json(new Hashtable{{"panel_active",panel.gameObject.activeInHierarchy},{"open_ms",(int)((DateTime.UtcNow.Ticks-start)/TimeSpan.TicksPerMillisecond)}});
 }
 const BindingFlags Members=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
 static object Value(object target,string name){
  if(target==null)return null;var type=target.GetType();var p=type.GetProperty(name,Members);
  if(p!=null)return p.GetValue(target,null);var f=type.GetField(name,Members);return f==null?null:f.GetValue(target);
 }
 static string PathOf(Transform t){string path=t.name;while(t.parent!=null){t=t.parent;path=t.name+"/"+path;}return path;}
 static string DisplayProbe(){
  var rows=new ArrayList();
  foreach(Component c in UnityEngine.Object.FindObjectsOfType(typeof(Component))){
   if(c==null||!c.gameObject.activeInHierarchy)continue;
   string kind=c.GetType().Name;if(kind!="UILabel"&&kind!="TextMesh")continue;
   var style=CW3Runtime.StyleReport(c);var mesh=c as TextMesh;var renderer=c.GetComponent<Renderer>();
   rows.Add(new Hashtable{{"kind",kind},{"path",PathOf(c.transform)},{"text",Value(c,"text")},
    {"processed",Value(c,"processedText")},{"style",style},{"render",mesh==null?null:CW3Runtime.MeshReport(mesh)},
    {"color",renderer==null||renderer.sharedMaterial==null?null:(object)renderer.sharedMaterial.color}});
   if(rows.Count>=400)break;
  }
  return Json(new Hashtable{{"scene",Application.loadedLevelName},{"controls",rows},{"screen",Screen.width+"x"+Screen.height}});
 }
 static string FontsProbe(){
  var rows=new ArrayList();var seen=new System.Collections.Generic.HashSet<string>();
  foreach(string role in TextStylePolicy.Roles){string family=TextStyles.ActivePolicy().For(role).Family;if(!seen.Add(family))continue;
   Font font=TextStyles.FontFor(family);CharacterInfo glyph=new CharacterInfo();bool available=false;
   if(font!=null){font.RequestCharactersInTexture("字体验",24,FontStyle.Normal);available=font.GetCharacterInfo('验',out glyph,24,FontStyle.Normal);}
   rows.Add(new Hashtable{{"family",family},{"font",font==null?null:font.name},{"names",font==null?null:font.fontNames},
    {"dynamic",font!=null&&font.dynamic},{"chinese_glyph",available},{"advance",glyph.advance}});
  }
  return Json(new Hashtable{{"fonts",rows},{"styles",TextStyles.Status()}});
 }
 static string FallbackProbe(){
  // Zpix covers every current translation. This fixed offscreen sample exercises
  // the real TextMesh selection path with U+3400, absent from Zpix but in sans.
  var go=new GameObject("CW3 fixed missing glyph probe");go.SetActive(false);var mesh=go.AddComponent<TextMesh>();
  try{mesh.font=TextStyles.FontFor("sans");mesh.fontSize=24;TextStyles.Mesh(mesh,"字体㐀",TextStylePolicy.Body);
   var report=TextStyles.Report(mesh);CharacterInfo glyph=new CharacterInfo();
   mesh.font.RequestCharactersInTexture("㐀",24,FontStyle.Normal);
   report["fixed_sample"]="字体㐀";report["fallback_glyph"]=mesh.font.GetCharacterInfo('㐀',out glyph,24,FontStyle.Normal);
   report["advance"]=glyph.advance;return Json(report);
  }finally{TextStyles.ReleaseMesh(mesh.GetInstanceID());UnityEngine.Object.Destroy(go);}
 }
 string PreludePreview(){
  if(Application.loadedLevelName!="MainMenu"||preview)throw new InvalidOperationException("Fresh MainMenu only");
  if((bool)FontSettingsView.Probe()["open"])throw new InvalidOperationException("Close font settings first");
  preview=true;Application.LoadLevel("Prelude");
  return Json(new Hashtable{{"scene","Prelude"},{"route","direct read-only scene preview"}});
 }
 string Execute(string command,string arg,string id){
  if(command=="runtime_probe"&&arg==""){
   var report=CW3Runtime.RuntimeReport();
   Type bridge=Type.GetType("CW3Runtime, CW3Runtime",true);
   string status=(string)bridge.GetMethod("BridgeStatus",BindingFlags.Public|BindingFlags.Static).Invoke(null,null);
   return Json(new Hashtable{{"scene",Application.loadedLevelName},{"bridge",status},{"version",CW3BuildInfo.Version},{"translations",report["translations"]},{"targets",report["targets"]},{"bound_xml",report["bound_xml"]},{"time",Time.realtimeSinceStartup.ToString(System.Globalization.CultureInfo.InvariantCulture)}});
  }
  if(command=="style_probe"&&arg=="")return Json(CW3Runtime.StyleStatus());
  if(command=="display_probe"&&arg=="")return DisplayProbe();
  if(command=="fonts_probe"&&arg=="")return FontsProbe();
  if(command=="fallback_probe"&&arg=="")return FallbackProbe();
  if(command=="audio_probe"&&arg==""){
   var clips=new ArrayList();foreach(AudioClip clip in Resources.FindObjectsOfTypeAll(typeof(AudioClip)))
    clips.Add(new Hashtable{{"name",clip.name},{"load_state",clip.loadState.ToString()},{"samples",clip.samples},{"frequency",clip.frequency}});
   var playing=new ArrayList();foreach(AudioSource source in UnityEngine.Object.FindObjectsOfType(typeof(AudioSource)))
    if(source.isPlaying&&source.clip!=null)playing.Add(source.clip.name);
   return Json(new Hashtable{{"scene",Application.loadedLevelName},{"clips",clips},{"playing",playing}});
  }
  if(command=="prelude_preview"&&arg=="")return PreludePreview();
  if(command=="preview_return"&&arg==""){
   if(!preview||Application.loadedLevelName!="Prelude")throw new InvalidOperationException("Owned Prelude preview only");
   Application.LoadLevel("MainMenu");preview=false;return Json(new Hashtable{{"scene","MainMenu"}});
  }
  if(command=="quit"&&arg==""){
   if(Application.loadedLevelName!="MainMenu"||preview)throw new InvalidOperationException("MainMenu only; return from preview first");
   Application.Quit();return Json(new Hashtable{{"queued",true}});
  }
  if(command=="font_probe"&&arg==""){
   Font font=TextStyles.FontFor("sans");
   return Json(new Hashtable{{"font",font==null?null:font.name},{"has_chinese_glyph",font!=null&&font.HasCharacter('验')}});
  }
  if(command=="settings_native_open"&&arg=="")return NativeSettingsOpen();
  if(command=="settings_open"||command=="settings_probe"||command=="settings_cancel"||command=="settings_save"||command=="settings_defaults"){
   if(arg!="")throw new FormatException("Unexpected argument");
   return Json(FontSettingsView.DebugAction(command.Substring(9),""));
  }
  if(command=="settings_change"&&Choice(arg))return Json(FontSettingsView.DebugAction("change",arg));
  if(command=="screenshot"&&arg==""){
   string path=Path.Combine(root,"capture-"+id+".png");if(File.Exists(path))throw new IOException("Capture already exists");
   Application.CaptureScreenshot(path);
   return Json(new Hashtable{{"path",path},{"queued",true}});
  }
  throw new FormatException("Command not allowed");
 }
}
