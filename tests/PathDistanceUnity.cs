using System;
using System.Runtime.CompilerServices;
namespace UnityEngine {
 public struct Vector3 {public float x,y,z;public Vector3(float x,float y,float z){this.x=x;this.y=y;this.z=z;}}
 public class Transform {
  public Vector3 value;public int reads;public bool fail;public string name;
  [MethodImpl(MethodImplOptions.NoInlining)] public Vector3 Read(){reads++;Component.Record("position:"+name);if(fail)throw new InvalidOperationException(name);return value;}
  public Vector3 localPosition {get{return Read();}}
 }
 public class Component {
  public Transform target;public int reads;public bool fail;public string name;public static string trace;
  public static void Record(string value){if(trace!=null)trace+=value+",";}
  [MethodImpl(MethodImplOptions.NoInlining)] public Transform Read(){reads++;Record("transform:"+name);if(fail)throw new InvalidOperationException(name);return target;}
  public Transform transform {get{return Read();}}
 }
 public static class Mathf {public static float Sqrt(float v){return (float)Math.Sqrt(v);}}
}
