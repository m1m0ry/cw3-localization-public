using System;using System.IO;using System.Collections;using System.Collections.Generic;using System.Reflection;using System.Text;using System.Text.RegularExpressions;using System.Security.Cryptography;using System.Runtime.InteropServices;using System.Xml;using UnityEngine;
// CW3 2.12 only. Fixed IDs/bindings are compiled, translations are read once per process.
public static class CW3Runtime {
 const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
 static readonly Dictionary<string,Hashtable> definitions=new Dictionary<string,Hashtable>();
 static readonly Dictionary<string,string> translations=new Dictionary<string,string>();
 static readonly Dictionary<string,List<Hashtable>> sources=new Dictionary<string,List<Hashtable>>();
 static Candidates candidates;static readonly HashSet<string> translated=new HashSet<string>();static string guiContext;
 static readonly MessageBindings messageBindings=new MessageBindings();
 static readonly ScriptBindings scriptBindings=new ScriptBindings();
 static string[] guiArguments;static string lastScript,lastHash;static WeakReference ordinalCommands;static int[] outputOrdinals;
 static readonly List<Hashtable> displayLabels=new List<Hashtable>();
 sealed class MeshMaterial {internal Material Current;internal readonly List<Material> Created=new List<Material>();}
 static bool rebuildingFont;
 static readonly Dictionary<int,TextMesh> meshOwners=new Dictionary<int,TextMesh>();
 static readonly Dictionary<int,string> meshOriginal=new Dictionary<int,string>();
 static readonly Dictionary<int,MeshMaterial> meshMaterials=new Dictionary<int,MeshMaterial>();
 static readonly HashSet<int> fonts=new HashSet<int>();static Font external,guiExternal;static bool loaded;static string guiId,guiOriginal;static CW3RuntimePump pump;
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode,EntryPoint="AddFontResourceExW")]static extern int AddFontResourceEx(string file,uint flags,IntPtr reserved);
 static string S(Hashtable d,string k){return d[k] as string;}
 static object Get(object value,string name){if(value==null)return null;Type t=value as Type??value.GetType();var f=t.GetField(name,Flags);if(f!=null)return f.GetValue(value is Type?null:value);var p=t.GetProperty(name,Flags);return p==null?null:p.GetValue(value,null);}
 static string Hash(string text){using(var h=SHA256.Create()){byte[] bytes=h.ComputeHash(Encoding.UTF8.GetBytes(text));return BitConverter.ToString(bytes).Replace("-","").ToLowerInvariant();}}
 static bool Tokens(string a,string b){foreach(string rx in new[]{@"\{\d+(?:[^{}]*)\}|%(?:\d+\$)?[sdif]",@"\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]"}){var x=Regex.Matches(a,rx);var y=Regex.Matches(b,rx);if(x.Count!=y.Count)return false;for(int i=0;i<x.Count;i++)if(x[i].Value!=y[i].Value)return false;}return true;}
 static void Load(){if(loaded)return;loaded=true;string folder=Path.Combine(Application.dataPath,"../CW3Localization");candidates=new Candidates(File.Exists(Path.Combine(folder,"discover.enabled")),Path.Combine(folder,"candidates.json"));try{foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){definitions.Add(S(d,"id"),d);messageBindings.Add(d);scriptBindings.Add(d);if(S(d,"kind")=="label_display")displayLabels.Add(d);string source=S(d,"source");List<Hashtable> list;if(!sources.TryGetValue(source,out list))sources.Add(source,list=new List<Hashtable>());list.Add(d);}try{string path=Path.Combine(Application.dataPath,"../CW3Localization/zh-CN.json");if(new FileInfo(path).Length>4000000)throw new FormatException("Dictionary too large");var root=(Hashtable)Json.Read(File.ReadAllText(path));if((int)root["format"]!=1||S(root,"language")!="zh-CN")throw new FormatException("Dictionary format");var seen=new HashSet<string>();foreach(Hashtable row in (ArrayList)root["entries"]){string id=S(row,"id");if(id==null||!seen.Add(id))throw new FormatException("Duplicate ID");Hashtable d;string value=S(row,"translation");if(definitions.TryGetValue(id,out d)&&S(row,"source")==S(d,"source")&&!String.IsNullOrEmpty(value)&&Tokens(S(d,"source"),value))translations.Add(id,value);}foreach(string value in translations.Values)translated.Add(value);Debug.Log("CW3Localization loaded "+translations.Count+" fixed translations");}catch(Exception e){translations.Clear();Debug.LogWarning("CW3Localization dictionary fallback: "+e.Message);}
 try{string file=Path.Combine(Application.dataPath,"../CW3Localization/font.ttf");if(File.Exists(file)&&AddFontResourceEx(file,16,IntPtr.Zero)>0){external=Font.CreateDynamicFontFromOSFont(FontFile.Family(file),20);if(external==null||!external.HasCharacter('中'))throw new Exception("External font family/glyph unavailable");
 // Both original CW3 GUISkins inherit builtin Arial 13. NGUI uses its own 20-pixel font.
 guiExternal=Font.CreateDynamicFontFromOSFont(FontFile.Family(file),13);Font.textureRebuilt+=FontRebuilt;Debug.Log("CW3Localization external font loaded");}}catch(Exception e){external=null;Debug.LogWarning("CW3Localization embedded font fallback: "+e.Message);}
 }catch(Exception e){Debug.LogWarning("CW3Localization initialization fallback: "+e.Message);}}
 public static string Text(string id,string original){return Translate(id,original,true);}
 static string Translate(string id,string original,bool observe){Load();string status,value=FixedText.Resolve(definitions,translations,id,original,out status);if(observe&&status!="translated"&&candidates.Enabled){Hashtable d;bool known=id!=null&&definitions.TryGetValue(id,out d);d=known?definitions[id]:null;Observe(original,known?S(d,"kind"):"managed",known?DefinitionContext(d):"guarded Text",status,id);}return value;}
 static string ComponentText(string id,string original,Component c){Load();string status,value=FixedText.Resolve(definitions,translations,id,original,out status);if(status!="translated")ObserveComponent(original,c,c is TextMesh?"textmesh":"label",null,status,id);return value;}
 static string DefinitionContext(Hashtable d){if(d.ContainsKey("message_list"))return S(d,"resource_key")+"/"+S(d,"message_list")+"/Message["+((int)d["index"]+1)+"]";if(d.ContainsKey("path"))return S(d,"path");if(d.ContainsKey("script_hash"))return "script:"+S(d,"script")+":"+S(d,"script_hash")+":"+d["line"];if(d.ContainsKey("guid"))return S(d,"owner")+":"+S(d,"guid");return S(d,"site")??("binding:"+S(d,"id"));}
 static void Observe(string original,string kind,string context,string reason,string id){if(candidates.Enabled&&!translated.Contains(original??""))candidates.Record(Time.frameCount,original,kind,Application.loadedLevelName,context,reason,id);}
 static void ObserveComponent(string original,Component c,string kind,string path,string reason,string id=""){if(!candidates.Enabled||c==null||!c.gameObject.activeInHierarchy||!Candidates.Useful(original,id.Length>0))return;object enabled=Get(c,"enabled");if(enabled is bool&&!(bool)enabled)return;for(Transform t=c.transform;t!=null;t=t.parent)if(t.GetComponent("UIInput")!=null)return;Observe(original,kind,path??PathOf(c),reason,id);}
 public static string DiscoveryStatus(){Load();return candidates.Status();}
 internal static void DiscoveryTick(){if(candidates!=null)candidates.Tick(Time.realtimeSinceStartup);}
 internal static void DiscoveryFlush(){if(candidates!=null&&!candidates.Finish())Debug.LogWarning("CW3Localization candidate final flush incomplete: "+candidates.Status());}
 public static void Boot(){Load();if(pump!=null)return;var go=new GameObject("CW3LocalizationRuntime");UnityEngine.Object.DontDestroyOnLoad(go);pump=go.AddComponent<CW3RuntimePump>();}
 static string PathOf(Component c){string path="";for(Transform t=c.transform;t!=null;t=t.parent){string n=t.name;if(n.EndsWith("(Clone)",StringComparison.Ordinal))n=n.Substring(0,n.Length-7);path=n+(path.Length==0?"":"/"+path);}return path;}
 static string ForComponent(string text,Component c,string kind){Load();List<Hashtable> list;if(text==null||c==null)return text;if(!sources.TryGetValue(text,out list)){ObserveComponent(text,c,kind,null,"unbound_source");return text;}string path=PathOf(c);Hashtable wildcard=null;foreach(var d in list)if(S(d,"kind")==kind){string p=S(d,"path"),scene=S(d,"scene");if((scene==Application.loadedLevelName||(scene=="Splash"&&Application.loadedLevel==0))&&path==p)return ComponentText(S(d,"id"),text,c);if(scene=="*"&&(path==p||path.EndsWith("/"+p,StringComparison.Ordinal)))wildcard=d;}if(wildcard!=null)return ComponentText(S(wildcard,"id"),text,c);ObserveComponent(text,c,kind,path,"unbound_context");return text;}
 static void FontForLabel(Component label){if(external==null||label==null)return;object value=Get(label,"font");var obj=value as UnityEngine.Object;if(obj==null||fonts.Contains(obj.GetInstanceID()))return;try{var p=value.GetType().GetProperty("dynamicFont",Flags);if(p!=null){p.SetValue(value,external,null);fonts.Add(obj.GetInstanceID());}}catch(Exception e){Debug.LogWarning("CW3Localization NGUI font fallback: "+e.Message);}}
 public static void PrepareLabel(object value){Load();Component label=value as Component;if(label==null||(label.name!="CharacterName"&&label.name!="MapTitleLabel"))return;try{FontForLabel(label);string raw=Get(label,"text") as string;CaptionLayout.Prepare(label,ForLabel(raw,label));}catch(Exception e){Debug.LogWarning("CW3Localization layout fallback: "+e.Message);}}
 public static bool LayoutButton(string text,GUILayoutOption[] options){return LayoutStyledButton(text,GUI.skin.button,options);}
 public static bool LayoutStyledButton(string text,GUIStyle style,GUILayoutOption[] options){Load();if(translated.Contains(text??""))try{options=CaptionLayout.ButtonOptions(text,style,options);}catch(Exception e){Debug.LogWarning("CW3Localization button layout fallback: "+e.Message);}return GUILayout.Button(text,style,options);}
 public static string ForLabel(string text,object value){Load();Component label=value as Component;if(label==null||text==null)return text;FontForLabel(label);foreach(var d in displayLabels)if(S(d,"selector")==label.name){string source=S(d,"source");if(S(d,"match")=="exact"&&text==source)return ComponentText(S(d,"id"),text,label);if(S(d,"match")=="prefix"&&text.StartsWith(source,StringComparison.Ordinal))return ComponentText(S(d,"id"),source,label)+text.Substring(source.Length);}if(label.name=="InfoBarSystemLabel"){Type sector=label.GetType().Assembly.GetType("SectorManager");object star=Get(Get(sector,"instance"),"currentStar");if(star!=null)return ForName(text,star);}switch(label.name){case "UnitDeactivateButtonLabel":if(text=="ACTIVATE")return ComponentText("text.63b374e8d84d967e",text,label);if(text=="DEACTIVATE")return ComponentText("text.4da1839c612154ca",text,label);break;case "UnitDisarmButtonLabel":if(text=="ARM")return ComponentText("text.bd08ffebeaa89d56",text,label);if(text=="DISARM")return ComponentText("text.791afba48d68c010",text,label);break;case "UnitStopResupplyButtonLabel":if(text=="RESUPPLY")return ComponentText("text.1c1c796fc1ed36a6",text,label);if(text=="STOP RESUPPLY")return ComponentText("text.5f4ba2c5bbe4a3d4",text,label);break;case "MapTitleLabel":if(text.StartsWith("Arc Eternal : ",StringComparison.Ordinal))return ComponentText("text.b33c1c3e1a5be568","Arc Eternal : ",label)+TitleNames(text.Substring(14));break;}if(text=="Current")for(Transform t=label.transform;t!=null;t=t.parent)if(t.name=="MenuWindowResList"||t.name=="Drop-down List")return ComponentText("text.8e506022a417b175",text,label);return ForComponent(text,label,"label");}
 static string TitleNames(string original){string[] parts=original.Split(new string[]{" : "},StringSplitOptions.None);for(int i=0;i<parts.Length;i++){List<Hashtable> list;if(sources.TryGetValue(parts[i],out list))foreach(var d in list)if(S(d,"kind")=="xml_text"&&d.ContainsKey("guid")){parts[i]=Text(S(d,"id"),parts[i]);break;}}return String.Join(" : ",parts);}
 // Borrow game-owned instances (SetColor keeps one). Track only instances this bridge creates.
 static void MeshFont(TextMesh mesh){
  if(external==null||mesh==null)return;mesh.font=external;var renderer=mesh.GetComponent<Renderer>();if(renderer==null)return;
  MeshMaterial state;if(!meshMaterials.TryGetValue(mesh.GetInstanceID(),out state))meshMaterials.Add(mesh.GetInstanceID(),state=new MeshMaterial());
  if(state.Current==null||state.Current!=renderer.sharedMaterial){
   Material previous=renderer.sharedMaterial,current=renderer.material;
   if(current==null){current=new Material(external.material);renderer.sharedMaterial=current;}
   if(current!=previous)state.Created.Add(current);state.Current=current;
  }
  state.Current.mainTexture=external.material.mainTexture;
 }
 public static Hashtable MeshReport(TextMesh mesh){
  var report=new Hashtable();if(mesh==null){report["status"]="missing_mesh";return report;}
  var renderer=mesh.GetComponent<Renderer>();Material material=renderer==null?null:renderer.sharedMaterial;
  var fade=mesh.GetComponent("SetColor");Material held=Get(fade,"material") as Material;
  MeshMaterial state;bool tracked=meshMaterials.TryGetValue(mesh.GetInstanceID(),out state);
  report["status"]=material==null?"missing_renderer_material":held!=null&&held!=material?"fade_material_mismatch":tracked&&state.Current!=material?"renderer_material_changed":"ready";
  report["material_owned"]=tracked&&material!=null&&state.Created.Contains(material);
  return report;
 }
 static void RememberMesh(TextMesh mesh,string original){int id=mesh.GetInstanceID();meshOwners[id]=mesh;meshOriginal[id]=original;var lifetime=mesh.GetComponent<CW3MeshLifetime>();if(lifetime==null)lifetime=mesh.gameObject.AddComponent<CW3MeshLifetime>();lifetime.MeshId=id;}
 internal static void ReleaseMesh(int id){MeshMaterial state;if(meshMaterials.TryGetValue(id,out state)){foreach(var material in state.Created)if(material!=null)UnityEngine.Object.Destroy(material);meshMaterials.Remove(id);}meshOwners.Remove(id);meshOriginal.Remove(id);}
 public static void SetMesh(TextMesh mesh,string original){Load();RememberMesh(mesh,original);MeshFont(mesh);mesh.text=ForComponent(original,mesh,"textmesh");}
 public static void SetNamedMesh(TextMesh mesh,string original,object owner){Load();RememberMesh(mesh,original);MeshFont(mesh);mesh.text=ForName(original,owner);}
 public static string OriginalMesh(TextMesh mesh){string text;return meshOriginal.TryGetValue(mesh.GetInstanceID(),out text)?text:mesh.text;}
 public static string ForName(string original,object owner){Load();List<Hashtable> list;if(original==null||owner==null)return original;string guid=Get(owner,"GUID") as string;if(sources.TryGetValue(original,out list))foreach(var d in list)if(S(d,"owner")==owner.GetType().Name&&S(d,"guid")==guid)return Text(S(d,"id"),original);Observe(original,"xml_name",owner.GetType().Name+":"+guid,"unbound_context","");return original;}
 // Resource identity comes from native loaders, before their XML loses that identity.
 static string HashBytes(byte[] data){if(data==null)return null;using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
 public static void RegisterSystemDocument(XmlDocument doc,string resourceKey,byte[] data){Load();messageBindings.Register(doc,messageBindings.FromResource(resourceKey,HashBytes(data)));}
 public static void BeginMissionLoad(){MissionLoads.Begin();}
 public static byte[] CaptureMissionResource(byte[] data,string resourceKey){Load();MissionLoads.Capture(messageBindings.FromResource(resourceKey,HashBytes(data)));return data;}
 public static void RegisterMissionDocument(XmlDocument doc){Load();messageBindings.Register(doc,MissionLoads.Take());}
 public static void EndMissionLoad(){MissionLoads.End();}
 static void OwnMessages(object manager){var component=manager as Component;if(component==null)return;var lifetime=component.GetComponent<CW3MessageLifetime>();if(lifetime==null)lifetime=component.gameObject.AddComponent<CW3MessageLifetime>();lifetime.Manager=manager;}
 public static void BindMessages(object manager,XmlNode node){Load();try{OwnMessages(manager);messageBindings.Bind(manager,Get(manager,"messages") as IList,node);}catch(Exception e){messageBindings.Clear(manager);Debug.LogWarning("CW3Localization XML binding fallback: "+e.Message);}}
 public static void ClearMessages(object manager){messageBindings.Clear(manager);}
 public static void MessageAdded(object manager){Load();var list=Get(manager,"messages") as IList;if(list!=null&&list.Count>0){OwnMessages(manager);messageBindings.Added(manager,list[list.Count-1]);}}
 public static void MessageRemoved(object manager,object message){messageBindings.Removed(manager,message);}
 public static string ForMessage(string original,object message){Load();string status;MessageBindings.Binding binding=messageBindings.Get(message);string value=messageBindings.Display(original,message,definitions,translations,out status);if(status!="translated")Observe(original,"xml_message",binding==null?"unknown resource":binding.Context,status,binding==null?"":binding.Id??"");return value;}
 public static Hashtable MessageReport(string original,object message){Load();return messageBindings.Report(original,message,definitions,translations);}
 public static Hashtable RuntimeReport(){Load();return new Hashtable{{"bound_xml",messageBindings.BoundCount},{"tracked_xml",messageBindings.Count},{"targets",definitions.Count},{"translations",translations.Count},{"font",external},{"crpl_id",guiId}};}
 static string ScriptTarget(object core,string kind,string original,out string context){
  context="unknown script";if(core==null)return null;
  Type game=core.GetType().Assembly.GetType("GameSpace");object manager=Get(Get(game,"instance"),"scriptManager");string name=Get(core,"scriptName") as string;
  if(manager==null||name==null)return null;string code=(string)manager.GetType().GetMethod("GetScript",Flags).Invoke(manager,new object[]{name});
  var commands=Get(core,"commands") as IList;object at=Get(core,"currentCommandIndex");if(commands==null||!(at is int)||(int)at<0||(int)at>=commands.Count)return null;
  object line=Get(commands[(int)at],"lineNumber");if(!(line is int))return null;string hash;if(code==lastScript)hash=lastHash;else{lastScript=code;lastHash=hash=Hash(code);}context="script:"+name+":"+hash+":"+line;
  string id=scriptBindings.Find(kind,name,hash,(int)line,original);
  if(id==null&&kind=="show"&&scriptBindings.HasOutputs(name,hash)){
   if(commands.Count>16384)return null;
   if(ordinalCommands==null||outputOrdinals.Length!=commands.Count||!System.Object.ReferenceEquals(ordinalCommands.Target,commands)){
    ordinalCommands=new WeakReference(commands);outputOrdinals=new int[commands.Count];int ordinal=-1;
    for(int i=0;i<commands.Count;i++){object statement=Get(commands[i],"statement");int type=statement==null?-1:Convert.ToInt32(statement);if(type==291||type==292)ordinal++;outputOrdinals[i]=(type==291||type==292)?ordinal:-1;}
   }
   id=scriptBindings.FindOutput(name,hash,(int)line,outputOrdinals[(int)at],original,out guiArguments);
  }
  return id;
 }
 public static void BindScriptConversation(int character,string original,object core){
  Load();if(character>=8)return;try{
   Type game=core.GetType().Assembly.GetType("GameSpace");object manager=Get(Get(game,"instance"),"crplMdm");var list=Get(manager,"messages") as IList;
   if(list==null||list.Count==0)return;object row=list[list.Count-1];if(!System.Object.Equals(Get(row,"message"),original)||!System.Object.Equals(Get(row,"character"),character))return;
   string context,id=ScriptTarget(core,"conversation",original,out context);OwnMessages(manager);messageBindings.BindScript(manager,row,id,context);
  }catch(Exception e){Debug.LogWarning("CW3Localization script conversation fallback: "+e.Message);}
 }
 public static string CaptureCrpl(string original,object core){Load();guiId=null;guiArguments=null;guiOriginal=original;guiContext="GameSpace/ShowMessage";try{guiId=ScriptTarget(core,"show",original,out guiContext);}catch(Exception e){Debug.LogWarning("CW3Localization CRPL context fallback: "+e.Message);}return original;}
 public static string ForGuiMessage(string original){Load();if(guiId==null||original!=guiOriginal){Observe(original,"crpl",guiContext,"unbound_script_literal","");return original;}Hashtable d=definitions[guiId];if(S(d,"kind")=="crpl_output"){string target;if(!translations.TryGetValue(guiId,out target))return original;return ScriptBindings.Format(target,guiArguments)??original;}return Text(guiId,S(d,"source")).Replace("\\n","\n").Replace("\\t","\t");}
 public static void GuiFont(){Load();if(guiExternal!=null&&GUI.skin!=null)GUI.skin.font=guiExternal;}
 static void FontRebuilt(Font f){if(f!=external||rebuildingFont)return;rebuildingFont=true;try{foreach(var mesh in meshOwners.Values)if(mesh!=null){MeshFont(mesh);mesh.text=mesh.text;}}finally{rebuildingFont=false;}}
 internal static void Scan(){Load();Scene();foreach(TextMesh mesh in Resources.FindObjectsOfTypeAll(typeof(TextMesh))){if(mesh==null)continue;int id=mesh.GetInstanceID();if(!meshOriginal.ContainsKey(id))SetMesh(mesh,mesh.text);}if(external!=null){Type font=typeof(CW3Runtime).Assembly.GetType("UIFont");if(font==null){foreach(var asm in AppDomain.CurrentDomain.GetAssemblies()){font=asm.GetType("UIFont");if(font!=null)break;}}if(font!=null)foreach(UnityEngine.Object obj in Resources.FindObjectsOfTypeAll(font))try{if(fonts.Add(obj.GetInstanceID()))font.GetProperty("dynamicFont",Flags).SetValue(obj,external,null);}catch(Exception e){Debug.LogWarning(e.Message);}}}
 internal static void Scene(){messageBindings.Cleanup(owner=>owner is UnityEngine.Object&&(UnityEngine.Object)owner==null);var dead=new List<int>();foreach(var pair in meshOwners)if(pair.Value==null)dead.Add(pair.Key);foreach(int id in dead)ReleaseMesh(id);}
}
public sealed class CW3RuntimePump:MonoBehaviour {
 int frames=4;void OnLevelWasLoaded(int level){CW3Runtime.Scene();frames=4;}void LateUpdate(){if(frames>0){frames--;CW3Runtime.Scan();}CW3Runtime.DiscoveryTick();}void OnApplicationQuit(){CW3Runtime.DiscoveryFlush();}void OnDestroy(){CW3Runtime.Scene();}
}
// Release sidecar data at the native object's lifetime, including destruction within one scene.
public sealed class CW3MessageLifetime:MonoBehaviour {internal object Manager;void OnDestroy(){CW3Runtime.ClearMessages(Manager);}}
public sealed class CW3MeshLifetime:MonoBehaviour {internal int MeshId;void OnDestroy(){CW3Runtime.ReleaseMesh(MeshId);}}
