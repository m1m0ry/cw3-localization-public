using System;
using System.Diagnostics;
using System.Reflection;
using UnityEngine;
class RenderingCacheContracts {
 static int assertions;
 static void Need(bool value,string reason){assertions++;if(!value)throw new Exception(reason);}
 class Base {private int hidden=1;public int Mutable=2;public int Use(){return hidden;}}
 class BareWidget:Component {public int mDepth;}
 class Derived:Base {private int hidden=3;public int UseDerived(){return hidden;}}
 static object Field(object o,string n){return typeof(CW3Rendering).GetMethod("Field",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,new[]{o,(object)n});}
 static T Widget<T>(UIPanel panel,string name,int depth)where T:UIWidget,new(){var g=new GameObject(name);g.transform.parent=panel.transform;var w=g.AddComponent<T>();w.mPanel=panel;w.mDepth=depth;return w;}
 static void Main(string[] args){
  var b=new Base();var d=new Derived();Need((int)Field(b,"hidden")==1,"private base field");Need((int)Field(d,"hidden")==3,"hidden derived field");Need((int)Field(d,"Mutable")==2,"inherited field");d.Mutable=7;Need((int)Field(d,"Mutable")==7,"cache metadata, not values");Need(Field(d,"absent")==null&&Field(d,"absent")==null,"negative lookup");Need(Field(null,"absent")==null,"null receiver");
  var panel=new GameObject("panel").AddComponent<UIPanel>();var source=new Material{name="atlas",mainTexture=new Texture()};var a=Widget<UIWidget>(panel,"a",2);var same=Widget<UIWidget>(panel,"same",2);same.transform.parent=a.transform;var label=Widget<UILabel>(panel,"label",2);label.transform.parent=a.transform;
  #if !BASELINE
  var keyA=new CW3Rendering.MaterialKey(1,0,0,0,0);var keyB=new CW3Rendering.MaterialKey(0,397,0,0,0);
  Need(keyA.GetHashCode()==keyB.GetHashCode()&&!keyA.Equals(keyB),"collision retains identity");
  var keys=new System.Collections.Generic.Dictionary<CW3Rendering.MaterialKey,int>();keys.Add(keyA,1);keys.Add(keyB,2);Need(keys[keyA]==1&&keys[keyB]==2,"collision dictionary lookup");
#endif
  var first=CW3Rendering.Ordered(source,a);Need(first!=source,"owned material");Need(CW3Rendering.Ordered(source,a)==first,"repeat identity");Need(CW3Rendering.Ordered(first,a)==first,"unwrap own copy");Need(CW3Rendering.Ordered(source,same)==first,"same layer/depth batches");
  var text=CW3Rendering.Ordered(source,label);Need(text!=first&&text.renderQueue>first.renderQueue,"text tie follows atlas");
  same.mDepth=3;var deeper=CW3Rendering.Ordered(source,same);Need(deeper!=first&&deeper.renderQueue>text.renderQueue,"depth change observed");same.mDepth=2;Need(CW3Rendering.Ordered(source,same)==first,"return to previous key");
  var other=Widget<UIWidget>(panel,"other",0);other.transform.position=new Vector3(-1);var front=CW3Rendering.Ordered(source,other);Need(front.renderQueue>deeper.renderQueue,"foreground layer");other.transform.position=new Vector3(1);CW3Rendering.Ordered(source,other);Need(front.renderQueue<first.renderQueue,"z move reorders");
  var alternateSource=new Material{name="other source"};Need(CW3Rendering.Ordered(alternateSource,a)!=first,"source identity isolation");
  var alternateLayer=Widget<UIWidget>(panel,"alternate layer",2);Need(CW3Rendering.Ordered(source,alternateLayer)!=first,"layer identity isolation");
  var alternatePanel=new GameObject("other panel").AddComponent<UIPanel>();same.mPanel=alternatePanel;var changedPanel=CW3Rendering.Ordered(source,same);Need(changedPanel!=first,"panel change observed");same.mPanel=panel;Need(CW3Rendering.Ordered(source,same)==first,"panel restoration observed");
  var bare=new GameObject("bare").AddComponent<BareWidget>();bare.transform.parent=panel.transform;bare.mDepth=2;Need(CW3Rendering.Ordered(source,bare)!=source,"missing mPanel uses parent lookup");Need(CW3Rendering.Ordered(source,bare)==CW3Rendering.Ordered(source,bare),"negative field cache keeps parent lookup");
  CW3Rendering.ReleasePanel(alternatePanel.GetInstanceID());Need(changedPanel==null&&first!=null,"panel release isolation");
  var texture=new Texture();source.mainTexture=texture;Need(CW3Rendering.Ordered(source,a).mainTexture==texture,"texture change observed");
  var call=new GameObject("draw").AddComponent<UIDrawCall>();call.mSharedMat=first;call.mClippedMat=new Material();CW3Rendering.SyncDrawCall(call);Need(call.mClippedMat.renderQueue==first.renderQueue,"clip queue sync");call.mSharedMat=text;CW3Rendering.SyncDrawCall(call);Need(call.mClippedMat.renderQueue==text.renderQueue,"clip source change observed");
  var font=new Font();label.mFont=new UIFont{dynamicFont=font};Font.Rebuild(font);Need(label.Changed==1,"font refresh preserved");label.mFont=new UIFont{dynamicFont=new Font()};Font.Rebuild(font);Need(label.Changed==1,"font replacement observed");
  if(args.Length>0&&args[0]=="--benchmark"){
   for(int i=0;i<10000;i++)CW3Rendering.Ordered(source,a);
   GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();int collections=GC.CollectionCount(0);var watch=Stopwatch.StartNew();
   for(int i=0;i<300000;i++)if(CW3Rendering.Ordered(source,a)!=first)throw new Exception("identity drift");watch.Stop();Console.WriteLine("BENCH 300000 warm material queries: "+watch.Elapsed.TotalMilliseconds.ToString("F1",System.Globalization.CultureInfo.InvariantCulture)+" ms; gen0 collections "+(GC.CollectionCount(0)-collections));
  }
  CW3Rendering.ReleasePanel(panel.GetInstanceID());Need(first==null&&text==null&&deeper==null&&front==null,"release copies");Need(source!=null&&texture!=null,"borrowed resources survive");Need(CW3Rendering.Ordered(source,a)!=first,"recreate after release");
  Console.WriteLine("PASS "+assertions+" rendering identity, mutation, ordering, font and lifetime contracts");
 }
}
