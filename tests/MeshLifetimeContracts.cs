using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;

// Run the shipped runtime/styles against a managed Unity-object boundary.
// Destruction and lazy Renderer.material instances are simulated, not rendered.
namespace UnityEngine {
 public class Object {
  static int next;readonly int id=++next;public string name;public bool Destroyed;public int DestroyCalls;
  public int GetInstanceID(){return id;}
  public static void Destroy(Object value){if(ReferenceEquals(value,null))return;value.DestroyCalls++;value.Destroyed=true;var component=value as Component;if(component!=null){var method=component.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic);if(method!=null)method.Invoke(component,null);}}
  public static void DontDestroyOnLoad(Object value){}
  public static bool operator==(Object a,Object b){bool x=ReferenceEquals(a,null)||a.Destroyed,y=ReferenceEquals(b,null)||b.Destroyed;return x||y?x==y:ReferenceEquals(a,b);}
  public static bool operator!=(Object a,Object b){return !(a==b);}
  public override bool Equals(object value){return ReferenceEquals(this,value);}public override int GetHashCode(){return id;}
 }
 public enum HideFlags {HideAndDontSave}public enum FontStyle {Normal}public enum FilterMode {Bilinear,Point}public enum TextureFormat {ARGB32}
 public class GameObject:Object {
  readonly List<Component> components=new List<Component>();public bool activeInHierarchy=true;public int layer;public HideFlags hideFlags;public Transform transform;
  public GameObject(string value){name=value;transform=new Transform{gameObject=this,name=value};}
  public Component AddComponent(Type type){var c=(Component)Activator.CreateInstance(type);c.gameObject=this;c.name=name;components.Add(c);return c;}
  public T AddComponent<T>() where T:Component,new(){return (T)AddComponent(typeof(T));}
  public Component GetComponent(Type type){foreach(var c in components)if(c!=null&&type.IsInstanceOfType(c))return c;return null;}
  public Component GetComponent(string type){foreach(var c in components)if(c!=null&&c.GetType().Name==type)return c;return null;}
  public T[] GetComponentsInChildren<T>(bool inactive){var result=new List<T>();foreach(var c in components)if(c is T)result.Add((T)(object)c);return result.ToArray();}
  public void SetActive(bool value){activeInHierarchy=value;}public static GameObject Find(string value){return null;}
 }
 public class Component:Object {public GameObject gameObject;public Transform transform{get{return gameObject.transform;}}public T GetComponent<T>() where T:Component{return (T)gameObject.GetComponent(typeof(T));}public Component GetComponent(string name){return gameObject.GetComponent(name);}public T[] GetComponentsInChildren<T>(bool inactive){return gameObject.GetComponentsInChildren<T>(inactive);}}
 public class Behaviour:Component {public bool enabled=true;}public class MonoBehaviour:Behaviour {}
 public class Transform:Component {public Transform parent;public Vector3 localScale=Vector3.one,localPosition;public Transform Find(string name){return null;}}
 public struct Vector3 {public float x,y,z;public Vector3(float a,float b,float c){x=a;y=b;z=c;}public static Vector3 one{get{return new Vector3(1,1,1);}}public static bool operator==(Vector3 a,Vector3 b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}public static bool operator!=(Vector3 a,Vector3 b){return !(a==b);}public override bool Equals(object v){return v is Vector3&&this==(Vector3)v;}public override int GetHashCode(){return (int)x;}}
 public struct Vector2 {public float x,y;public Vector2(float a,float b){x=a;y=b;}public static Vector2 zero{get{return new Vector2(0,0);}}}
 public struct Bounds {public Vector3 size,min,max;}public struct Rect {public Rect(float a,float b,float c,float d){}}
 public struct Color {public Color(float a,float b,float c,float d){}public static Color white{get{return new Color(1,1,1,1);}}}
 public class Texture:Object {public FilterMode filterMode;}public class Texture2D:Texture {public Texture2D(int w,int h,TextureFormat format,bool mip){}public void SetPixel(int x,int y,Color c){}public void Apply(){}}
 public class Material:Object {public Texture mainTexture;public Material(){}public Material(Material source){mainTexture=source.mainTexture;}}
 public class Renderer:Component {public Bounds bounds;public Material sharedMaterial;public bool InstanceOnRead;public Material material{get{if(InstanceOnRead&&sharedMaterial!=null){sharedMaterial=new Material(sharedMaterial);InstanceOnRead=false;}return sharedMaterial;}}}
 public class Collider:Component {public Bounds bounds;}public class BoxCollider:Collider {public Vector3 size;}
 public struct CharacterInfo {public int advance;}
 public class Font:Object {public static event Action<Font> textureRebuilt;public Material material=new Material{mainTexture=new Texture()};public int fontSize=20,lineHeight=20;public bool dynamic=true;public string[] fontNames=new[]{"Fixture"};public void RequestCharactersInTexture(string text,int size,FontStyle style){}public bool GetCharacterInfo(char c,out CharacterInfo info,int size,FontStyle style){info=new CharacterInfo{advance=20};return true;}public static void Rebuild(Font font){if(textureRebuilt!=null)textureRebuilt(font);}}
 public class TextMesh:Component {public Font font;public int fontSize=20;public string text;}
 public class AssetBundle:Object {public static AssetBundle CreateFromFile(string file){return null;}public Object LoadAsset(string name,Type type){return null;}public void Unload(bool destroy){}}
 public class Camera:Behaviour {public Vector3 WorldToScreenPoint(Vector3 p){return p;}}
 public static class Application {public static string dataPath="/unused-fixture",loadedLevelName="Game";public static int loadedLevel=3;public static void OpenURL(string url){}}
 public static class Time {public static int frameCount=1;public static float realtimeSinceStartup;}
 public static class Debug {public static void Log(string value){}public static void LogWarning(string value){}}
 public static class Resources {public static Object Load(string name,Type type){return null;}public static Object[] FindObjectsOfTypeAll(Type type){return new Object[0];}}
 public static class Screen {public static int width=1280,height=720;}
 public class GUILayoutOption {}public class GUIContent {public string text;public GUIContent(string value){text=value;}}
 public class GUIStyleState {public Texture2D background;}
 public class GUIStyle {public string name;public Font font;public int fontSize;public bool wordWrap;public GUIStyleState normal=new GUIStyleState();public GUIStyle(){}public GUIStyle(GUIStyle value){font=value.font;fontSize=value.fontSize;wordWrap=value.wordWrap;}public Vector2 CalcSize(GUIContent text){return new Vector2(text.text.Length*13,13);}}
 public class GUISkin {public GUIStyle label=new GUIStyle(),button=new GUIStyle(),box=new GUIStyle(),toggle=new GUIStyle(),textField=new GUIStyle(),textArea=new GUIStyle();}
 public static class GUI {public static GUISkin skin=new GUISkin();public static bool enabled=true;public static int depth;public static Color color,contentColor,backgroundColor;public static void Box(params object[] a){}public static void Label(params object[] a){}public static bool Button(params object[] a){return false;}}
 public static class GUILayout {public static GUILayoutOption Width(float n){return new GUILayoutOption();}public static GUILayoutOption Height(float n){return new GUILayoutOption();}public static GUILayoutOption MinWidth(float n){return new GUILayoutOption();}public static void Label(params object[] a){}public static void Box(params object[] a){}public static bool Button(params object[] a){return false;}public static bool Toggle(bool value,params object[] a){return value;}public static string TextField(string value,params object[] a){return value;}public static string TextArea(string value,params object[] a){return value;}public static int SelectionGrid(int value,params object[] a){return value;}public static void BeginArea(params object[] a){}public static void EndArea(){}public static void BeginHorizontal(){}public static void EndHorizontal(){}public static Vector2 BeginScrollView(Vector2 value){return value;}public static void EndScrollView(){}public static void Space(float n){}}
 public enum KeyCode {Escape}public enum EventType {KeyDown}public class Event {public static Event current=new Event();public EventType type;public KeyCode keyCode;public void Use(){}}
 public static class Input {public static bool GetMouseButton(int n){return false;}public static bool GetKey(KeyCode key){return false;}}
}
public class SetColor:UnityEngine.Component {public UnityEngine.Material material;}
class NamedOwner {public string GUID="fixture-guid";}
class MeshLifetimeContracts {
 const BindingFlags Flags=BindingFlags.Static|BindingFlags.NonPublic;
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static object Field(Type type,string name){return type.GetField(name,Flags).GetValue(null);}
 static UnityEngine.TextMesh Mesh(string name,UnityEngine.Font font){var go=new UnityEngine.GameObject(name);var mesh=go.AddComponent<UnityEngine.TextMesh>();mesh.font=font;mesh.text="initial";return mesh;}
 static UnityEngine.Renderer Render(UnityEngine.TextMesh mesh,UnityEngine.Material material,bool instance){var renderer=mesh.gameObject.AddComponent<UnityEngine.Renderer>();renderer.sharedMaterial=material;renderer.InstanceOnRead=instance;return renderer;}
 static void Main(){
  typeof(CW3Runtime).GetField("loaded",Flags).SetValue(null,true);typeof(CW3Runtime).GetField("candidates",Flags).SetValue(null,new Candidates(false,"/unused-fixture/candidates.json"));
  var font=new UnityEngine.Font();((Dictionary<string,UnityEngine.Font>)Field(typeof(TextStyles),"fonts")).Add("sans",font);((Dictionary<int,BitArray>)Field(typeof(TextStyles),"coverage")).Add(font.GetInstanceID(),new BitArray(65536,true));
  var definitions=(Dictionary<string,Hashtable>)Field(typeof(CW3Runtime),"definitions");var translations=(Dictionary<string,string>)Field(typeof(CW3Runtime),"translations");var sources=(Dictionary<string,List<Hashtable>>)Field(typeof(CW3Runtime),"sources");
  foreach(string raw in new[]{"Alpha","Beta"}){var d=new Hashtable{{"id",raw},{"source",raw},{"kind","xml_text"},{"owner","NamedOwner"},{"guid","fixture-guid"}};definitions.Add(raw,d);translations.Add(raw,"translated "+raw);sources.Add(raw,new List<Hashtable>{d});}
  var owner=new NamedOwner();var noRenderer=Mesh("NoRenderer",font);CW3Runtime.SetNamedMesh(noRenderer,"Alpha",owner);
  Need(CW3Runtime.OriginalMesh(noRenderer)=="Alpha"&&noRenderer.text=="translated Alpha","Raw named source survives display without a renderer");
  Need((string)CW3Runtime.MeshReport(noRenderer)["status"]=="missing_renderer_material","Missing renderer is not material ownership");
  var borrowed=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};var renderer=Render(noRenderer,borrowed,false);var fade=noRenderer.gameObject.AddComponent<SetColor>();fade.material=borrowed;
  Need((string)CW3Runtime.MeshReport(noRenderer)["status"]=="ready","Remembered record alone does not claim a new renderer");
  for(int i=0;i<3;i++)CW3Runtime.SetNamedMesh(noRenderer,"Beta",owner);
  Need(CW3Runtime.OriginalMesh(noRenderer)=="Beta"&&noRenderer.text=="translated Beta","Repeated writes replace raw source, never capture translated text");
  Need(noRenderer.gameObject.GetComponentsInChildren<CW3MeshLifetime>(true).Length==1,"Exactly one lifetime owner");
  Need(renderer.sharedMaterial==borrowed&&!(bool)CW3Runtime.MeshReport(noRenderer)["material_owned"]&&fade.material==borrowed,"Game/SetColor instance remains borrowed");
  CW3Runtime.ReleaseMesh(noRenderer.GetInstanceID());CW3Runtime.ReleaseMesh(noRenderer.GetInstanceID());Need(borrowed.DestroyCalls==0,"Borrowed material destroyed");
  Need(CW3Runtime.OriginalMesh(noRenderer)==noRenderer.text,"Released source falls back to native getter");
  var mesh=Mesh("Owned",font);var shared=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};renderer=Render(mesh,shared,true);CW3Runtime.SetNamedMesh(mesh,"Alpha",owner);var created=renderer.sharedMaterial;
  Need(created!=shared&&(bool)CW3Runtime.MeshReport(mesh)["material_owned"],"Lazy material instance is tracked as owned");
  CW3Runtime.SetNamedMesh(mesh,"Alpha",owner);Need(renderer.sharedMaterial==created,"Repeated text allocates no second material");
  var replacement=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};renderer.sharedMaterial=replacement;
  Need((string)CW3Runtime.MeshReport(mesh)["status"]=="renderer_material_changed","External material replacement detected");
  CW3Runtime.SetNamedMesh(mesh,"Beta",owner);Need(renderer.sharedMaterial==replacement&&!(bool)CW3Runtime.MeshReport(mesh)["material_owned"],"Replacement becomes borrowed while older owned instance is retained");
  UnityEngine.Object.Destroy(mesh.gameObject.GetComponent(typeof(CW3MeshLifetime)));CW3Runtime.ReleaseMesh(mesh.GetInstanceID());
  Need(created.DestroyCalls==1&&shared.DestroyCalls==0&&replacement.DestroyCalls==0&&!font.material.mainTexture.Destroyed,"Release destroys each owned material once and preserves borrowed materials/atlas");
  var absent=Mesh("InitiallyEmpty",font);renderer=Render(absent,null,false);CW3Runtime.SetMesh(absent,null);var generated=renderer.sharedMaterial;
  Need(CW3Runtime.OriginalMesh(absent)==null&&generated!=null&&(bool)CW3Runtime.MeshReport(absent)["material_owned"],"Null raw source and material creation remain distinguishable");
  UnityEngine.Object.Destroy(absent);CW3Runtime.Scene();CW3Runtime.ReleaseMesh(absent.GetInstanceID());Need(generated.DestroyCalls==1,"Scene cleanup and repeated release destroy owned material once");
  Console.WriteLine("PASS shipped runtime/styles with simulated Unity lifetimes: raw/display separation, missing renderer, repeated writes, borrowed/lazy/replaced materials and idempotent release");
 }
}
