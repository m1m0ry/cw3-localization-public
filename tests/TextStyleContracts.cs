using System;using System.IO;using System.Security.Cryptography;using System.Collections;using System.Collections.Generic;using System.Reflection;
namespace UnityEngine {
 public class Object {static int next;int id=++next;public string name;public int GetInstanceID(){return id;}public static void Destroy(Object value){}public static void DontDestroyOnLoad(Object value){}}
 public enum HideFlags {HideAndDontSave}public enum FontStyle {Normal}
 public class GameObject:Object {public bool activeInHierarchy=true;public HideFlags hideFlags;public Transform transform=new Transform();public GameObject(string n){name=n;transform.name=n;}public Component AddComponent(Type type){var c=(Component)Activator.CreateInstance(type);c.gameObject=this;return c;}public T AddComponent<T>() where T:Component,new(){return (T)AddComponent(typeof(T));}}
 public class Component:Object {public GameObject gameObject;public Transform transform{get{return gameObject.transform;}}}
 public class MonoBehaviour:Component {}
 public class Transform:Object {public Transform parent;public Vector3 localScale=new Vector3(20,20,1),localPosition;public Dictionary<string,Transform> children=new Dictionary<string,Transform>();public Transform Find(string name){Transform value;return children.TryGetValue(name,out value)?value:null;}public Component GetComponent(string name){return null;}}
 public struct Vector3 {public float x,y,z;public Vector3(float a,float b,float c){x=a;y=b;z=c;}public static bool operator==(Vector3 a,Vector3 b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}public static bool operator!=(Vector3 a,Vector3 b){return !(a==b);}public override bool Equals(object o){return o is Vector3&&this==(Vector3)o;}public override int GetHashCode(){return (int)x;}}
 public struct Vector2 {public float x,y;public Vector2(float a,float b){x=a;y=b;}}
 public enum FilterMode {Bilinear,Point}
 public class Texture {public FilterMode filterMode;}
 public class Material {public Texture mainTexture=new Texture();}
 public struct CharacterInfo {public int advance;}
 public class Font:Object {public void RequestCharactersInTexture(string text,int size,FontStyle style){}public bool GetCharacterInfo(char c,out CharacterInfo ci,int size,FontStyle style){ci=new CharacterInfo{advance=20};return true;}public int fontSize=20;public bool dynamic=true;public Material material=new Material();public bool HasCharacter(char c){return true;}}
 public static class Debug {public static void LogWarning(string message){}}
 public static class Application {public static string dataPath,persistentDataPath;}
 public static class Resources {public static Dictionary<string,Object> values=new Dictionary<string,Object>();public static Object Load(string path,Type type){Object value;return values.TryGetValue(path,out value)?value:null;}}
 public class TextMesh:Component {public Font font;public int fontSize;public string text;}
 public static class Screen {public static int width=1280,height=720;}
 public class GUILayoutOption {}
 public static class GUILayout {public static GUILayoutOption Width(float value){return new GUILayoutOption();}}
 public class GUIContent {public string text;public GUIContent(string value){text=value;}}
 public class GUIStyle {public string name;public Font font;public int fontSize;public bool wordWrap;public int padding;public GUIStyle(){}public GUIStyle(GUIStyle value){name=value.name;font=value.font;fontSize=value.fontSize;wordWrap=value.wordWrap;padding=value.padding;}public Vector2 CalcSize(GUIContent content){return new Vector2(content.text.Length*(fontSize>0?fontSize:13),13);}}
}
public class UIFont:UnityEngine.Component {public object mUVRect,mFont;public int mSpacingX,mSpacingY;public float mPixelSize;public UnityEngine.FontStyle mDynamicFontStyle;public UnityEngine.Font dynamicFont{get;set;}public int dynamicFontSize{get;set;}
 public string WrapText(string text,float width,int lines,bool encoding,CaptionSymbols symbols){int count=Math.Max(1,(int)width);var rows=new List<string>();foreach(string paragraph in text.Split('\n')){if(paragraph.Length==0)rows.Add("");else for(int i=0;i<paragraph.Length;i+=count)rows.Add(paragraph.Substring(i,Math.Min(count,paragraph.Length-i)));}return String.Join("\n",rows.ToArray());}
 public UnityEngine.Vector2 CalculatePrintedSize(string text,bool encoding,CaptionSymbols symbols){string[] rows=text.Split('\n');int width=0;foreach(string row in rows)width=Math.Max(width,row.Length);return new UnityEngine.Vector2(width,rows.Length);}
}
public enum CaptionSymbols {None}
public class Label:UnityEngine.Component {public UIFont font{get;set;}public string text{get;set;}public CaptionSymbols symbolStyle{get;set;}public bool supportEncoding{get;set;}public bool password{get;set;}public bool shrinkToFit{get;set;}public int lineWidth{get;set;}public int maxLineCount{get;set;}public int marks;public void MarkAsChanged(){marks++;}}
internal static class StyleFontFixture {internal static string SansHash="",SerifHash="",AssetsHash="",SansCoverage="",SerifCoverage="";}
internal static class CW3BuildInfo {internal const bool NativeMac=false;}
internal static class FontFile {internal static string Family(string path,string prefix){return prefix;}}
// Stand in for Unity's native bundle loader; TextStyles must select the user's
// file from State, independently of the two embedded default font resources.
internal static class LocalFonts {
 internal static UnityEngine.Font Shared,User;internal static string UserHash;internal static byte[] UserCoverage;
 internal static Dictionary<string,UnityEngine.Font> Points=new Dictionary<string,UnityEngine.Font>();
 static string userPath;
 internal static string Add(string folder,string id){string path=Path.Combine(folder,"fonts/"+id);if(id!="pixel.ttf"||!File.Exists(path))return "missing";userPath=path;return "ready";}
 internal static UnityEngine.Font FontFor(string id){return userPath==null?null:User;}
 internal static byte[] Coverage(string id){return UserCoverage;}
 internal static int PixelUnit(string id){return 12;}
 internal static UnityEngine.Font Point(string folder,string id){return userPath==null?null:Point(folder,userPath,UserHash);}
 internal static UnityEngine.Font Point(string folder,string path,string hash){UnityEngine.Font f;if(Points.TryGetValue(hash,out f))return f;f=new UnityEngine.Font{name="Point_"+hash};if(path.EndsWith("serif.ttf"))f.material.mainTexture=Shared.material.mainTexture;Points.Add(hash,f);return f;}
 internal static bool Owns(UnityEngine.Font f){return false;}internal static void KeepAtlas(UnityEngine.Font f){}internal static void Shutdown(IEnumerable<UnityEngine.Font> borrowed){}internal static Hashtable Status(){return new Hashtable();}
}

