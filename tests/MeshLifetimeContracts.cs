using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;

// Run the shipped runtime/styles against a managed Unity-object boundary.
// Destruction and lazy Renderer.material instances are simulated, not rendered.
public class SetColor:UnityEngine.Component {public UnityEngine.Material material;}
class NamedOwner {public string GUID="fixture-guid";}
class MeshLifetimeContracts {
 const BindingFlags Flags=BindingFlags.Static|BindingFlags.NonPublic;
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static object Field(Type type,string name){return type.GetField(name,Flags).GetValue(null);}
 static UnityEngine.TextMesh Mesh(string name,UnityEngine.Font font){var go=new UnityEngine.GameObject(name);var mesh=go.AddComponent<UnityEngine.TextMesh>();mesh.font=font;mesh.text="initial";return mesh;}
 static UnityEngine.Renderer Render(UnityEngine.TextMesh mesh,UnityEngine.Material material,bool instance){var renderer=mesh.gameObject.AddComponent<UnityEngine.Renderer>();renderer.sharedMaterial=material;renderer.InstanceOnRead=instance;return renderer;}
 static void Main(){
  typeof(CW3Runtime).GetField("loaded",Flags).SetValue(null,true);typeof(CW3Runtime).GetField("candidates",Flags).SetValue(null,new Candidates(false,"/unused-fixture/candidates.json"));
  var font=new UnityEngine.Font();((Dictionary<string,UnityEngine.Font>)Field(typeof(TextStyles),"fonts")).Add("sans",font);((Dictionary<int,BitArray>)Field(typeof(TextStyles),"coverage")).Add(font.GetInstanceID(),new BitArray(65536,true));
  var definitions=(Dictionary<string,Hashtable>)Field(typeof(CW3Runtime),"definitions");var translations=(Dictionary<string,string>)Field(typeof(CW3Runtime),"translations");var sources=(Dictionary<string,List<Hashtable>>)Field(typeof(CW3Runtime),"sources");
  foreach(string raw in new[]{"Alpha","Beta"}){var d=new Hashtable{{"id",raw},{"source",raw},{"kind","xml_text"},{"owner","NamedOwner"},{"guid","fixture-guid"}};definitions.Add(raw,d);translations.Add(raw,"translated "+raw);sources.Add(raw,new List<Hashtable>{d});}
  var owner=new NamedOwner();var noRenderer=Mesh("NoRenderer",font);CW3Runtime.SetNamedMesh(noRenderer,"Alpha",owner);
  Need(CW3Runtime.OriginalMesh(noRenderer)=="Alpha"&&noRenderer.text=="translated Alpha","Raw named source survives display without a renderer");
  Need((string)CW3Runtime.MeshReport(noRenderer)["status"]=="missing_renderer_material","Missing renderer is not material ownership");
  var borrowed=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};var renderer=Render(noRenderer,borrowed,false);var fade=noRenderer.gameObject.AddComponent<SetColor>();fade.material=borrowed;
  Need((string)CW3Runtime.MeshReport(noRenderer)["status"]=="ready","Remembered record alone does not claim a new renderer");
  for(int i=0;i<3;i++)CW3Runtime.SetNamedMesh(noRenderer,"Beta",owner);
  Need(CW3Runtime.OriginalMesh(noRenderer)=="Beta"&&noRenderer.text=="translated Beta","Repeated writes replace raw source, never capture translated text");
  Need(noRenderer.gameObject.GetComponentsInChildren<CW3MeshLifetime>(true).Length==1,"Exactly one lifetime owner");
  Need(renderer.sharedMaterial==borrowed&&!(bool)CW3Runtime.MeshReport(noRenderer)["material_owned"]&&fade.material==borrowed,"Game/SetColor instance remains borrowed");
  CW3Runtime.ReleaseMesh(noRenderer.GetInstanceID());CW3Runtime.ReleaseMesh(noRenderer.GetInstanceID());Need(borrowed.DestroyCalls==0,"Borrowed material destroyed");
  Need(CW3Runtime.OriginalMesh(noRenderer)==noRenderer.text,"Released source falls back to native getter");
  var mesh=Mesh("Owned",font);var shared=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};renderer=Render(mesh,shared,true);CW3Runtime.SetNamedMesh(mesh,"Alpha",owner);var created=renderer.sharedMaterial;
  Need(created!=shared&&(bool)CW3Runtime.MeshReport(mesh)["material_owned"],"Lazy material instance is tracked as owned");
  CW3Runtime.SetNamedMesh(mesh,"Alpha",owner);Need(renderer.sharedMaterial==created,"Repeated text allocates no second material");
  var replacement=new UnityEngine.Material{mainTexture=new UnityEngine.Texture()};renderer.sharedMaterial=replacement;
  Need((string)CW3Runtime.MeshReport(mesh)["status"]=="renderer_material_changed","External material replacement detected");
  CW3Runtime.SetNamedMesh(mesh,"Beta",owner);Need(renderer.sharedMaterial==replacement&&!(bool)CW3Runtime.MeshReport(mesh)["material_owned"],"Replacement becomes borrowed while older owned instance is retained");
  UnityEngine.Object.Destroy(mesh.gameObject.GetComponent(typeof(CW3MeshLifetime)));CW3Runtime.ReleaseMesh(mesh.GetInstanceID());
  Need(created.DestroyCalls==1&&shared.DestroyCalls==0&&replacement.DestroyCalls==0&&!font.material.mainTexture.Destroyed,"Release destroys each owned material once and preserves borrowed materials/atlas");
  var absent=Mesh("InitiallyEmpty",font);renderer=Render(absent,null,false);CW3Runtime.SetMesh(absent,null);var generated=renderer.sharedMaterial;
  Need(CW3Runtime.OriginalMesh(absent)==null&&generated!=null&&(bool)CW3Runtime.MeshReport(absent)["material_owned"],"Null raw source and material creation remain distinguishable");
  UnityEngine.Object.Destroy(absent);CW3Runtime.Scene();CW3Runtime.ReleaseMesh(absent.GetInstanceID());Need(generated.DestroyCalls==1,"Scene cleanup and repeated release destroy owned material once");
  Console.WriteLine("PASS shipped runtime/styles with simulated Unity lifetimes: raw/display separation, missing renderer, repeated writes, borrowed/lazy/replaced materials and idempotent release");
 }
}
