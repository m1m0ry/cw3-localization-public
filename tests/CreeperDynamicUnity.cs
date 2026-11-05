using System;using System.Collections.Generic;
namespace UnityEngine {
 public class Mesh {public int marks;public readonly float[] vertices=new[]{1f,2f,3f};public static List<string> events=new List<string>();public string name;public void MarkDynamic(){marks++;events.Add("hint:"+name);}}
 public class MeshFilter {public Mesh held;public int reads;public Mesh mesh {get{reads++;Mesh.events.Add("get:"+held.name);return held;}}}
}