class TextStyleContracts {
 const string Opening="斯卡斯……醒醒。\n斯卡斯！……\n\n斯卡斯加德·阿布拉克西斯指挥官！";
 static void Need(bool condition,string message){if(!condition)throw new Exception(message);}
 static Label Make(string name,UIFont native){var label=new Label{gameObject=new UnityEngine.GameObject(name),name=name,font=native};return label;}
 static void Reject(string value){bool failed=false;try{TextStylePolicy.Parse(value);}catch(FormatException){failed=true;}Need(failed,"reject invalid style");}
 static string Hash(string path){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
 static string Cmap(string chars){byte[] bits=new byte[8192];foreach(char c in chars)bits[c/8]|=(byte)(1<<(c%8));return Convert.ToBase64String(bits);}
 static void Main(string[] args){
  var defaults=new TextStylePolicy();foreach(string role in new[]{"body","title","ui","status","code_input"})Need(defaults.For(role).Family=="sans"&&defaults.For(role).Percent==100,"v12.5 default metrics");
  Need(TextStylePolicy.Role("MessageText","UI/MessageDialog/MessageText")=="body"&&TextStylePolicy.Role("MessageText","Other/MessageText")=="ui","actual control context");Need(TextStylePolicy.Role("EnergyLabel","")=="status","numeric separation");
  Need(TextStylePolicy.Role("EntryTitle","EntryPoints/ArcEternalEntrySprite/EntryTitle")=="ui","main menu entry titles belong to menu role");
  Need(TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"pixel.ttf\",\"size_percent\":100}}}").For("body").Family=="pixel.ttf","custom font allowed in body");Reject("{\"format\":1,\"roles\":{\"ui\":{\"font\":\"sans\",\"size_percent\":151}}}");Reject("{\"format\":1,\"roles\":{},\"path\":\"bad\"}");
  Need(TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"文楷 Screen.ttf\",\"size_percent\":100},\"ui\":{\"font\":\"pixel.ttf\",\"size_percent\":100,\"pixel_size\":12}}}").For("ui").PixelSize==12,"file references and explicit pixel metadata");
  foreach(string bad in new[]{"../font.ttf","C:\\font.ttf",".font.ttf","a/b.ttf","font.woff"})Need(!TextStylePolicy.FontReference(bad),"reject unsafe or unsupported font reference");
  var flags=BindingFlags.Static|BindingFlags.NonPublic;
  bool nativeMac=args.Length>0&&args[0].StartsWith("native",StringComparison.Ordinal),blocked=args.Length>0&&args[0]=="native-state-unavailable";
  string root=Path.Combine(args.Length>1?args[1]:Path.GetTempPath(),"cw3-native-font-contract-"+Guid.NewGuid());Directory.CreateDirectory(root);
  string persistent=Path.Combine(root,"user-state");if(blocked)File.WriteAllText(persistent,"keep");
  var paths=RuntimePaths.Resolve(Path.Combine(root,nativeMac?"CW3Localization/Runtime/CW3ExternalRuntime.dll":"CW3_Data/Managed/CW3Runtime.dll"),nativeMac,persistent);
  string temp=paths.Content;Directory.CreateDirectory(temp);Directory.CreateDirectory(paths.Data);UnityEngine.Application.dataPath=nativeMac?Path.Combine(root,"CW3.app/Contents"):paths.Data;
  Directory.CreateDirectory(Path.Combine(temp,"fonts"));
  foreach(string file in new[]{"font.ttf","serif.ttf","fonts/pixel.ttf"})File.WriteAllText(Path.Combine(temp,file),file);
  foreach(string file in new[]{"sharedassets0.assets","mainData"})File.WriteAllText(Path.Combine(paths.Data,file),file);
  StyleFontFixture.SansHash=Hash(Path.Combine(temp,"font.ttf"));StyleFontFixture.SerifHash=Hash(Path.Combine(temp,"serif.ttf"));string pixelHash=Hash(Path.Combine(temp,"fonts/pixel.ttf"));StyleFontFixture.AssetsHash=Hash(Path.Combine(paths.Data,"sharedassets0.assets"));
  StyleFontFixture.SansCoverage=Cmap("中雪龘"+Opening);StyleFontFixture.SerifCoverage=Cmap("中");string pixelCoverage=Cmap("中"+Opening);
  var sans=new UnityEngine.Font{name="CW3Style_sans_"+StyleFontFixture.SansHash.Substring(0,12)};var serif=new UnityEngine.Font{name="CW3Style_serif_"+StyleFontFixture.SerifHash.Substring(0,12)};var pixel=new UnityEngine.Font{name="CW3Style_pixel.ttf_"+pixelHash.Substring(0,12)};
  UnityEngine.Resources.values.Add("cw3-localization/fonts/sans",sans);UnityEngine.Resources.values.Add("cw3-localization/fonts/serif",serif);
  Func<string,string,string,int,string> face=(file,hash,cmap,unit)=>"{\"file\":\""+file+"\",\"sha256\":\""+hash+"\",\"family\":\"Fixture\",\"coverage\":\""+cmap+"\",\"pixel_size\":"+unit+",\"probe_char\":20013,\"probe_advance\":20}";
  string registry="{\"format\":1,\"runtime_sha256\":\""+Hash(typeof(TextStyles).Assembly.Location)+"\",\"resources\":{\"CW3_Data/sharedassets0.assets\":\""+StyleFontFixture.AssetsHash+"\",\"CW3_Data/mainData\":\""+Hash(Path.Combine(paths.Data,"mainData"))+"\"},\"fonts\":{\"sans\":"+face("font.ttf",StyleFontFixture.SansHash,StyleFontFixture.SansCoverage,0)+",\"serif\":"+face("serif.ttf",StyleFontFixture.SerifHash,StyleFontFixture.SerifCoverage,0)+"}}";
  string extra=registry.Substring(0,registry.Length-2)+",\"pixel\":"+face("fonts/pixel.ttf",pixelHash,pixelCoverage,12)+"}}";bool registryRejected=false;try{FontRegistry.Parse(extra);}catch(FormatException){registryRejected=true;}Need(registryRejected,"Extra embedded faces are registryRejected");
  registryRejected=false;try{FontRegistry.Parse(registry.Replace("serif.ttf","font.ttf"));}catch(FormatException){registryRejected=true;}Need(registryRejected,"Default face cannot use another face's file");
  File.WriteAllText(Path.Combine(temp,"fonts.json"),registry);LocalFonts.User=pixel;LocalFonts.UserHash=pixelHash;LocalFonts.UserCoverage=Convert.FromBase64String(pixelCoverage);
  LocalFonts.Shared=sans;File.WriteAllText(Path.Combine(temp,"text-style.json"),"{\"format\":1,\"roles\":{\"ui\":{\"font\":\"sans\",\"size_percent\":100,\"pixel_size\":12},\"title\":{\"font\":\"pixel.ttf\",\"size_percent\":100},\"status\":{\"font\":\"serif\",\"size_percent\":100,\"pixel_size\":12}}}");
  var smoothPixel=pixel;smoothPixel.material.mainTexture.filterMode=UnityEngine.FilterMode.Point;
  if(nativeMac&&!blocked){Directory.CreateDirectory(Path.Combine(paths.State,"fonts"));File.Copy(Path.Combine(temp,"text-style.json"),Path.Combine(paths.State,"text-style.json"));File.Copy(Path.Combine(temp,"fonts/pixel.ttf"),Path.Combine(paths.State,"fonts/pixel.ttf"));}
  string failure=args.Length>0?args[0]:"";
  if(failure=="registry-missing")File.Delete(Path.Combine(temp,"fonts.json"));
  if(failure=="registry-invalid")File.WriteAllText(Path.Combine(temp,"fonts.json"),"{");
  if(failure=="registry-runtime")File.WriteAllText(Path.Combine(temp,"fonts.json"),registry.Replace(Hash(typeof(TextStyles).Assembly.Location),new string('0',64)));
  if(failure=="registry-resource")File.WriteAllText(Path.Combine(paths.Data,"mainData"),"changed");
  TextStyles.Load(paths);
  if(failure.StartsWith("registry-",StringComparison.Ordinal)){
   Need(TextStyles.FontFor("sans")==null&&TextStyles.FontFor("serif")==null&&LocalFonts.Points.Count==0,"Invalid registry cannot load weaker compiled defaults or local variants");
   Directory.Delete(root,true);Console.WriteLine("PASS "+failure+": native display retained, no second font metadata authority");return;
  }
  Need((string)TextStyles.Status()["sans"]=="ready"&&(string)TextStyles.Status()["serif"]=="ready","hash-bound native font resources loaded");
  if(nativeMac){
   var active=TextStyles.ActivePolicy();
   Need(blocked?active.For("title").Family=="sans"&&active.For("ui").PixelSize==0:active.For("title").Family=="pixel.ttf"&&active.For("status").Family=="serif"&&active.For("ui").PixelSize==12,"Native policy loads only from external state, or defaults when unavailable");
   Need((string)TextStyles.Status()["config"]==(blocked?"missing_defaults":"loaded"),"Native policy status reports external state");
   Need(blocked?LocalFonts.Points.Count==0:LocalFonts.Points.ContainsKey(pixelHash)&&LocalFonts.Points.ContainsKey(StyleFontFixture.SansHash),"Native point variants follow the saved policy");
   var fontStatus=(Hashtable)TextStyles.Status()["font_status"];Need(blocked?!fontStatus.ContainsKey("pixel.ttf"):(string)fontStatus["pixel.ttf"]=="ready","Local user font loads only from available external state");
   Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"中","title").font==(blocked?sans:LocalFonts.Points[pixelHash]),"Native title face follows policy or default");
   Need(!File.Exists(Path.Combine(temp,"font-status.json"))&&!File.Exists(Path.Combine(paths.Data,"font-status.json")),"Runtime status never writes package content or Data");
   Need(blocked?File.ReadAllText(persistent)=="keep":File.Exists(Path.Combine(paths.State,"font-status.json")),"Status output stays in external state or reports failure without fallback");
   if(!blocked)Need(File.ReadAllText(Path.Combine(paths.State,"text-style.json"))==File.ReadAllText(Path.Combine(temp,"text-style.json")),"Native policy leaves the user's existing settings unchanged");
   Directory.Delete(root,true);Console.WriteLine("PASS native style with "+(blocked?"unavailable":"external")+" state; font choice and point variants follow policy");return;
  }
  Need((string)((Hashtable)TextStyles.Status()["font_status"])["pixel.ttf"]=="ready","Windows local custom font remains available");
  Need(TextStyles.FontFor("sans")==sans&&TextStyles.FontFor("serif")==serif,"exact resource instances, no OS lookup");pixel=LocalFonts.Points[pixelHash];var sansPoint=LocalFonts.Points[StyleFontFixture.SansHash];
  Need(pixel!=smoothPixel&&pixel.material!=smoothPixel.material&&pixel.material.mainTexture!=smoothPixel.material.mainTexture&&pixel.material.mainTexture.filterMode==UnityEngine.FilterMode.Point,"pixel variant owns font, material and atlas");
  Need(sans.material.mainTexture.filterMode==UnityEngine.FilterMode.Bilinear&&smoothPixel.material.mainTexture.filterMode==UnityEngine.FilterMode.Bilinear,"startup pixel choices never mutate canonical atlases");
  var startupNative=new UIFont{gameObject=new UnityEngine.GameObject("native"),dynamicFont=sans,dynamicFontSize=20};
  var startup=Make("ButtonLabel",startupNative);startup.text="中";TextStyles.Label(startup,startup.text,"Menu/ButtonLabel");
  Need(startup.font.dynamicFont==sansPoint&&TextStyles.LabelPixelUnit(startup)==12,"mixed startup UI uses isolated point font");
  Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"中","ui").font==sansPoint&&TextStyles.Gui(new UnityEngine.GUIStyle(),"中","body").font==sans&&TextStyles.Gui(new UnityEngine.GUIStyle(),"中","code_input").font==sans,"UI point and body/code smooth are isolated");
  var startupMesh=new UnityEngine.TextMesh{gameObject=new UnityEngine.GameObject("ButtonLabel"),font=sans,fontSize=20,text="中"};TextStyles.Mesh(startupMesh,"中","ui");Need(startupMesh.font==sansPoint&&startupMesh.fontSize==24,"TextMesh uses same point instance independent of size");
  var rejected=Make("EnergyLabel",startupNative);TextStyles.Label(rejected,"中","UI/EnergyLabel");Need(rejected.font.dynamicFont==sans&&TextStyles.LabelPixelUnit(rejected)==0&&rejected.transform.localScale.x==20,"shared atlas variant falls back to smooth metrics");
  Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"雪","status").font==sans&&TextStyles.Gui(new UnityEngine.GUIStyle(),"雪","status").fontSize==13,"explicit pixel metadata never quantizes a missing-glyph fallback");
  TextStyles.BodyFallback(startup,"中","UI/MessageDialog/MessageText");Need(startup.font.dynamicFont==sans&&TextStyles.LabelPixelUnit(startup)==0,"body fallback uses canonical smooth font");
  TextStyles.ReleaseLabel(startup.GetInstanceID());TextStyles.ReleaseLabel(rejected.GetInstanceID());TextStyles.ReleaseMesh(startupMesh.GetInstanceID());
  var load=typeof(TextStyles).GetMethod("LoadFace",flags);File.WriteAllText(Path.Combine(temp,"serif.ttf"),"changed");Need((string)load.Invoke(null,new object[]{temp,"other","serif.ttf",StyleFontFixture.SerifHash,StyleFontFixture.SerifCoverage,"Serif",0,0})=="hash_mismatch","changed TTF rejected");
  Need((string)load.Invoke(null,new object[]{temp,"other","absent.ttf",StyleFontFixture.SerifHash,StyleFontFixture.SerifCoverage,"Serif",0,0})=="missing","missing font falls back");
  typeof(TextStyles).GetField("assetsValid",flags).SetValue(null,false);Need((string)load.Invoke(null,new object[]{temp,"other","font.ttf",StyleFontFixture.SansHash,StyleFontFixture.SansCoverage,"Sans",0,0})=="resource_hash_mismatch","wrong serialized font bytes rejected");Directory.Delete(root,true);

  var policy=TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"serif\",\"size_percent\":125},\"ui\":{\"font\":\"pixel.ttf\",\"size_percent\":75}}}");typeof(TextStyles).GetField("policy",flags).SetValue(null,policy);
  var native=new UIFont{gameObject=new UnityEngine.GameObject("native"),dynamicFont=new UnityEngine.Font{name="Embedded"},dynamicFontSize=20};
  var body=Make("MessageText",native);var body2=Make("MessageText",native);var title=Make("CharacterName",native);TextStyles.Label(body,"中","UI/MessageDialog/MessageText");TextStyles.Label(body2,"中","UI/MessageDialog/MessageText");TextStyles.Label(title,"中","UI/MessageDialog/CharacterName");
  Need(body.font!=native&&body.font!=title.font&&body.font==body2.font,"UIFont isolation and reuse");Need(native.dynamicFont.name=="Embedded"&&native.dynamicFontSize==20,"shared native UIFont unchanged");Need(body.transform.localScale.x==25&&title.transform.localScale.x==20,"role scales independent");
  for(int i=0;i<5;i++)TextStyles.Label(body,"中","UI/MessageDialog/MessageText");Need(body.transform.localScale.x==25,"repeat ProcessText never multiplies again");TextStyles.Label(body,"雪","UI/MessageDialog/MessageText");Need(body.font.dynamicFont==sans&&body2.font.dynamicFont==serif,"source cmap forces per-control fallback even when Unity HasCharacter reports true");
  var menu=Make("ButtonLabel",native);TextStyles.Label(menu,"中","Menu/ButtonLabel");Need(menu.font.dynamicFont==pixel&&menu.font.dynamicFontSize==12&&menu.transform.localScale.x==12,"pixel menu aligned 12px");
  var gui=new UnityEngine.GUIStyle{padding=7,wordWrap=true};var styled=TextStyles.Gui(gui,"中","ui");Need(gui.font==null&&gui.fontSize==0&&styled.font==pixel&&styled.fontSize==12&&styled.padding==7&&styled.wordWrap,"GUIStyle copy preserves caller");
  var code=TextStyles.Gui(gui,"中","code_input");Need(code.font==sans&&code.fontSize==13&&gui.font==null,"code input ignores menu style and preserves metrics");gui.font=new UnityEngine.Font{name="explicit"};Need(TextStyles.Gui(gui,"中","code_input").font==gui.font,"explicit input font retained");Need(Object.ReferenceEquals(TextStyles.Gui(gui,"中","code_input"),gui),"unchanged explicit code style reused");var matching=TextStyles.Gui(new UnityEngine.GUIStyle(),"中","ui");Need(Object.ReferenceEquals(TextStyles.Gui(matching,"中","ui"),matching),"already resolved style reused");
  foreach(string role in new[]{"body","title","ui","status"}){var all=TextStylePolicy.Parse("{\"format\":1,\"roles\":{\""+role+"\":{\"font\":\"pixel.ttf\",\"size_percent\":100}}}");typeof(TextStyles).GetField("policy",flags).SetValue(null,all);Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"中",role).font==pixel,"any role uses local pixel font");Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"雪",role).font==sans,"missing custom glyph falls back for each role");}
  pixel.material.mainTexture.filterMode=UnityEngine.FilterMode.Bilinear;TextStyles.Rebuilt(pixel,c=>{},(m,refit)=>{});Need(pixel.material.mainTexture.filterMode==UnityEngine.FilterMode.Point,"custom pixel metadata survives rebuild");
  TextStyles.ReleaseLabel(body2.GetInstanceID());Need(body.font.dynamicFont==sans,"releasing shared owner preserves survivor");Need((bool)TextStyles.Status()["diagnostics"]==false,"diagnostics default disabled");
  typeof(TextStyles).GetField("policy",flags).SetValue(null,new TextStylePolicy());
  var hot=Make("MessageText",native);hot.text="中";TextStyles.Label(hot,hot.text,"UI/MessageDialog/MessageText");
  var mesh=new UnityEngine.TextMesh{name="EnergyLabel",gameObject=new UnityEngine.GameObject("EnergyLabel"),font=sans,fontSize=40,text="已显示标题"};TextStyles.Mesh(mesh,mesh.text,"title");int materialUpdates=0;
  Action<UnityEngine.Component> prepare=c=>{var l=(Label)c;TextStyles.Label(l,l.text,"UI/MessageDialog/"+l.name);};
  foreach(int percent in new[]{150,75,100,150,75,100}){var saved=new TextStylePolicy();saved.Change("body","serif",percent,0);saved.Change("title","serif",percent,0);var report=TextStyles.ApplySizes(saved,prepare,m=>materialUpdates++);Need(TextStyles.ActivePolicy().For("body").Family=="sans","mixed save keeps active font");Need(hot.transform.localScale.x==20*percent/100f,"live size uses original scale every time");Need(mesh.fontSize==40*percent/100&&mesh.text=="已显示标题","named mesh remembered role and display survive refresh");Need((int)report["failures"]==0&&hot.marks>0,"existing labels invalidate native caches");}
  var same=TextStyles.ApplySizes(new TextStylePolicy(),prepare,m=>materialUpdates++);Need((int)same["labels"]==0&&(int)same["meshes"]==0,"unchanged save does not refresh controls");
  var sizes=new TextStylePolicy();sizes.Change("body","sans",125,0);TextStyles.ApplySizes(sizes,prepare,m=>materialUpdates++);var later=Make("MessageText",native);TextStyles.Label(later,"中","UI/MessageDialog/MessageText");Need(later.transform.localScale.x==25,"new label adopts live policy");
  typeof(TextStyles).GetField("policy",flags).SetValue(null,TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"ui\":{\"font\":\"pixel.ttf\",\"size_percent\":100}}}"));var px=Make("ButtonLabel",native);px.transform.localScale=new UnityEngine.Vector3(32,32,1);px.text="中";TextStyles.Label(px,px.text,"UI/ButtonLabel");foreach(int percent in new[]{150,75,100}){var s2=new TextStylePolicy();s2.Change("ui","serif",percent,0);TextStyles.ApplySizes(s2,prepare,m=>materialUpdates++);Need(px.transform.localScale.x==TextStylePolicy.PixelSize(32,percent,12),"live pixel size snaps from original baseline");}
  // Exercise the same Label -> layout -> Fitted order as CW3Runtime, including live ApplySizes.
  Action<UnityEngine.Component> prepareTitle=c=>{var l=(Label)c;TextStyles.Label(l,l.text,"UI/"+l.transform.parent.name+"/"+l.name);CaptionLayout.PrepareStyled(l,l.text,TextStyles.Percent(l),TextStyles.LabelPixelUnit(l));TextStyles.Fitted(l);};
  foreach(bool explicitUnit in new[]{false,true})foreach(string name in new[]{"CharacterName","MapTitleLabel"}){
   var titlePolicy=new TextStylePolicy();titlePolicy.Change("title",explicitUnit?"sans":"pixel.ttf",100,explicitUnit?12:0);typeof(TextStyles).GetField("policy",flags).SetValue(null,titlePolicy);
   var fitted=Make(name,native);fitted.text="中中";fitted.transform.localScale=new UnityEngine.Vector3(16,16,1);fitted.transform.localPosition=new UnityEngine.Vector3(7,2,-1);
   var host=new UnityEngine.Transform{name=name=="CharacterName"?"MessageDialog":"CommandNodePanels"};fitted.transform.parent=host;
   var bound=new UnityEngine.Transform{localScale=new UnityEngine.Vector3(144,100,1),localPosition=new UnityEngine.Vector3(0,-50,0)};host.children.Add(name=="CharacterName"?"Texture":"SlicedSprite (ButtonSelection)",bound);
   prepareTitle(fitted);Need(fitted.transform.localScale.y==12&&fitted.font.dynamicFontSize==12,"first title keeps pixel grid");
   foreach(int percent in new[]{150,75,100,150,75,100}){
    var saved=titlePolicy.Copy();saved.Change("title","serif",percent,0);
    // Only this title is in scope for this callback; older controls may have other hosts.
    var report=TextStyles.ApplySizes(saved,c=>{if(c==fitted)prepareTitle(c);},m=>{});
    int wanted=TextStylePolicy.PixelSize(16,percent,12);Need(fitted.transform.localScale.y==wanted&&fitted.font.dynamicFontSize==wanted,"live title uses original baseline and matching pixel glyph size");
    Need((int)report["failures"]==0&&TextStyles.LabelPixelUnit(fitted)==12,"live title preserves active pixel metadata");
    for(int repeat=0;repeat<3;repeat++){prepareTitle(fitted);Need(fitted.transform.localScale.y==wanted&&fitted.font.dynamicFontSize==wanted,"repeated layout does not replace or compound title size");}
   }
   var large=titlePolicy.Copy();large.Change("title","serif",150,0);TextStyles.ApplySizes(large,c=>{if(c==fitted)prepareTitle(c);},m=>{});
   fitted.text=new string('中',name=="CharacterName"?14:10);
   for(int repeat=0;repeat<3;repeat++){prepareTitle(fitted);Need(fitted.transform.localScale.y==12&&fitted.font.dynamicFontSize==12,"bounded title repeatedly fits 24 to 12 with matching glyph size");}
   fitted.text="中中";prepareTitle(fitted);Need(fitted.transform.localScale.y==24&&fitted.font.dynamicFontSize==24,"short title restores requested size after bounded fit");
   fitted.text=new string('中',100);prepareTitle(fitted);Need(fitted.transform.localScale.y==12&&fitted.font.dynamicFontSize==12,"extreme title stops at one whole pixel unit");
   Need(fitted.lineWidth==(name=="CharacterName"?144:128)&&fitted.maxLineCount==(name=="CharacterName"?2:1)&&!fitted.shrinkToFit,"native title bounds remain fixed");
   Need(fitted.transform.localPosition.x==7&&fitted.transform.localPosition.z==-1&&(name!="MapTitleLabel"||fitted.transform.localPosition.y==2),"title preserves native anchor axes");
   Need(bound.localScale.x==144&&bound.localScale.y==100,"title does not resize its host region");
   fitted.text="中中";prepareTitle(fitted);Need(fitted.transform.localScale.y==24&&fitted.font.dynamicFontSize==24,"short text restores style from original baseline after fitting");
   if(!explicitUnit){fitted.text="雪";prepareTitle(fitted);Need(fitted.font.dynamicFont==sans&&TextStyles.LabelPixelUnit(fitted)==0&&fitted.transform.localScale.y==24,"nonpixel glyph fallback retains legacy title fitting");}
   TextStyles.ReleaseLabel(fitted.GetInstanceID());
  }
  BodyContracts(native,sans,flags);
  var isolatedPolicy=new TextStylePolicy();isolatedPolicy.Change("ui","sans",100,12);typeof(TextStyles).GetField("policy",flags).SetValue(null,isolatedPolicy);
  var rebuilding=Make("ButtonLabel",native);rebuilding.text="中";TextStyles.Label(rebuilding,"中","UI/ButtonLabel");
  var rebuildingMesh=new UnityEngine.TextMesh{gameObject=new UnityEngine.GameObject("ButtonLabel"),font=sans,fontSize=20,text="中"};TextStyles.Mesh(rebuildingMesh,"中","ui");
  int prepared=0;Action<UnityEngine.Component> refresh=c=>{prepared++;var l=(Label)c;TextStyles.Label(l,l.text,"UI/"+l.name);};int refreshed=0;
  sansPoint.material.mainTexture=new UnityEngine.Texture();TextStyles.Rebuilt(sansPoint,refresh,(m,refit)=>refreshed++);
  Need(sansPoint.material.mainTexture.filterMode==UnityEngine.FilterMode.Point&&sans.material.mainTexture.filterMode==UnityEngine.FilterMode.Bilinear,"new point atlas filtering leaves smooth unchanged");Need(prepared==0,"ordinary atlas rebuild invalidates without reapplying layout");
  // A smooth rebuild can also introduce sharing; invalidate existing controls and meshes.
  sans.material.mainTexture=sansPoint.material.mainTexture;TextStyles.Rebuilt(sans,refresh,(m,refit)=>refreshed++);
  Need(sans.material.mainTexture.filterMode==UnityEngine.FilterMode.Bilinear&&rebuilding.font.dynamicFont==sans&&TextStyles.LabelPixelUnit(rebuilding)==0,"smooth-direction sharing blocks point and restores active label");
  Need(rebuildingMesh.font==sans&&rebuildingMesh.fontSize==20&&TextStyles.MeshPixelUnit(rebuildingMesh)==0&&refreshed>=2,"blocked active mesh restores smooth metrics and refreshes its material");
  Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"中","ui").font==sans&&TextStyles.Gui(new UnityEngine.GUIStyle(),"中","ui").fontSize==13,"blocked point cannot return on the next draw");
  Console.WriteLine("PASS pixel title/body layout/live-size integration, semantic policy, defaults, native isolation/reuse, stable scales, per-control glyph fallback, pixel menu, GUI copies and input metrics");
 }
 static Label Body(UIFont native){
  var body=Make("MessageText",native);body.text=Opening;body.lineWidth=561;body.maxLineCount=5;
  body.transform.localPosition=new UnityEngine.Vector3(-216,-12,0);
  var dialog=new UnityEngine.Transform{name="MessageDialog"};body.transform.parent=dialog;
  var next=new UnityEngine.Transform{localPosition=new UnityEngine.Vector3(315,-116,0)};
  next.children.Add("Background",new UnityEngine.Transform{localScale=new UnityEngine.Vector3(60,20,1)});dialog.children.Add("NextButton",next);
  return body;
 }
 static void PrepareBody(UnityEngine.Component component){
  var body=(Label)component;const string path="UI/MessageDialog/MessageText";
  TextStyles.Label(body,body.text,path);
  if(!CaptionLayout.PrepareStyled(body,body.text,TextStyles.Percent(body),TextStyles.LabelPixelUnit(body))){
   TextStyles.BodyFallback(body,body.text,path);CaptionLayout.PrepareStyled(body,body.text,TextStyles.Percent(body),0);
  }TextStyles.Fitted(body);
 }
 static void BodyFits(Label body){
  float size=body.transform.localScale.y;
  string wrapped=body.font.WrapText(body.text,561/size,0,false,CaptionSymbols.None);
  Need(body.font.CalculatePrintedSize(wrapped,false,CaptionSymbols.None).y*size<=90.1f&&size>=12,"body remains readable above the fixed button row");
  Need(body.transform.localPosition==new UnityEngine.Vector3(-216,-12,0)&&body.lineWidth==561&&body.maxLineCount==5,"body keeps native bounds and anchor");
 }
 static void BodyContracts(UIFont native,UnityEngine.Font sans,BindingFlags flags){
  // text.1bd8ca742b1590ce, level2/level3 MessageDialog: four lines, 561px wide, 90px high.
  foreach(bool explicitUnit in new[]{false,true}){
   var policy=new TextStylePolicy();policy.Change("body",explicitUnit?"sans":"pixel.ttf",100,explicitUnit?12:0);
   typeof(TextStyles).GetField("policy",flags).SetValue(null,policy);var body=Body(native);
   PrepareBody(body);BodyFits(body);
   Need(body.transform.localScale.y==12&&body.font.dynamicFontSize==12,"four-line opening in 90px keeps whole 12px glyphs, not a 24px glyph scaled to 22px");
   var next=body.transform.parent.Find("NextButton");next.localPosition=new UnityEngine.Vector3(315,-122,0);
   PrepareBody(body);Need(body.transform.localScale.y==24&&body.font.dynamicFontSize==24,"exact 96px boundary retains four 24px lines");
   next.localPosition=new UnityEngine.Vector3(315,-116,0);
   foreach(int percent in new[]{150,75,100}){
    var saved=policy.Copy();saved.Change("body",policy.For("body").Family,percent,policy.For("body").PixelSize);
    body.text=Opening;var report=TextStyles.ApplySizes(saved,c=>{if(c==body)PrepareBody(c);},m=>{});
    Need((int)report["failures"]==0,"body live-size refresh succeeds");BodyFits(body);
    Need(body.transform.localScale.y==12&&body.font.dynamicFontSize==12,"live body fitting retains its pixel baseline");
    body.text="中";PrepareBody(body);int expected=percent==150?36:percent==75?12:24;
    Need(body.transform.localScale.y==expected&&body.font.dynamicFontSize==expected,"short body restores the requested glyph size without compounding");
    body.text=Opening;for(int i=0;i<3;i++){PrepareBody(body);BodyFits(body);Need(body.transform.localScale.y==12&&body.font.dynamicFontSize==12,"repeated body processing stays on the pixel grid");}
   }TextStyles.ReleaseLabel(body.GetInstanceID());
  }
  // Non-divisors of 12 must not round the readability floor down; oversized units use smooth Sans.
  foreach(int pixel in new[]{5,8,11,24,64}){
   int percent=pixel==11?75:150;var policy=new TextStylePolicy();policy.Change("body","pixel.ttf",percent,pixel);
   typeof(TextStyles).GetField("policy",flags).SetValue(null,policy);var body=Body(native);PrepareBody(body);BodyFits(body);
   if(pixel==5||pixel==8){int expected=pixel==5?20:16;Need(body.transform.localScale.y==expected&&body.font.dynamicFontSize==expected&&TextStyles.LabelPixelUnit(body)==pixel,"readable integer pixel sizes fit without a fractional floor");}
   else{Need(body.font.dynamicFont==sans&&TextStyles.LabelPixelUnit(body)==0&&(string)TextStyles.Report(body)["fallback"]=="pixel_body_bounds","unreadable or oversized pixel grid falls back for this body only");Need(body.transform.localScale.y==(pixel==11?15:22),"fallback preserves ordinary Sans fitting");}
   Need(TextStyles.ActivePolicy().For("body").PixelSize==pixel,"bounded fallback does not rewrite the user setting");
   if(pixel>=24){
    for(int repeat=0;repeat<3;repeat++){PrepareBody(body);BodyFits(body);Need(body.transform.localScale.y==22,"repeated fallback retains the original size baseline");}
    body.text="中";PrepareBody(body);Need(body.font.dynamicFont!=sans&&body.transform.localScale.y==pixel&&body.font.dynamicFontSize==pixel&&TextStyles.LabelPixelUnit(body)==pixel,"shorter text restores the selected pixel face after bounded fallback");
   }
   TextStyles.ReleaseLabel(body.GetInstanceID());
  }
  var smooth=new TextStylePolicy();smooth.Change("body","sans",150,0);typeof(TextStyles).GetField("policy",flags).SetValue(null,smooth);
  var ordinary=Body(native);PrepareBody(ordinary);BodyFits(ordinary);
  Need(ordinary.transform.localScale.y==22&&ordinary.font.dynamicFontSize==20&&TextStyles.LabelPixelUnit(ordinary)==0,"ordinary nonpixel body retains its existing 22px fit and native glyph size");
  TextStyles.ReleaseLabel(ordinary.GetInstanceID());
 }
}
