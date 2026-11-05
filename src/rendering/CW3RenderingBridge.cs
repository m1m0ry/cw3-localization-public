using System;
using UnityEngine;

// Native Mac's stable signed ABI. Bind once per process; the implementation owns
// materials, event subscriptions and panel lifetimes in the external runtime.
// Warm dispatch adds no reflection, lookup, allocation or filesystem IO; the
// renderer retains its own implementation costs.
public static class CW3Rendering {
 static readonly Func<Material,object,Material> ordered;
 static readonly Action<object> sync;
 static CW3Rendering(){CW3Runtime.BindRenderingV1(out ordered,out sync);}

 public static Material Ordered(Material source,object widget){
  return ordered==null?source:ordered(source,widget);
 }
 public static void SyncDrawCall(object drawCall){if(sync!=null)sync(drawCall);}
}
