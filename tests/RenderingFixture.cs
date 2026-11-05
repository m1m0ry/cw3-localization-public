using System;
using System.Collections.Generic;
using System.Reflection;
// Minimal managed Unity boundary for rendering identity/lifetime contracts.
namespace UnityEngine {
 public enum HideFlags {DontSave}
 public class Object {
  static int next;readonly int id=++next;public string name;public bool Destroyed;public HideFlags hideFlags;
  public int GetInstanceID(){return id;}
  public static void Destroy(Object o){if(ReferenceEquals(o,null))return;o.Destroyed=true;var m=o.GetType().GetMethod("OnDestroy",BindingFlags.Instance|BindingFlags.NonPublic);if(m!=null)m.Invoke(o,null);}
  public static Object[] FindObjectsOfType(Type t){var result=new List<Object>();foreach(var c in Component.All)if(c!=null&&t.IsInstanceOfType(c))result.Add(c);return result.ToArray();}
  public static bool operator==(Object a,Object b){bool x=ReferenceEquals(a,null)||a.Destroyed,y=ReferenceEquals(b,null)||b.Destroyed;return x||y?x==y:ReferenceEquals(a,b);}
  public static bool operator!=(Object a,Object b){return !(a==b);}public override bool Equals(object b){return ReferenceEquals(this,b);}public override int GetHashCode(){return id;}
 }
 public class GameObject:Object {
  internal readonly List<Component> Components=new List<Component>();public Transform transform;
  public GameObject(string name){this.name=name;transform=AddComponent<Transform>();}
  public T AddComponent<T>() where T:Component,new(){var c=new T{gameObject=this,name=name};Components.Add(c);Component.All.Add(c);return c;}
  public T GetComponent<T>() where T:Component{foreach(var c in Components)if(c!=null&&c is T)return (T)c;return null;}
 }
 public class Component:Object {
  internal static readonly List<Component> All=new List<Component>();public GameObject gameObject;public Transform transform{get{return gameObject.transform;}}
  public T GetComponent<T>() where T:Component{return gameObject.GetComponent<T>();}
  public T[] GetComponents<T>(){var result=new List<T>();foreach(var c in gameObject.Components)if(c is T)result.Add((T)(object)c);return result.ToArray();}
 }
 public class MonoBehaviour:Component {}public struct Vector3{public float z;public Vector3(float z){this.z=z;}}
 public class Transform:Component{public Transform parent;public Vector3 position;}
 public class Texture:Object{}public class Material:Object{public Texture mainTexture;public int renderQueue;public Material(){}public Material(Material s){name=s.name;mainTexture=s.mainTexture;renderQueue=s.renderQueue;}}
 public class Font:Object{public static event Action<Font> textureRebuilt;public static void Rebuild(Font f){if(textureRebuilt!=null)textureRebuilt(f);}}
}
public class UIPanel:UnityEngine.Component{}
public class UIWidget:UnityEngine.Component{public UIPanel mPanel;public int mDepth;}
public class UIFont{public UnityEngine.Font dynamicFont{get;set;}}
public class UILabel:UIWidget{public UIFont mFont;public int Changed;public void MarkAsChanged(){Changed++;}}
public class UIDrawCall:UnityEngine.Component{public UnityEngine.Material mSharedMat,mClippedMat;}
