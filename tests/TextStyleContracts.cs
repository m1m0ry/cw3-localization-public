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
 public static class Application {public static string dataPath;}
 public static class Resources {public static Dictionary<string,Object> values=new Dictionary<string,Object>();public static Object Load(string path,Type type){Object value;return values.TryGetValue(path,out value)?value:null;}}
 public class TextMesh:Component {public Font font;public int fontSize;public string text;}
 public static class Screen {public static int width=1280,height=720;}
 public class GUILayoutOption {}
 public static class GUILayout {public static GUILayoutOption Width(float value){return new GUILayoutOption();}}
 public class GUIContent {public string text;public GUIContent(string value){text=value;}}
 public class GUIStyle {public string name;public Font font;public int fontSize;public bool wordWrap;public int padding;public GUIStyle(){}public GUIStyle(GUIStyle value){name=value.name;font=value.font;fontSize=value.fontSize;wordWrap=value.wordWrap;padding=value.padding;}public Vector2 CalcSize(GUIContent content){return new Vector2(content.text.Length*(fontSize>0?fontSize:13),13);}}
}
public class UIFont:UnityEngine.Component {public object mUVRect,mFont;public int mSpacingX,mSpacingY;public float mPixelSize;public UnityEngine.FontStyle mDynamicFontStyle;public UnityEngine.Font dynamicFont{get;set;}public int dynamicFontSize{get;set;}
 public string WrapText(string text,float width,int lines,bool encoding,CaptionSymbols symbols){int count=Math.Max(1,(int)width);var rows=new List<string>();for(int i=0;i<text.Length;i+=count)rows.Add(text.Substring(i,Math.Min(count,text.Length-i)));return String.Join("\n",rows.ToArray());}
 public UnityEngine.Vector2 CalculatePrintedSize(string text,bool encoding,CaptionSymbols symbols){string[] rows=text.Split('\n');int width=0;foreach(string row in rows)width=Math.Max(width,row.Length);return new UnityEngine.Vector2(width,rows.Length);}
}
public enum CaptionSymbols {None}
public class Label:UnityEngine.Component {public UIFont font{get;set;}public string text{get;set;}public CaptionSymbols symbolStyle{get;set;}public bool supportEncoding{get;set;}public bool password{get;set;}public bool shrinkToFit{get;set;}public int lineWidth{get;set;}public int maxLineCount{get;set;}public int marks;public void MarkAsChanged(){marks++;}}
internal static class CW3StyleFonts {internal static string SansHash="",SerifHash="",AssetsHash="",SansCoverage="",SerifCoverage="";}
internal static class FontFile {internal static string Family(string path,string prefix){return prefix;}}
internal static class LocalFonts {internal static string Add(string folder,string id){return "missing";}internal static UnityEngine.Font FontFor(string id){return null;}internal static byte[] Coverage(string id){return new byte[8192];}internal static int PixelUnit(string id){return 0;}internal static bool Owns(UnityEngine.Font f){return false;}internal static void KeepAtlas(UnityEngine.Font f){}internal static void Shutdown(){}internal static Hashtable Status(){return new Hashtable();}}

