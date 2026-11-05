using System;using System.Reflection;using System.Collections.Generic;using UnityEngine;
// Old NGUI batches an entire panel by material. A separate dynamic font material
// therefore loses the interleaved widget depth order of its original atlas.
#if CW3_RENDER_EXTERNAL
internal static class CW3RenderingImplementation {
#else
public static class CW3Rendering {
#endif
 static BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 class Entry {public Material source,copy;public Component panel;public Transform layer;public float z;public int depth,tie,panelId;}
 // Identity, not formatting: avoid allocating five decimal strings and a joined key
 // on each material query. Equality retains every dimension of the old key.
 internal struct MaterialKey:IEquatable<MaterialKey> {
  readonly int source,panel,layer,depth,tie;
  internal MaterialKey(int source,int panel,int layer,int depth,int tie){this.source=source;this.panel=panel;this.layer=layer;this.depth=depth;this.tie=tie;}
  public bool Equals(MaterialKey other){return source==other.source&&panel==other.panel&&layer==other.layer&&depth==other.depth&&tie==other.tie;}
  public override bool Equals(object value){return value is MaterialKey&&Equals((MaterialKey)value);}
  public override int GetHashCode(){unchecked{int hash=source;hash=hash*397^panel;hash=hash*397^layer;hash=hash*397^depth;return hash*397^tie;}}
 }
 sealed class TypeFields {
  internal readonly Type Type;internal readonly bool IsLabel;
  internal readonly Dictionary<string,FieldInfo> Fields=new Dictionary<string,FieldInfo>();
  internal TypeFields(Type type){Type=type;IsLabel=type.Name=="UILabel";}
 }
 static readonly Dictionary<Type,TypeFields> fields=new Dictionary<Type,TypeFields>();
 static TypeFields Metadata(Type type){TypeFields value;if(!fields.TryGetValue(type,out value)){value=new TypeFields(type);fields.Add(type,value);}return value;}
 static Dictionary<MaterialKey,Entry> entries=new Dictionary<MaterialKey,Entry>();static Dictionary<int,Material> originals=new Dictionary<int,Material>();static bool subscribed;
#if CW3_RENDER_EXTERNAL
 // Read only on explicit diagnostics requests, never per frame.
 internal static int CachedMaterialCount {get{return entries.Count;}}
#endif
 // Cache metadata only, never field values: panel/depth/material changes must
 // remain visible on the next query. Runtime type preserves hidden-field lookup.
 static object Field(object o,string n){
  return o==null?null:ReadField(o,n,Metadata(o.GetType()));
 }
 static object ReadField(object o,string n,TypeFields metadata){
  FieldInfo field;if(!metadata.Fields.TryGetValue(n,out field)){
   for(Type t=metadata.Type;t!=null;t=t.BaseType){field=t.GetField(n,flags|BindingFlags.DeclaredOnly);if(field!=null)break;}
   metadata.Fields.Add(n,field);
  }
  return field==null?null:field.GetValue(o);
 }
 static Component Panel(Component w,TypeFields metadata){Component p=ReadField(w,"mPanel",metadata) as Component;if(p!=null)return p;for(Transform t=w.transform;t!=null;t=t.parent)foreach(Component c in t.GetComponents<Component>())if(c!=null&&c.GetType().Name=="UIPanel")return c;return null;}
 // A dialog can sit in front of its panel through its direct child transform.
 static Transform Layer(Component w,Component panel){
  // Resolve native properties once per visited node. This is call-local only:
  // reparenting and panel changes remain visible on the very next material query.
  Transform panelTransform=panel.transform,layer=w.transform;
  while(true){Transform parent=layer.parent;if(parent==panelTransform)return layer;if(parent==null)return panelTransform;layer=parent;}
 }
 internal static int CompareOrder(float az,float bz,int ad,int bd,int at,int bt){int z=bz.CompareTo(az);if(z!=0)return z;int d=ad.CompareTo(bd);return d!=0?d:at.CompareTo(bt);}
 static int Compare(Entry a,Entry b){return CompareOrder(a.z,b.z,a.depth,b.depth,a.tie,b.tie);}
 static void Release(Entry entry){if(entry.copy!=null){originals.Remove(entry.copy.GetInstanceID());UnityEngine.Object.Destroy(entry.copy);}}
 internal static void ReleasePanel(int panelId){var gone=new List<MaterialKey>();foreach(var pair in entries)if(pair.Value.panelId==panelId){Release(pair.Value);gone.Add(pair.Key);}foreach(MaterialKey key in gone)entries.Remove(key);Reorder();}
 static void Reorder(){var list=new List<Entry>();var dead=new List<MaterialKey>();foreach(var pair in entries){var e=pair.Value;if(e.panel==null||e.layer==null||e.source==null){Release(e);dead.Add(pair.Key);}else{e.z=e.layer.position.z;list.Add(e);}}foreach(MaterialKey k in dead)entries.Remove(k);list.Sort(Compare);int rank=0;Entry previous=null;foreach(var e in list){if(previous!=null&&Compare(previous,e)!=0)rank++;if(rank>1900)throw new InvalidOperationException("CW3 UI order exceeds bounded queue range");e.copy.renderQueue=3000+rank;previous=e;}}
 public static Material Ordered(Material source,object value){
  if(source==null)return null;Component w=value as Component;if(w==null)return source;// Type names are immutable metadata. Old Mono creates a string for Name on
  // every query; resolve once without retaining or caching mutable widget state.
  TypeFields metadata=Metadata(w.GetType());Component panel=Panel(w,metadata);if(panel==null)return source;
  Material original;if(originals.TryGetValue(source.GetInstanceID(),out original))source=original;
  int depth=(int)ReadField(w,"mDepth",metadata);int tie=metadata.IsLabel?1:0;Transform layer=Layer(w,panel);
  var key=new MaterialKey(source.GetInstanceID(),panel.GetInstanceID(),layer.GetInstanceID(),depth,tie);Entry e;
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
public sealed class CW3RenderingLifetime:MonoBehaviour {
 internal int PanelId;
 void OnDestroy(){
#if CW3_RENDER_EXTERNAL
  CW3RenderingImplementation.ReleasePanel(PanelId);
#else
  CW3Rendering.ReleasePanel(PanelId);
#endif
 }
}
