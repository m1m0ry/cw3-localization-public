using System;using System.IO;using System.Collections;using System.Collections.Generic;using System.Reflection;using UnityEngine;

// Owned settings UI: native menu callbacks, colliders and editable game inputs stay intact.
internal static class FontSettingsView {
 const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance;
 static readonly List<CW3FontSettingsEntry> entries=new List<CW3FontSettingsEntry>();
 static readonly Dictionary<Behaviour,bool> cameras=new Dictionary<Behaviour,bool>();
 static GameObject owner;
 static Type cameraType;
 static bool oldFocus;
 static int releaseFrame=-1;
 static FontSettingsModel model;
 static TextStylePolicy pendingSizes;
 static Hashtable sizeReport;
 static string[] choices;
 static readonly string[] roleNames={"正文","标题／角色名","界面／菜单","状态／数值"};
 static int chooser=-1;
 static Vector2 scroll,choiceScroll;
 static GUIStyle label,button,heading,box;
 static Texture2D background;
 static string folder {get{return Path.GetFullPath(Path.Combine(Application.dataPath,"../CW3Localization"));}}
 internal static void Bind(){
  var root=GameObject.Find("UI Root (2D)");if(root==null)return;
  foreach(string path in new[]{"Camera/Anchor/SettingsPanel","Camera/MenuPanelAnchor/MenuPanel"}){
   Transform panel=root.transform.Find(path);if(panel==null||panel.Find("CW3FontSettingsButton")!=null)continue;
   // Put a separate footer below the existing 308px panel, keeping its tab and close targets.
   Transform bg=panel.Find(path.EndsWith("SettingsPanel")?"Background":"MenuDialogBackground");if(bg==null)continue;
   var go=new GameObject("CW3FontSettingsButton");go.layer=panel.gameObject.layer;go.transform.parent=panel;go.transform.localScale=Vector3.one;
   go.transform.localPosition=new Vector3(0,bg.localPosition.y-Math.Abs(bg.localScale.y)/2-19,-2);
   var collider=go.AddComponent<BoxCollider>();collider.size=new Vector3(220,30,1);
   var entry=go.AddComponent<CW3FontSettingsEntry>();entry.Owner=panel.gameObject;entry.Camera=root.transform.Find("Camera").GetComponent<Camera>();entries.Add(entry);
   go.SetActive(panel.gameObject.activeInHierarchy);
  }
 }
 internal static bool Open(GameObject panel){
  if(owner!=null||releaseFrame>=0||panel==null||!panel.activeInHierarchy)return false;
  try{model=new FontSettingsModel(folder,TextStyles.ActivePolicy());choices=FontSettingsModel.Choices(folder,TextStyles.FontChoices(),model.Saved);
   var root=GameObject.Find("UI Root (2D)");foreach(Component c in root.GetComponentsInChildren<Component>(true))if(c.GetType().Name=="UICamera"){
    cameraType=c.GetType();var b=c as Behaviour;if(b!=null){cameras[b]=b.enabled;b.enabled=false;}
   }
   if(cameraType==null)throw new InvalidOperationException("UICamera unavailable");
   var focus=cameraType.GetField("inputHasFocus",Flags);oldFocus=(bool)focus.GetValue(null);focus.SetValue(null,true);
   owner=panel;chooser=-1;scroll=choiceScroll=Vector2.zero;return true;
  }catch(Exception e){Release();Debug.LogWarning("CW3Localization font settings unavailable: "+e.GetType().Name);return false;}
 }
 internal static void Close(){if(model!=null)model.Cancel();owner=null;chooser=-1;releaseFrame=Time.frameCount+2;}
 static void Release(){foreach(var c in cameras)if(c.Key!=null)c.Key.enabled=c.Value;cameras.Clear();if(cameraType!=null)cameraType.GetField("inputHasFocus",Flags).SetValue(null,oldFocus);cameraType=null;releaseFrame=-1;}
 internal static void Tick(){
  // Commit once outside OnGUI; cancelled drafts never enter this queue.
  if(pendingSizes!=null){var saved=pendingSizes;pendingSizes=null;sizeReport=CW3Runtime.ApplySizes(saved);if(model!=null)model.Applied(TextStyles.ActivePolicy(),(int)sizeReport["failures"]);}
  if(owner==null&&cameras.Count>0&&releaseFrame<0)releaseFrame=Time.frameCount+2;
  if(owner!=null&&!owner.activeInHierarchy)Close();
  // Release after the closing click/key is up, so it cannot activate the native menu below.
  if(releaseFrame>=0&&Time.frameCount>=releaseFrame&&!Input.GetMouseButton(0)&&!Input.GetMouseButton(1)&&!Input.GetKey(KeyCode.Escape))Release();
 }
 internal static void Scene(){owner=null;model=null;chooser=-1;Release();entries.RemoveAll(e=>e==null);label=button=heading=box=null;}
 static void Styles(){if(label!=null)return;Font font=TextStyles.FontFor("sans");label=new GUIStyle(GUI.skin.label){font=font,fontSize=16,wordWrap=true};button=new GUIStyle(GUI.skin.button){font=font,fontSize=16,wordWrap=true};heading=new GUIStyle(label){fontSize=20};box=new GUIStyle(GUI.skin.box){font=font,fontSize=16};
  // Native Box is translucent: an owned opaque background keeps the original tabs from
  // showing through the modal. It has no NGUI material, queue or serialized resource edits.
  if(background==null){background=new Texture2D(1,1,TextureFormat.ARGB32,false);background.SetPixel(0,0,new Color(.07f,.08f,.10f,1));background.Apply();UnityEngine.Object.DontDestroyOnLoad(background);}box.normal.background=background;
 }
 internal static void Draw(){
  Styles();int oldDepth=GUI.depth;Color oldColor=GUI.color,oldContent=GUI.contentColor,oldBackground=GUI.backgroundColor;GUI.depth=-10000;GUI.color=GUI.contentColor=GUI.backgroundColor=Color.white;
  try{
   if(owner==null){foreach(var entry in entries)if(entry!=null&&entry.gameObject.activeInHierarchy){Rect r=entry.ScreenRect();GUI.Box(r,"字体与字号",button);}return;}
   // Use the actual Unity client dimensions; never change Wine desktop or game resolution.
   GUI.Box(new Rect(0,0,Screen.width,Screen.height),"",box);
   float width=Math.Min(720,Screen.width-20),height=Math.Min(580,Screen.height-20);
   GUILayout.BeginArea(new Rect((Screen.width-width)/2,(Screen.height-height)/2,width,height),box);
   try{
    GUILayout.Label("字体与字号",heading);GUILayout.Label("字号保存后即时生效，固定区域会适配。字体更换需重启。",label);
    if(chooser>=0)DrawChoices();else DrawRoles();
    GUILayout.Label(model.Notice.Length>0?model.Notice:model.Pending?"已保存的字体或像素基准尚未启用；请重启游戏。":model.Dirty?"有未保存的修改。":"保存的设置与当前启用设置一致。",label,GUILayout.Height(48));
    GUILayout.BeginHorizontal();
    if(GUILayout.Button("保存",button))Save();
    if(GUILayout.Button("取消／返回",button))Close();
    if(GUILayout.Button("恢复默认",button)){model.Defaults();chooser=-1;}
    if(GUILayout.Button("打开字体目录",button))try{string dir=Path.Combine(folder,"fonts");Directory.CreateDirectory(dir);Application.OpenURL(new Uri(dir+Path.DirectorySeparatorChar).AbsoluteUri);}catch(Exception e){model.Notice="无法打开字体目录："+e.GetType().Name;}
    GUILayout.EndHorizontal();GUILayout.Label("CW3 汉化 "+CW3BuildInfo.Version,label);
   }finally{GUILayout.EndArea();}
   if(Event.current.type==EventType.KeyDown&&Event.current.keyCode==KeyCode.Escape){Close();Event.current.Use();}
  }finally{GUI.depth=oldDepth;GUI.color=oldColor;GUI.contentColor=oldContent;GUI.backgroundColor=oldBackground;}
 }
 static void DrawRoles(){
  scroll=GUILayout.BeginScrollView(scroll);try{for(int i=0;i<TextStylePolicy.Roles.Length;i++){
   string role=TextStylePolicy.Roles[i];var style=model.Draft.For(role);
   GUILayout.BeginHorizontal();GUILayout.Label(roleNames[i],label,GUILayout.Width(124));if(GUILayout.Button(FontName(style.Family)+"（选择）",button,GUILayout.MinWidth(200)))chooser=i;
   bool enabled=GUI.enabled;GUI.enabled=style.Percent>75;if(GUILayout.Button("−",button,GUILayout.Width(38)))Change(role,style.Family,Math.Max(75,style.Percent-5),style.PixelSize);
   GUI.enabled=enabled;GUILayout.Label(style.Percent+"%",label,GUILayout.Width(62));GUI.enabled=style.Percent<150;if(GUILayout.Button("＋",button,GUILayout.Width(38)))Change(role,style.Family,Math.Min(150,style.Percent+5),style.PixelSize);GUI.enabled=enabled;
   GUILayout.EndHorizontal();GUILayout.Label(Current(role),label);GUILayout.Space(8);
  }}finally{GUILayout.EndScrollView();}
 }
 static void DrawChoices(){
  GUILayout.Label("选择 "+roleNames[chooser]+" 字体；新文件将在重启时检查。",label);
  choiceScroll=GUILayout.BeginScrollView(choiceScroll);try{foreach(string id in choices)if(GUILayout.Button(FontName(id),button)){string role=TextStylePolicy.Roles[chooser];var s=model.Draft.For(role);Change(role,id,s.Percent,id==s.Family?s.PixelSize:TextStyles.PixelUnit(id));chooser=-1;break;}}finally{GUILayout.EndScrollView();}
  if(GUILayout.Button("返回字号设置",button))chooser=-1;
 }
 static void Change(string role,string font,int percent,int pixel){model.Draft.Change(role,font,percent,pixel);model.Notice="";}
 static void Save(){try{model.Save();pendingSizes=model.Saved.Copy();chooser=-1;}catch(Exception e){model.Notice=e.Message=="配置已被外部修改，请取消并重新打开。"?e.Message:"保存失败，请检查设置文件的写入权限。";}}
 internal static string FontName(string id){return id=="sans"?"默认无衬线 (Sans)":id=="serif"?"默认衬线 (Serif)":id;}
 static string Failure(string status){if(status=="missing"||status=="not_loaded")return "文件缺失或本次启动未加载";if(status=="hash_mismatch")return "字体文件已改变";if(status=="resource_hash_mismatch")return "资源不匹配";if(status=="ready")return "已加载";if(status=="ambiguous_files")return "同名 TTF 和 OTF 无法区分";if(status.IndexOf("FormatException",StringComparison.Ordinal)>=0)return "字体格式或字形检查失败";if(status.IndexOf("IOException",StringComparison.Ordinal)>=0)return "字体文件读取失败";return "字体加载失败";}
 static string Current(string role){var r=TextStyles.RoleState(role);string result="当前："+FontName((string)r["font"])+" / "+r["percent"]+"%";string load=(string)r["load_status"];
  if(load!="ready")return result+"；"+Failure(load)+"，回退默认字体";
  int missing=(int)r["missing_glyph_controls"],other=(int)r["other_fallback_controls"];
  return result+(missing>0?"；"+missing+" 个已检查控件缺字，使用默认字体":other>0?"；"+other+" 个已检查控件加载回退":(int)r["observed_controls"]>0?"；已加载，控件检查通过":"；已加载，尚无该角色控件状态");
 }
 // Fixed developer probe, called only by the separately enabled debug helper.
 internal static Hashtable Probe(){var rows=new Hashtable();foreach(string role in TextStylePolicy.Roles)rows[role]=TextStyles.RoleState(role);var enabled=new ArrayList();foreach(var c in cameras)if(c.Key!=null)enabled.Add(c.Key.enabled);return new Hashtable{{"open",owner!=null},{"version",CW3BuildInfo.Version},{"saved",model==null?null:model.Saved.Serialize()},{"draft",model==null?null:model.Draft.Serialize()},{"active",TextStyles.ActivePolicy().Serialize()},{"pending_restart",model!=null&&model.Pending},{"size_apply_pending",pendingSizes!=null},{"size_refresh",sizeReport},{"notice",model==null?"":model.Notice},{"camera_enabled",enabled},{"roles",rows}};}
 internal static Hashtable DebugAction(string action,string arg){
  if(action=="open"){foreach(var entry in entries)if(entry!=null&&entry.Owner.activeInHierarchy){Open(entry.Owner);break;}}
  else if(action=="probe"){}
  else if(owner==null)throw new InvalidOperationException("Open the native settings first");
  else if(action=="cancel")Close();else if(action=="save")Save();else if(action=="defaults")model.Defaults();
  else if(action=="change"){string[] fields=arg.Split('|');if(fields.Length!=3||Array.IndexOf(choices,fields[1])<0)throw new FormatException("choice");int percent=Int32.Parse(fields[2]);var s=model.Draft.For(fields[0]);Change(fields[0],fields[1],percent,s.Family==fields[1]?s.PixelSize:TextStyles.PixelUnit(fields[1]));}
  else throw new FormatException("settings action");return Probe();
 }
}
public sealed class CW3FontSettingsEntry:MonoBehaviour {
 internal GameObject Owner;internal Camera Camera;
 void OnPress(bool pressed){if(!pressed)FontSettingsView.Open(Owner);}
 internal Rect ScreenRect(){var b=GetComponent<BoxCollider>().bounds;Vector3 low=Camera.WorldToScreenPoint(b.min),high=Camera.WorldToScreenPoint(b.max);return new Rect(low.x,Screen.height-high.y,high.x-low.x,high.y-low.y);}
}