class TextStyleContracts {
 static void Need(bool condition,string message){if(!condition)throw new Exception(message);}
 static Label Make(string name,UIFont native){var label=new Label{gameObject=new UnityEngine.GameObject(name),name=name,font=native};return label;}
 static void Reject(string value){bool failed=false;try{TextStylePolicy.Parse(value);}catch(FormatException){failed=true;}Need(failed,"reject invalid style");}
 static string Hash(string path){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
 static string Cmap(string chars){byte[] bits=new byte[8192];foreach(char c in chars)bits[c/8]|=(byte)(1<<(c%8));return Convert.ToBase64String(bits);}
 static void Main(){
  var defaults=new TextStylePolicy();foreach(string role in new[]{"body","title","ui","status","code_input"})Need(defaults.For(role).Family=="sans"&&defaults.For(role).Percent==100,"v12.5 default metrics");
  Need(TextStylePolicy.Role("MessageText","UI/MessageDialog/MessageText")=="body"&&TextStylePolicy.Role("MessageText","Other/MessageText")=="ui","actual control context");Need(TextStylePolicy.Role("EnergyLabel","")=="status","numeric separation");
  Need(TextStylePolicy.Role("EntryTitle","EntryPoints/ArcEternalEntrySprite/EntryTitle")=="ui","main menu entry titles belong to menu role");
  Need(TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"pixel_custom\",\"size_percent\":100}}}").For("body").Family=="pixel_custom","custom font allowed in body");Reject("{\"format\":1,\"roles\":{\"ui\":{\"font\":\"sans\",\"size_percent\":151}}}");Reject("{\"format\":1,\"roles\":{},\"path\":\"bad\"}");
  Need(TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"文楷 Screen.ttf\",\"size_percent\":100},\"ui\":{\"font\":\"pixel.ttf\",\"size_percent\":100,\"pixel_size\":12}}}").For("ui").PixelSize==12,"file references and explicit pixel metadata");
  foreach(string bad in new[]{"../font.ttf","C:\\font.ttf",".font.ttf","a/b.ttf","font.woff"})Need(!TextStylePolicy.FontReference(bad),"reject unsafe or unsupported font reference");
  var flags=BindingFlags.Static|BindingFlags.NonPublic;
  string temp=Path.Combine(Path.GetTempPath(),"cw3-native-font-contract-"+Guid.NewGuid());Directory.CreateDirectory(temp);UnityEngine.Application.dataPath=temp;
  Directory.CreateDirectory(Path.Combine(temp,"fonts"));
  foreach(string file in new[]{"font.ttf","serif.ttf","fonts/pixel.ttf","sharedassets0.assets","mainData"})File.WriteAllText(Path.Combine(temp,file),file);
  CW3StyleFonts.SansHash=Hash(Path.Combine(temp,"font.ttf"));CW3StyleFonts.SerifHash=Hash(Path.Combine(temp,"serif.ttf"));string pixelHash=Hash(Path.Combine(temp,"fonts/pixel.ttf"));CW3StyleFonts.AssetsHash=Hash(Path.Combine(temp,"sharedassets0.assets"));
  CW3StyleFonts.SansCoverage=Cmap("中雪龘");CW3StyleFonts.SerifCoverage=Cmap("中");string pixelCoverage=Cmap("中");
  var sans=new UnityEngine.Font{name="CW3Style_sans_"+CW3StyleFonts.SansHash.Substring(0,12)};var serif=new UnityEngine.Font{name="CW3Style_serif_"+CW3StyleFonts.SerifHash.Substring(0,12)};var pixel=new UnityEngine.Font{name="CW3Style_pixel_custom_"+pixelHash.Substring(0,12)};
  UnityEngine.Resources.values.Add("cw3-localization/fonts/sans",sans);UnityEngine.Resources.values.Add("cw3-localization/fonts/serif",serif);UnityEngine.Resources.values.Add("cw3-localization/fonts/pixel_custom",pixel);
  Func<string,string,string,int,string> face=(file,hash,cmap,unit)=>"{\"file\":\""+file+"\",\"sha256\":\""+hash+"\",\"family\":\"Fixture\",\"coverage\":\""+cmap+"\",\"pixel_size\":"+unit+",\"probe_char\":20013,\"probe_advance\":20}";
  File.WriteAllText(Path.Combine(temp,"fonts.json"),"{\"format\":1,\"runtime_sha256\":\""+Hash(typeof(TextStyles).Assembly.Location)+"\",\"resources\":{\"CW3_Data/sharedassets0.assets\":\""+CW3StyleFonts.AssetsHash+"\",\"CW3_Data/mainData\":\""+Hash(Path.Combine(temp,"mainData"))+"\"},\"fonts\":{\"sans\":"+face("font.ttf",CW3StyleFonts.SansHash,CW3StyleFonts.SansCoverage,0)+",\"serif\":"+face("serif.ttf",CW3StyleFonts.SerifHash,CW3StyleFonts.SerifCoverage,0)+",\"pixel_custom\":"+face("fonts/pixel.ttf",pixelHash,pixelCoverage,12)+"}}");
  TextStyles.Load(temp);Need((string)TextStyles.Status()["sans"]=="ready"&&(string)TextStyles.Status()["serif"]=="ready"&&(string)((Hashtable)TextStyles.Status()["font_status"])["pixel_custom"]=="ready","hash-bound native font resources loaded");
  Need(TextStyles.FontFor("sans")==sans&&TextStyles.FontFor("serif")==serif,"exact resource instances, no OS lookup");Need(pixel.material.mainTexture.filterMode==UnityEngine.FilterMode.Point,"pixel atlas point filtering");
  var load=typeof(TextStyles).GetMethod("LoadFace",flags);File.WriteAllText(Path.Combine(temp,"serif.ttf"),"changed");Need((string)load.Invoke(null,new object[]{temp,"other","serif.ttf",CW3StyleFonts.SerifHash,CW3StyleFonts.SerifCoverage,"Serif",0,0})=="hash_mismatch","changed TTF rejected");
  Need((string)load.Invoke(null,new object[]{temp,"other","absent.ttf",CW3StyleFonts.SerifHash,CW3StyleFonts.SerifCoverage,"Serif",0,0})=="missing","missing font falls back");
  typeof(TextStyles).GetField("assetsValid",flags).SetValue(null,false);Need((string)load.Invoke(null,new object[]{temp,"other","font.ttf",CW3StyleFonts.SansHash,CW3StyleFonts.SansCoverage,"Sans",0,0})=="resource_hash_mismatch","wrong serialized font bytes rejected");Directory.Delete(temp,true);

