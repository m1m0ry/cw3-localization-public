using System;
using System.Reflection;
using UnityEngine;

// The facade is tested with the real external renderer and its V1 binding. This
// has no game IO: all Unity ownership/lifetime behavior comes from the fixture.
class RenderingBridgeContracts {
 static int checks;
 static void Need(bool ok,string text){if(!ok)throw new Exception(text);checks++;}
 static void Main(){
  var panel=new GameObject("panel").AddComponent<UIPanel>();
  var label=new GameObject("label").AddComponent<UILabel>();label.mPanel=panel;label.mDepth=3;label.transform.parent=panel.transform;
  var source=new Material{name="font"};var result=CW3Rendering.Ordered(source,label);
  Need(result!=source,"external renderer owns a copy");
  Need(result==CW3RenderingImplementation.Ordered(source,label),"facade and implementation share one material state");
  var draw=new GameObject("draw").AddComponent<UIDrawCall>();draw.mSharedMat=result;draw.mClippedMat=new Material();
  CW3Rendering.SyncDrawCall(draw);Need(draw.mClippedMat.renderQueue==result.renderQueue,"clipped queue through facade");
  var font=new Font();label.mFont=new UIFont{dynamicFont=font};Font.Rebuild(font);Need(label.Changed==1,"one font subscription");
  Need(CW3Rendering.Ordered(null,label)==null,"null source");Need(CW3Rendering.Ordered(source,null)==source,"unknown widget");
  for(int i=0;i<1000;i++)Need(CW3Rendering.Ordered(source,label)==result,"stable material");
  var lifetime=panel.GetComponent<CW3RenderingLifetime>();Need(lifetime!=null,"external lifetime component attached");
  UnityEngine.Object.Destroy(lifetime);Need(result==null&&source!=null,"lifetime releases own copy not source");
  Need(CW3Rendering.Ordered(source,label)!=result,"new lifecycle can recreate copy");
  if(Environment.GetEnvironmentVariable("CW3_BENCH_RENDER_BRIDGE")=="1"){
   Func<Material> direct=()=>CW3RenderingImplementation.Ordered(source,label),facade=()=>CW3Rendering.Ordered(source,label);
   // Alternate order in one warm process so startup/temperature drift is visible.
   for(int round=0;round<6;round++){
    if(round%2==0){Bench("direct",direct);Bench("facade",facade);}
    else{Bench("facade",facade);Bench("direct",direct);}
   }
  }
  Console.WriteLine("PASS "+checks+" external renderer bridge/lifetime checks");
 }
 static void Bench(string name,Func<Material> query){
  for(int i=0;i<10000;i++)query();GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();
  var getter=typeof(GC).GetMethod("GetAllocatedBytesForCurrentThread",BindingFlags.Public|BindingFlags.Static);
  var allocated=getter==null?null:(Func<long>)Delegate.CreateDelegate(typeof(Func<long>),getter);
  var process=System.Diagnostics.Process.GetCurrentProcess();var cpu=process.TotalProcessorTime;
  int before=GC.CollectionCount(0);var watch=new System.Diagnostics.Stopwatch();long memory=allocated==null?0:allocated();watch.Start();
  for(int i=0;i<300000;i++)query();watch.Stop();long bytes=allocated==null?-1:allocated()-memory;
  Console.WriteLine(name+" 300000 queries: "+watch.Elapsed.TotalMilliseconds.ToString("F2",System.Globalization.CultureInfo.InvariantCulture)+" ms; CPU="+(process.TotalProcessorTime-cpu).TotalMilliseconds.ToString("F2",System.Globalization.CultureInfo.InvariantCulture)+" ms; allocated="+bytes+" bytes; Gen0="+(GC.CollectionCount(0)-before));
 }
}
