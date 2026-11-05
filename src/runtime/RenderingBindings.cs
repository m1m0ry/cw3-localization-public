using System;
using UnityEngine;

// A versioned pair, not a general plugin API. Future incompatible contracts get
// a new entry point; V1's Unity-only signatures and ownership stay unchanged.
public static partial class CW3Runtime {
 public static void BindRenderingV1(out Func<Material,object,Material> ordered,out Action<object> sync){
  ordered=CW3RenderingImplementation.Ordered;
  sync=CW3RenderingImplementation.SyncDrawCall;
 }
}