  var policy=TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"body\":{\"font\":\"serif\",\"size_percent\":125},\"ui\":{\"font\":\"pixel_custom\",\"size_percent\":75}}}");typeof(TextStyles).GetField("policy",flags).SetValue(null,policy);
  var native=new UIFont{gameObject=new UnityEngine.GameObject("native"),dynamicFont=new UnityEngine.Font{name="Embedded"},dynamicFontSize=20};
  var body=Make("MessageText",native);var body2=Make("MessageText",native);var title=Make("CharacterName",native);TextStyles.Label(body,"中","UI/MessageDialog/MessageText");TextStyles.Label(body2,"中","UI/MessageDialog/MessageText");TextStyles.Label(title,"中","UI/MessageDialog/CharacterName");
  Need(body.font!=native&&body.font!=title.font&&body.font==body2.font,"UIFont isolation and reuse");Need(native.dynamicFont.name=="Embedded"&&native.dynamicFontSize==20,"shared native UIFont unchanged");Need(body.transform.localScale.x==25&&title.transform.localScale.x==20,"role scales independent");
  for(int i=0;i<5;i++)TextStyles.Label(body,"中","UI/MessageDialog/MessageText");Need(body.transform.localScale.x==25,"repeat ProcessText never multiplies again");TextStyles.Label(body,"雪","UI/MessageDialog/MessageText");Need(body.font.dynamicFont==sans&&body2.font.dynamicFont==serif,"source cmap forces per-control fallback even when Unity HasCharacter reports true");
  var menu=Make("ButtonLabel",native);TextStyles.Label(menu,"中","Menu/ButtonLabel");Need(menu.font.dynamicFont==pixel&&menu.font.dynamicFontSize==12&&menu.transform.localScale.x==12,"pixel menu aligned 12px");
  var gui=new UnityEngine.GUIStyle{padding=7,wordWrap=true};var styled=TextStyles.Gui(gui,"中","ui");Need(gui.font==null&&gui.fontSize==0&&styled.font==pixel&&styled.fontSize==12&&styled.padding==7&&styled.wordWrap,"GUIStyle copy preserves caller");
  var code=TextStyles.Gui(gui,"中","code_input");Need(code.font==sans&&code.fontSize==13&&gui.font==null,"code input ignores menu style and preserves metrics");gui.font=new UnityEngine.Font{name="explicit"};Need(TextStyles.Gui(gui,"中","code_input").font==gui.font,"explicit input font retained");Need(Object.ReferenceEquals(TextStyles.Gui(gui,"中","code_input"),gui),"unchanged explicit code style reused");var matching=TextStyles.Gui(new UnityEngine.GUIStyle(),"中","ui");Need(Object.ReferenceEquals(TextStyles.Gui(matching,"中","ui"),matching),"already resolved style reused");
  foreach(string role in new[]{"body","title","ui","status"}){var all=TextStylePolicy.Parse("{\"format\":1,\"roles\":{\""+role+"\":{\"font\":\"pixel_custom\",\"size_percent\":100}}}");typeof(TextStyles).GetField("policy",flags).SetValue(null,all);Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"中",role).font==pixel,"any role uses registered pixel font");Need(TextStyles.Gui(new UnityEngine.GUIStyle(),"雪",role).font==sans,"missing custom glyph falls back for each role");}
  pixel.material.mainTexture.filterMode=UnityEngine.FilterMode.Bilinear;TextStyles.Rebuilt(pixel);Need(pixel.material.mainTexture.filterMode==UnityEngine.FilterMode.Point,"custom pixel metadata survives rebuild");
  TextStyles.ReleaseLabel(body2.GetInstanceID());Need(body.font.dynamicFont==sans,"releasing shared owner preserves survivor");Need((bool)TextStyles.Status()["diagnostics"]==false,"diagnostics default disabled");
  typeof(TextStyles).GetField("policy",flags).SetValue(null,new TextStylePolicy());
  var hot=Make("MessageText",native);hot.text="中";TextStyles.Label(hot,hot.text,"UI/MessageDialog/MessageText");
  var mesh=new UnityEngine.TextMesh{name="EnergyLabel",gameObject=new UnityEngine.GameObject("EnergyLabel"),font=sans,fontSize=40,text="已显示标题"};TextStyles.Mesh(mesh,mesh.text,"title");int materialUpdates=0;
  Action<UnityEngine.Component> prepare=c=>{var l=(Label)c;TextStyles.Label(l,l.text,"UI/MessageDialog/"+l.name);};
  foreach(int percent in new[]{150,75,100,150,75,100}){var saved=new TextStylePolicy();saved.Change("body","serif",percent,0);saved.Change("title","serif",percent,0);var report=TextStyles.ApplySizes(saved,prepare,m=>materialUpdates++);Need(TextStyles.ActivePolicy().For("body").Family=="sans","mixed save keeps active font");Need(hot.transform.localScale.x==20*percent/100f,"live size uses original scale every time");Need(mesh.fontSize==40*percent/100&&mesh.text=="已显示标题","named mesh remembered role and display survive refresh");Need((int)report["failures"]==0&&hot.marks>0,"existing labels invalidate native caches");}
  var same=TextStyles.ApplySizes(new TextStylePolicy(),prepare,m=>materialUpdates++);Need((int)same["labels"]==0&&(int)same["meshes"]==0,"unchanged save does not refresh controls");
  var sizes=new TextStylePolicy();sizes.Change("body","sans",125,0);TextStyles.ApplySizes(sizes,prepare,m=>materialUpdates++);var later=Make("MessageText",native);TextStyles.Label(later,"中","UI/MessageDialog/MessageText");Need(later.transform.localScale.x==25,"new label adopts live policy");
  typeof(TextStyles).GetField("policy",flags).SetValue(null,TextStylePolicy.Parse("{\"format\":1,\"roles\":{\"ui\":{\"font\":\"pixel_custom\",\"size_percent\":100}}}"));var px=Make("ButtonLabel",native);px.transform.localScale=new UnityEngine.Vector3(32,32,1);px.text="中";TextStyles.Label(px,px.text,"UI/ButtonLabel");foreach(int percent in new[]{150,75,100}){var s2=new TextStylePolicy();s2.Change("ui","serif",percent,0);TextStyles.ApplySizes(s2,prepare,m=>materialUpdates++);Need(px.transform.localScale.x==TextStylePolicy.PixelSize(32,percent,12),"live pixel size snaps from original baseline");}
  // Exercise the same Label -> layout -> Fitted order as CW3Runtime, including live ApplySizes.
  Action<UnityEngine.Component> prepareTitle=c=>{var l=(Label)c;TextStyles.Label(l,l.text,"UI/"+l.transform.parent.name+"/"+l.name);CaptionLayout.PrepareStyled(l,l.text,TextStyles.Percent(l),TextStyles.LabelPixelUnit(l));TextStyles.Fitted(l);};
  foreach(bool explicitUnit in new[]{false,true})foreach(string name in new[]{"CharacterName","MapTitleLabel"}){
   var titlePolicy=new TextStylePolicy();titlePolicy.Change("title",explicitUnit?"sans":"pixel_custom",100,explicitUnit?12:0);typeof(TextStyles).GetField("policy",flags).SetValue(null,titlePolicy);
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
  Console.WriteLine("PASS pixel title layout/live-size integration, semantic policy, defaults, native isolation/reuse, stable scales, per-control glyph fallback, pixel menu, GUI copies and input metrics");
 }
}
