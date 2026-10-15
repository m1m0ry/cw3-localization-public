using System;using System.IO;using System.Collections;using System.Collections.Generic;using System.Reflection;using System.Text;using System.Text.RegularExpressions;using System.Security.Cryptography;using System.Xml;using UnityEngine;
// CW3 2.12 only. Fixed IDs/bindings are compiled, translations are read once per process.
public static partial class CW3Runtime {
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
 sealed class MeshState {internal TextMesh Mesh;internal string Original;internal MeshMaterial Material;}
 static bool rebuildingFont;
 static readonly Dictionary<int,MeshState> meshes=new Dictionary<int,MeshState>();
 static Font external,guiExternal;static bool loaded;static string guiId,guiOriginal;static CW3RuntimePump pump;
 static string S(Hashtable d,string k){return d[k] as string;}
 static object Get(object value,string name){if(value==null)return null;Type t=value as Type??value.GetType();var f=t.GetField(name,Flags);if(f!=null)return f.GetValue(value is Type?null:value);var p=t.GetProperty(name,Flags);return p==null?null:p.GetValue(value,null);}
 static string Hash(string text){using(var h=SHA256.Create()){byte[] bytes=h.ComputeHash(Encoding.UTF8.GetBytes(text));return BitConverter.ToString(bytes).Replace("-","").ToLowerInvariant();}}
 static bool Tokens(string a,string b){foreach(string rx in new[]{@"\{\d+(?:[^{}]*)\}|%(?:\d+\$)?[sdif]",@"\[(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|-|/?[bius]|/?url(?:=[^\]]+)?)\]"}){var x=Regex.Matches(a,rx);var y=Regex.Matches(b,rx);if(x.Count!=y.Count)return false;for(int i=0;i<x.Count;i++)if(x[i].Value!=y[i].Value)return false;}return true;}
 static void Load(){if(loaded)return;loaded=true;string folder=Path.Combine(Application.dataPath,"../CW3Localization");candidates=new Candidates(File.Exists(Path.Combine(folder,"discover.enabled")),Path.Combine(folder,"candidates.json"));try{foreach(Hashtable d in (ArrayList)Json.Read(Encoding.UTF8.GetString(Convert.FromBase64String(CW3Definitions.Data)))){definitions.Add(S(d,"id"),d);messageBindings.Add(d);scriptBindings.Add(d);if(S(d,"kind")=="label_display")displayLabels.Add(d);string source=S(d,"source");List<Hashtable> list;if(!sources.TryGetValue(source,out list))sources.Add(source,list=new List<Hashtable>());list.Add(d);}try{string path=Path.Combine(Application.dataPath,"../CW3Localization/zh-CN.json");if(new FileInfo(path).Length>4000000)throw new FormatException("Dictionary too large");var root=(Hashtable)Json.Read(File.ReadAllText(path));if((int)root["format"]!=1||S(root,"language")!="zh-CN")throw new FormatException("Dictionary format");var seen=new HashSet<string>();foreach(Hashtable row in (ArrayList)root["entries"]){string id=S(row,"id");if(id==null||!seen.Add(id))throw new FormatException("Duplicate ID");Hashtable d;string value=S(row,"translation");if(definitions.TryGetValue(id,out d)&&S(row,"source")==S(d,"source")&&!String.IsNullOrEmpty(value)&&Tokens(S(d,"source"),value))translations.Add(id,value);}foreach(string value in translations.Values)translated.Add(value);Debug.Log("CW3Localization loaded "+translations.Count+" fixed translations");}catch(Exception e){translations.Clear();Debug.LogWarning("CW3Localization dictionary fallback: "+e.Message);}
 TextStyles.Load(folder);external=TextStyles.FontFor("sans");guiExternal=TextStyles.FontFor("sans");Font.textureRebuilt+=FontRebuilt;
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
 static void PrepareStyledLabel(Component label){
  string raw=Get(label,"text") as string,display=DisplayLabel(raw,label),path=PathOf(label);TextStyles.Label(label,display,path);
  if(!CaptionLayout.PrepareStyled(label,display,TextStyles.Percent(label),TextStyles.LabelPixelUnit(label))){
   TextStyles.BodyFallback(label,display,path);CaptionLayout.PrepareStyled(label,display,TextStyles.Percent(label),0);
  }TextStyles.Fitted(label);
 }
 public static void PrepareLabel(object value){Load();Component label=value as Component;if(label==null)return;try{PrepareStyledLabel(label);}catch(Exception e){Debug.LogWarning("CW3Localization layout fallback: "+e.GetType().Name);}}
 public static bool LayoutButton(string text,GUILayoutOption[] options){return LayoutStyledButton(text,GUI.skin.button,options);}
 public static bool LayoutStyledButton(string text,GUIStyle style,GUILayoutOption[] options){Load();style=TextStyles.Gui(style,text,TextStylePolicy.Ui);if(translated.Contains(text??""))try{options=CaptionLayout.ButtonOptions(text,style,options);}catch(Exception e){Debug.LogWarning("CW3Localization button layout fallback: "+e.Message);}return GUILayout.Button(text,style,options);}
 public static string ForLabel(string text,object value){Load();return DisplayLabel(text,value as Component);}
 static string DisplayLabel(string text,Component label){if(label==null||text==null)return text;foreach(var d in displayLabels)if(S(d,"selector")==label.name){string source=S(d,"source");if(S(d,"match")=="exact"&&text==source)return ComponentText(S(d,"id"),text,label);if(S(d,"match")=="prefix"&&text.StartsWith(source,StringComparison.Ordinal))return ComponentText(S(d,"id"),source,label)+text.Substring(source.Length);}if(label.name=="InfoBarSystemLabel"){Type sector=label.GetType().Assembly.GetType("SectorManager");object star=Get(Get(sector,"instance"),"currentStar");if(star!=null)return ForName(text,star);}switch(label.name){case "UnitDeactivateButtonLabel":if(text=="ACTIVATE")return ComponentText("text.63b374e8d84d967e",text,label);if(text=="DEACTIVATE")return ComponentText("text.4da1839c612154ca",text,label);break;case "UnitDisarmButtonLabel":if(text=="ARM")return ComponentText("text.bd08ffebeaa89d56",text,label);if(text=="DISARM")return ComponentText("text.791afba48d68c010",text,label);break;case "UnitStopResupplyButtonLabel":if(text=="RESUPPLY")return ComponentText("text.1c1c796fc1ed36a6",text,label);if(text=="STOP RESUPPLY")return ComponentText("text.5f4ba2c5bbe4a3d4",text,label);break;case "MapTitleLabel":if(text.StartsWith("Arc Eternal : ",StringComparison.Ordinal))return ComponentText("text.b33c1c3e1a5be568","Arc Eternal : ",label)+TitleNames(text.Substring(14));break;}if(text=="Current")for(Transform t=label.transform;t!=null;t=t.parent)if(t.name=="MenuWindowResList"||t.name=="Drop-down List")return ComponentText("text.8e506022a417b175",text,label);return ForComponent(text,label,"label");}
 static string TitleNames(string original){string[] parts=original.Split(new string[]{" : "},StringSplitOptions.None);for(int i=0;i<parts.Length;i++){List<Hashtable> list;if(sources.TryGetValue(parts[i],out list))foreach(var d in list)if(S(d,"kind")=="xml_text"&&d.ContainsKey("guid")){parts[i]=Text(S(d,"id"),parts[i]);break;}}return String.Join(" : ",parts);}
 // Borrow game-owned instances (SetColor keeps one). Track only instances this bridge creates.
 static void MeshFont(TextMesh mesh){
  if(mesh==null||mesh.font==null)return;var renderer=mesh.GetComponent<Renderer>();if(renderer==null)return;
  // A record can exist before a renderer/font is ready. Keep material ownership
  // optional, and never recreate an owner after its lifetime has released it.
  MeshState owner;if(!meshes.TryGetValue(mesh.GetInstanceID(),out owner))return;
  MeshMaterial state=owner.Material;if(state==null)owner.Material=state=new MeshMaterial();
  if(state.Current==null||state.Current!=renderer.sharedMaterial){
   Material previous=renderer.sharedMaterial,current=renderer.material;
   if(current==null){current=new Material(mesh.font.material);renderer.sharedMaterial=current;}
   if(current!=previous)state.Created.Add(current);state.Current=current;
  }
  state.Current.mainTexture=mesh.font.material.mainTexture;
 }
 public static Hashtable MeshReport(TextMesh mesh){
  var report=new Hashtable();if(mesh==null){report["status"]="missing_mesh";return report;}
  var renderer=mesh.GetComponent<Renderer>();Material material=renderer==null?null:renderer.sharedMaterial;
  var fade=mesh.GetComponent("SetColor");Material held=Get(fade,"material") as Material;
  MeshState owner;MeshMaterial state=meshes.TryGetValue(mesh.GetInstanceID(),out owner)?owner.Material:null;bool tracked=state!=null;
  report["status"]=material==null?"missing_renderer_material":held!=null&&held!=material?"fade_material_mismatch":tracked&&state.Current!=material?"renderer_material_changed":"ready";
  report["material_owned"]=tracked&&material!=null&&state.Created.Contains(material);
  return report;
 }
 static void RememberMesh(TextMesh mesh,string original){int id=mesh.GetInstanceID();MeshState state;if(!meshes.TryGetValue(id,out state))meshes.Add(id,state=new MeshState());state.Mesh=mesh;state.Original=original;var lifetime=mesh.GetComponent<CW3MeshLifetime>();if(lifetime==null)lifetime=mesh.gameObject.AddComponent<CW3MeshLifetime>();lifetime.MeshId=id;}
 internal static void ReleaseMesh(int id){MeshState state;if(meshes.TryGetValue(id,out state)){if(state.Material!=null)foreach(var material in state.Material.Created)if(material!=null)UnityEngine.Object.Destroy(material);meshes.Remove(id);}TextStyles.ReleaseMesh(id);}
 public static void SetMesh(TextMesh mesh,string original){Load();RememberMesh(mesh,original);string display=ForComponent(original,mesh,"textmesh");TextStyles.Mesh(mesh,display,TextStylePolicy.Role(mesh.name,PathOf(mesh)));MeshFont(mesh);mesh.text=display;RefreshSizedMesh(mesh);}
 public static void SetNamedMesh(TextMesh mesh,string original,object owner){Load();RememberMesh(mesh,original);string display=ForName(original,owner);TextStyles.Mesh(mesh,display,TextStylePolicy.Title);MeshFont(mesh);mesh.text=display;RefreshSizedMesh(mesh);}
 public static string OriginalMesh(TextMesh mesh){MeshState state;return meshes.TryGetValue(mesh.GetInstanceID(),out state)?state.Original:mesh.text;}
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
 public static string ForGuiMessage(string original){Load();if(guiId==null||original!=guiOriginal){Observe(original,"crpl",guiContext,"unbound_script_literal","");return original;}Hashtable d=definitions[guiId];if(S(d,"kind")=="crpl_output"){string target;if(!translations.TryGetValue(guiId,out target)){Observe(S(d,"source"),"crpl_output",guiContext,"missing_translation",guiId);return original;}return ScriptBindings.Format(target,guiArguments)??original;}return Text(guiId,S(d,"source")).Replace("\\n","\n").Replace("\\t","\t");}
 public static void StyleDiagnostics(bool enabled){TextStyles.Diagnostics(enabled);}
 public static Hashtable StyleReport(Component component){Load();return TextStyles.Report(component);}
 public static Hashtable StyleStatus(){Load();return TextStyles.Status();}
 static void RefreshSizedMesh(TextMesh mesh){
  if(PathOf(mesh).StartsWith("EntryPoints/",StringComparison.Ordinal)&&mesh.transform.parent!=null){var collider=mesh.transform.parent.GetComponent<Collider>();var renderer=mesh.GetComponent<Renderer>();
   if(collider!=null&&renderer!=null){int unit=Math.Max(1,TextStyles.MeshPixelUnit(mesh));string display=mesh.text;
    // Keep the original clickable region. Pixel fonts step only in whole baseline units.
    while(mesh.fontSize>Math.Max(4,unit)&&(renderer.bounds.size.x>collider.bounds.size.x||renderer.bounds.size.y>collider.bounds.size.y)){mesh.fontSize=Math.Max(Math.Max(4,unit),mesh.fontSize-unit);mesh.text=display;}
    TextStyles.FittedMesh(mesh);
   }
  }MeshFont(mesh);
 }
 internal static Hashtable ApplySizes(TextStylePolicy saved){Load();return TextStyles.ApplySizes(saved,label=>PrepareStyledLabel(label),mesh=>RefreshSizedMesh(mesh));}
 static void FontRebuilt(Font f){if(!TextStyles.Owns(f)||rebuildingFont)return;rebuildingFont=true;try{TextStyles.Rebuilt(f,PrepareStyledLabel,(mesh,refit)=>{if(refit)RefreshSizedMesh(mesh);else MeshFont(mesh);mesh.text=mesh.text;});}finally{rebuildingFont=false;}}
 internal static void Scan(){Load();Scene();FontSettingsView.Bind();foreach(TextMesh mesh in Resources.FindObjectsOfTypeAll(typeof(TextMesh))){if(mesh==null)continue;int id=mesh.GetInstanceID();if(!meshes.ContainsKey(id))SetMesh(mesh,mesh.text);}}
 internal static void Scene(){messageBindings.Cleanup(owner=>owner is UnityEngine.Object&&(UnityEngine.Object)owner==null);var dead=new List<int>();foreach(var pair in meshes)if(pair.Value.Mesh==null)dead.Add(pair.Key);foreach(int id in dead)ReleaseMesh(id);TextStyles.Cleanup();}
}
public sealed class CW3RuntimePump:MonoBehaviour {
 int frames=4;void OnLevelWasLoaded(int level){FontSettingsView.Scene();CW3Runtime.Scene();frames=4;}void LateUpdate(){if(frames>0){frames--;CW3Runtime.Scan();}FontSettingsView.Tick();CW3Runtime.DiscoveryTick();}void OnGUI(){FontSettingsView.Draw();}void OnApplicationQuit(){CW3Runtime.DiscoveryFlush();TextStyles.Shutdown();}void OnDestroy(){FontSettingsView.Scene();CW3Runtime.Scene();}
}
// Release sidecar data at the native object's lifetime, including destruction within one scene.
public sealed class CW3MessageLifetime:MonoBehaviour {internal object Manager;void OnDestroy(){CW3Runtime.ClearMessages(Manager);}}
public sealed class CW3MeshLifetime:MonoBehaviour {internal int MeshId;void OnDestroy(){CW3Runtime.ReleaseMesh(MeshId);}}
