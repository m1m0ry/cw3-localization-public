using System;
using System.Reflection;
using UnityEngine;

class RenderingAssemblyContracts {
 static void Need(bool ok,string text){if(!ok)throw new Exception(text);}
 static void Main(string[] args){
  var external=Assembly.LoadFrom(args[0]);var target=external.GetType("CW3Runtime",true);
  // Inject only the already-checked load target, so this fixture need not create
  // a real CW3.app or bypass the production ownership/path checks.
  const BindingFlags flags=BindingFlags.Static|BindingFlags.NonPublic;
  typeof(CW3Runtime).GetField("implementation",flags).SetValue(null,target);
  typeof(CW3Runtime).GetField("attempted",flags).SetValue(null,true);
  Need(typeof(CW3Rendering).Assembly!=external,"separate facade and implementation assemblies");
  foreach(var reference in typeof(CW3Rendering).Assembly.GetReferencedAssemblies())Need(reference.Name!="CW3ExternalRuntime","no static external dependency");
  var panel=new GameObject("panel").AddComponent<UIPanel>();var label=new GameObject("label").AddComponent<UILabel>();label.mPanel=panel;label.mDepth=3;label.transform.parent=panel.transform;
  var source=new Material{name="source"};var first=CW3Rendering.Ordered(source,label);Need(first!=source,"cold call before Boot works");
  var ordered=(Delegate)typeof(CW3Rendering).GetField("ordered",flags).GetValue(null);
  Need(ordered.Method.DeclaringType.Assembly==external,"delegate targets external implementation");
  Need(CW3Runtime.BridgeStatus()=="ready","binding succeeded");
  for(int i=0;i<10000;i++)Need(CW3Rendering.Ordered(source,label)==first,"single shared renderer state");
  Need(ReferenceEquals(ordered,typeof(CW3Rendering).GetField("ordered",flags).GetValue(null)),"warm calls keep same delegate");
  var draw=new GameObject("draw").AddComponent<UIDrawCall>();draw.mSharedMat=first;draw.mClippedMat=new Material();CW3Rendering.SyncDrawCall(draw);Need(draw.mClippedMat.renderQueue==first.renderQueue,"cross-assembly clip sync");
  Component lifetime=null;foreach(var component in panel.GetComponents<Component>())if(component.GetType().Name=="CW3RenderingLifetime")lifetime=component;
  Need(lifetime!=null&&lifetime.GetType().Assembly==external,"lifetime owned by external assembly");
  UnityEngine.Object.Destroy(lifetime);Need(first==null&&source!=null,"cross-assembly lifetime cleanup");
  Console.WriteLine("PASS separate rendering facade, real bridge and external assembly V1 binding");
 }
}
