using System;using System.Reflection;using System.Collections.Generic;using UnityEngine;
// Old NGUI batches an entire panel by material. A separate dynamic font material
// therefore loses the interleaved widget depth order of its original atlas.
public static class CW3Rendering {
 static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 class Entry {public Material source,copy;public Component panel;public Transform layer;public float z;public int depth,tie,panelId;}
 static Dictionary<string,Entry> entries=new Dictionary<string,Entry>();static Dictionary<int,Material> originals=new Dictionary<int,Material>();static bool subscribed;
 static object Field(object o,string n){if(o==null)return null;for(Type t=o.GetType();t!=null;t=t.BaseType){var f=t.GetField(n,flags|BindingFlags.DeclaredOnly);if(f!=null)return f.GetValue(o);}return null;}
 static Component Panel(Component w){Component p=Field(w,"mPanel") as Component;if(p!=null)return p;for(Transform t=w.transform;t!=null;t=t.parent)foreach(Component c in t.GetComponents<Component>())if(c!=null&&c.GetType().Name=="UIPanel")return c;return null;}
 // A dialog can sit in front of its panel through its direct child transform.
 static Transform Layer(Component w,Component panel){Transform layer=w.transform;while(layer.parent!=null&&layer.parent!=panel.transform)layer=layer.parent;return layer.parent==panel.transform?layer:panel.transform;}
 internal static int CompareOrder(float az,float bz,int ad,int bd,int at,int bt){int z=bz.CompareTo(az);if(z!=0)return z;int d=ad.CompareTo(bd);return d!=0?d:at.CompareTo(bt);}
 static int Compare(Entry a,Entry b){return CompareOrder(a.z,b.z,a.depth,b.depth,a.tie,b.tie);}
 static void Release(Entry entry){if(entry.copy!=null){originals.Remove(entry.copy.GetInstanceID());UnityEngine.Object.Destroy(entry.copy);}}
 internal static void ReleasePanel(int panelId){var gone=new List<string>();foreach(var pair in entries)if(pair.Value.panelId==panelId){Release(pair.Value);gone.Add(pair.Key);}foreach(string key in gone)entries.Remove(key);Reorder();}
 static void Reorder(){var list=new List<Entry>();var dead=new List<string>();foreach(var pair in entries){var e=pair.Value;if(e.panel==null||e.layer==null||e.source==null){Release(e);dead.Add(pair.Key);}else{e.z=e.layer.position.z;list.Add(e);}}foreach(string k in dead)entries.Remove(k);list.Sort(Compare);int rank=0;Entry previous=null;foreach(var e in list){if(previous!=null&&Compare(previous,e)!=0)rank++;if(rank>1900)throw new InvalidOperationException("CW3 UI order exceeds bounded queue range");e.copy.renderQueue=3000+rank;previous=e;}}
 public static Material Ordered(Material source,object value){
  if(source==null)return null;Component w=value as Component;if(w==null)return source;Component panel=Panel(w);if(panel==null)return source;
  Material original;if(originals.TryGetValue(source.GetInstanceID(),out original))source=original;
  int depth=(int)Field(w,"mDepth");int tie=w.GetType().Name=="UILabel"?1:0;Transform layer=Layer(w,panel);
  string key=source.GetInstanceID()+":"+panel.GetInstanceID()+":"+layer.GetInstanceID()+":"+depth+":"+tie;Entry e;
  if(!entries.TryGetValue(key,out e)){e=new Entry{source=source,copy=new Material(source),panel=panel,layer=layer,panelId=panel.GetInstanceID(),z=layer.position.z,depth=depth,tie=tie};e.copy.name=source.name+" [CW3 depth "+depth+"]";e.copy.hideFlags=HideFlags.DontSave;entries.Add(key,e);originals[e.copy.GetInstanceID()]=source;var lifetime=panel.GetComponent<CW3RenderingLifetime>();if(lifetime==null)lifetime=panel.gameObject.AddComponent<CW3RenderingLifetime>();lifetime.PanelId=panel.GetInstanceID();Reorder();}
  else if(e.z!=layer.position.z)Reorder();
  e.copy.mainTexture=source.mainTexture;
  if(!subscribed){Font.textureRebuilt+=FontRebuilt;subscribed=true;}
  return e.copy;
 }
 // Clipped NGUI materials are private copies. Preserve their shader/clip values
 // while keeping their queue in sync when another ordered batch is registered.
 public static void SyncDrawCall(object value){Component c=value as Component;if(c==null)return;Material shared=Field(value,"mSharedMat") as Material;if(shared==null||!originals.ContainsKey(shared.GetInstanceID()))return;Material clipped=Field(value,"mClippedMat") as Material;if(clipped!=null)clipped.renderQueue=shared.renderQueue;}
 static void FontRebuilt(Font font){foreach(Component c in UnityEngine.Object.FindObjectsOfType(typeof(Component))){if(c==null||c.GetType().Name!="UILabel")continue;object uiFont=Field(c,"mFont");if(uiFont==null)continue;var property=uiFont.GetType().GetProperty("dynamicFont",flags);if(property==null||property.GetValue(uiFont,null) as Font!=font)continue;var method=c.GetType().GetMethod("MarkAsChanged",flags,null,Type.EmptyTypes,null);if(method!=null)method.Invoke(c,null);}}
}
// Lifetime is the UIPanel owning our copies; never destroy its borrowed atlas or clip material.
public sealed class CW3RenderingLifetime:MonoBehaviour {internal int PanelId;void OnDestroy(){CW3Rendering.ReleasePanel(PanelId);}}
