using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using UnityEngine;

// Own fonts and NGUI sidecars here. Translation binding and material ownership stay in CW3Runtime.
internal static class TextStyles {
 const BindingFlags Flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
 static TextStylePolicy policy=new TextStylePolicy();
 static readonly Dictionary<int,BitArray> coverage=new Dictionary<int,BitArray>();
 static readonly Dictionary<string,Font> fonts=new Dictionary<string,Font>();
 static readonly Dictionary<string,Font> pointFonts=new Dictionary<string,Font>();
 static readonly Dictionary<string,string[]> fontSources=new Dictionary<string,string[]>();
 static readonly Dictionary<string,string> pointStatus=new Dictionary<string,string>();
 static readonly HashSet<int> blockedPoints=new HashSet<int>();
 static readonly Dictionary<string,bool> glyphs=new Dictionary<string,bool>();
 static readonly Dictionary<string,Clone> clones=new Dictionary<string,Clone>();
 static readonly Dictionary<int,LabelState> labels=new Dictionary<int,LabelState>();
 static readonly Dictionary<int,MeshState> meshes=new Dictionary<int,MeshState>();
 static readonly Dictionary<int,int> rebuilds=new Dictionary<int,int>();
 static readonly Dictionary<string,int> fallbacks=new Dictionary<string,int>();
 static readonly Dictionary<string,Hashtable> guiReports=new Dictionary<string,Hashtable>();
 static string configStatus="missing_defaults",sansStatus="not_loaded",serifStatus="not_loaded";
 static bool loaded,diagnostics;
 static bool assetsValid;
 static readonly Dictionary<string,int> pixelSizes=new Dictionary<string,int>();
 static readonly Dictionary<string,string> fontStatus=new Dictionary<string,string>();
 static string registryStatus="compiled_defaults",registryHash="";
 sealed class Clone {internal Component Font;internal int Users;}
 sealed class LabelState {
  internal Component Label,Native;internal Clone Clone;internal Vector3 Base,Applied;
  internal string Role,Family,Reason;internal int Percent,PixelUnit;
 }
 sealed class MeshState {internal TextMesh Mesh;internal Font Native;internal int BaseSize,Applied,PixelUnit;internal string Family,Reason,Role;internal int Percent;}
 static object Get(object value,string name){if(value==null)return null;var p=value.GetType().GetProperty(name,Flags);return p==null?null:p.GetValue(value,null);}
 static void Set(object value,string name,object data){var p=value.GetType().GetProperty(name,Flags);if(p==null||!p.CanWrite)throw new InvalidOperationException("Missing font property "+name);p.SetValue(value,data,null);}
 internal static void Load(string folder){
  if(loaded)return;loaded=true;
  try{string path=Path.Combine(folder,"text-style.json");if(File.Exists(path)){if(new FileInfo(path).Length>32768)throw new FormatException("style size");policy=TextStylePolicy.Parse(File.ReadAllText(path));configStatus="loaded";}}
  catch(Exception e){configStatus="invalid_defaults:"+e.GetType().Name;policy=new TextStylePolicy();}
  string registryPath=Path.Combine(folder,"fonts.json");
  try{
   if(!File.Exists(registryPath))throw new FileNotFoundException("font registry");
   var registry=FontRegistry.Parse(File.ReadAllText(registryPath));registryHash=FileHash(registryPath);
   if(FileHash(typeof(TextStyles).Assembly.Location)!=registry.RuntimeHash)throw new FormatException("font runtime mismatch");
   if(registry.Faces["sans"].Hash!=CW3StyleFonts.SansHash||registry.Faces["serif"].Hash!=CW3StyleFonts.SerifHash)throw new FormatException("controlled defaults");
   assetsValid=FileHash(Path.Combine(Application.dataPath,"sharedassets0.assets"))==registry.SharedHash&&FileHash(Path.Combine(Application.dataPath,"mainData"))==registry.MainHash;
   foreach(var entry in registry.Faces){var face=entry.Value;pixelSizes[entry.Key]=face.PixelSize;fontStatus[entry.Key]=LoadFace(folder,entry.Key,face.File,face.Hash,face.Coverage,face.Family,face.ProbeChar,face.ProbeAdvance);}
   registryStatus=assetsValid?"loaded":"resource_hash_mismatch";
  }catch(Exception e){
   registryStatus="invalid_defaults:"+e.GetType().Name;registryHash="";
   try{assetsValid=FileHash(Path.Combine(Application.dataPath,"sharedassets0.assets"))==CW3StyleFonts.AssetsHash;}catch{assetsValid=false;}
   fontStatus["sans"]=LoadFace(folder,"sans","font.ttf",CW3StyleFonts.SansHash,CW3StyleFonts.SansCoverage,"CW3 Sans SC External",0,0);
   fontStatus["serif"]=LoadFace(folder,"serif","serif.ttf",CW3StyleFonts.SerifHash,CW3StyleFonts.SerifCoverage,"CW3 Serif SC External",0,0);
  }
  if(assetsValid)foreach(string role in TextStylePolicy.Roles){var choice=policy.For(role);if(fontStatus.ContainsKey(choice.Family))continue;string status=LocalFonts.Add(folder,choice.Family);fontStatus[choice.Family]=status;if(status=="ready"){Font font=LocalFonts.FontFor(choice.Family);fonts.Add(choice.Family,font);coverage[font.GetInstanceID()]=new BitArray(LocalFonts.Coverage(choice.Family));pixelSizes[choice.Family]=LocalFonts.PixelUnit(choice.Family);}}

  foreach(Font smooth in fonts.Values)SmoothFilter(smooth);
  // Preload only the configured pixel variants, once per family. No file IO in
  // Label/GUI/TextMesh drawing; all smooth consumers retain their original atlas.
  foreach(string role in TextStylePolicy.Roles){var choice=policy.For(role);if(choice.PixelSize==0&&PixelUnit(choice.Family)==0||pointStatus.ContainsKey(choice.Family))continue;
   Font smooth=FontFor(choice.Family);if(smooth==null)continue;
   try{string[] source;Font point=fontSources.TryGetValue(choice.Family,out source)?LocalFonts.Point(folder,source[0],source[1]):LocalFonts.Point(folder,choice.Family);
    if(point==null)throw new InvalidOperationException("point font unavailable");pointFonts.Add(choice.Family,point);coverage[point.GetInstanceID()]=coverage[smooth.GetInstanceID()];
    if(PixelFilter(point))pointStatus[choice.Family]="ready";
   }catch(Exception e){pointStatus[choice.Family]="unavailable:"+e.GetType().Name;}
  }
  foreach(Font point in pointFonts.Values)PixelFilter(point);
  sansStatus=fontStatus["sans"];serifStatus=fontStatus["serif"];
  try{var rows=new List<string>();foreach(var entry in fontStatus)rows.Add("\""+entry.Key+"\":\""+entry.Value+"\"");string data="{\"format\":1,\"registry_sha256\":\""+registryHash+"\",\"fonts\":{"+String.Join(",",rows.ToArray())+"}}";string temp=Path.Combine(folder,"font-status.tmp");File.WriteAllText(temp,data);string target=Path.Combine(folder,"font-status.json");if(File.Exists(target))File.Delete(target);File.Move(temp,target);}catch(Exception e){Debug.LogWarning("CW3Localization font status unavailable: "+e.GetType().Name);}
 }
 static string FileHash(string path){using(var stream=File.OpenRead(path))using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();}
 static string LoadFace(string folder,string family,string file,string expected,string cmap,string prefix,int probe,int advance){
  try{string path=Path.Combine(folder,file);if(!File.Exists(path))return "missing";
   if(new FileInfo(path).Length>50000000)throw new FormatException("font size");
   if(FileHash(path)!=expected)return "hash_mismatch";
   string actualFamily=FontFile.Family(path,prefix);if(probe>0&&actualFamily!=prefix)return "family_mismatch";if(!assetsValid)return "resource_hash_mismatch";
   Font font=Resources.Load("cw3-localization/fonts/"+family,typeof(Font)) as Font;
   if(font==null||!font.dynamic||font.name!="CW3Style_"+family+"_"+expected.Substring(0,12))return "resource_unavailable";
   byte[] bits=Convert.FromBase64String(cmap);if(bits.Length!=8192)throw new FormatException("font coverage");var own=new BitArray(bits);
   if(probe>0){CharacterInfo ci;font.RequestCharactersInTexture(((char)probe).ToString(),20,FontStyle.Normal);if(!own[probe]||!font.GetCharacterInfo((char)probe,out ci,20,FontStyle.Normal)||Math.Abs(ci.advance-advance)>1)return "glyph_probe_failed";}
   if(!fonts.ContainsKey(family)){fonts.Add(family,font);coverage.Add(font.GetInstanceID(),own);fontSources[family]=new[]{path,expected};UnityEngine.Object.DontDestroyOnLoad(font);}return "ready";
  }catch(Exception e){return "unavailable:"+e.GetType().Name;}
 }
 internal static int PixelUnit(string family){int value;return pixelSizes.TryGetValue(family,out value)?value:0;}
 // A UIFont or Material copy still shares the texture. Point fonts come from
 // independently serialized Font/Material/Texture objects; verify native identity
 // again after every atlas rebuild before touching its filtering. Contracts cover
 // this guard, not Unity rendering. Remove the variant only if Unity offers proven
 // per-consumer sampling. Extra native source/atlas memory exists only for selected faces.
 static void SmoothFilter(Font font){if(font.material!=null&&font.material.mainTexture!=null)font.material.mainTexture.filterMode=FilterMode.Bilinear;}
 static bool PixelFilter(Font font){
  if(LocalFonts.Owns(font))LocalFonts.KeepAtlas(font);
  bool point=false;foreach(Font candidate in pointFonts.Values)if(candidate==font)point=true;if(!point)return false;
  bool isolated=font.material!=null&&font.material.mainTexture!=null;
  if(isolated)foreach(Font smooth in fonts.Values)if(smooth==font||smooth.material==font.material||smooth.material!=null&&smooth.material.mainTexture==font.material.mainTexture)isolated=false;
  if(!isolated){if(font.material!=null&&font.material.mainTexture!=null)font.material.mainTexture.filterMode=FilterMode.Bilinear;blockedPoints.Add(font.GetInstanceID());foreach(var row in pointFonts)if(row.Value==font)pointStatus[row.Key]="atlas_shared_or_missing";return false;}
  if(blockedPoints.Contains(font.GetInstanceID()))return false;
  font.material.mainTexture.filterMode=FilterMode.Point;return true;
 }

 internal static Font FontFor(string family){Font font;return fonts.TryGetValue(family,out font)?font:null;}
 static bool Covers(Font font,string text){
  if(font==null)return false;if(String.IsNullOrEmpty(text))return true;
  string key=font.GetInstanceID()+":"+text;bool found;if(text.Length<=4096&&glyphs.TryGetValue(key,out found))return found;
  BitArray own;found=coverage.TryGetValue(font.GetInstanceID(),out own);if(found)foreach(char c in text)if(!Char.IsWhiteSpace(c)&&!own[c]){found=false;break;}
  if(text.Length<=4096){if(glyphs.Count>=128)glyphs.Clear();glyphs[key]=found;}return found;
 }
 static Font Select(string role,string text,Font native,out string family,out string reason,out int unit){
  var style=policy.For(role);Font selected=FontFor(style.Family);unit=0;
  family=TextStylePolicy.Family(style.Family,selected!=null,Covers(selected,text),out reason);
  if(family!=style.Family)selected=FontFor(family);
  if(selected==null||!Covers(selected,text)){family="sans";selected=native;reason="sans_unavailable_native";}
  if(reason.Length==0){unit=style.PixelSize>0?style.PixelSize:PixelUnit(family);
   if(unit>0){Font point;if(pointFonts.TryGetValue(family,out point)&&!blockedPoints.Contains(point.GetInstanceID()))selected=point;
    else{unit=0;family="sans";reason="pixel_font_unavailable";selected=FontFor(family);if(!Covers(selected,text))selected=native;}
   }
  }return selected;
 }
 static void Count(string reason){if(reason.Length==0)return;int n;fallbacks.TryGetValue(reason,out n);fallbacks[reason]=n+1;}
 static Clone CloneFont(Component native,string family,Font dynamic,int size){
  string key=native.GetInstanceID()+":"+family+":"+size+":"+dynamic.GetInstanceID();Clone clone;if(clones.TryGetValue(key,out clone)&&clone.Font!=null)return clone;
  if(clones.Count>=256)throw new InvalidOperationException("UIFont sidecar limit");
  var go=new GameObject("CW3 style font");go.hideFlags=HideFlags.HideAndDontSave;UnityEngine.Object.DontDestroyOnLoad(go);
  try{Component font=go.AddComponent(native.GetType());
   // Copy serialized font metrics only. Mutable caches and replacement chains are never shared.
   foreach(string field in new[]{"mUVRect","mFont","mSpacingX","mSpacingY","mPixelSize","mDynamicFontStyle"}){var f=native.GetType().GetField(field,Flags);if(f!=null)f.SetValue(font,f.GetValue(native));}
   Set(font,"dynamicFont",dynamic);Set(font,"dynamicFontSize",size);
   clone=new Clone{Font=font};clones[key]=clone;return clone;
  }catch{UnityEngine.Object.Destroy(go);throw;}
 }
 static void Detach(LabelState state){if(state.Clone==null)return;state.Clone.Users--;state.Clone=null;}
 internal static void Label(Component label,string text,string path){Label(label,text,path,false);}
 internal static void BodyFallback(Component label,string text,string path){Label(label,text,path,true);}
 static void Label(Component label,string text,string path,bool smoothBodyFallback){
  if(label==null)return;int id=label.GetInstanceID();Component current=Get(label,"font") as Component;if(current==null)return;
  LabelState state;if(!labels.TryGetValue(id,out state)){state=new LabelState{Label=label,Native=current,Base=label.transform.localScale,Applied=label.transform.localScale};labels.Add(id,state);var life=label.gameObject.AddComponent<CW3StyleLifetime>();life.Id=id;}
  if(state.Clone!=null&&current!=state.Clone.Font){Detach(state);state.Native=current;state.Base=label.transform.localScale;state.Applied=state.Base;}
  else if(label.transform.localScale!=state.Applied)state.Base=label.transform.localScale;
  string role=TextStylePolicy.Role(label.name,path),family,reason;var style=policy.For(role);
  int size=20;object nativeSize=Get(state.Native,"dynamicFontSize");if(nativeSize is int)size=(int)nativeSize;size=Math.Max(4,Math.Min(128,size));
  int unit=0;Font selected;
  if(smoothBodyFallback){family="sans";reason="pixel_body_bounds";selected=FontFor(family);if(!Covers(selected,text))selected=Get(state.Native,"dynamicFont") as Font;}
  else selected=Select(role,text,Get(state.Native,"dynamicFont") as Font,out family,out reason,out unit);
  bool pixel=unit>0;if(pixel)size=TextStylePolicy.PixelSize((int)Math.Round(Math.Abs(state.Base.x)),style.Percent,unit);
  try{
   if(selected!=null){Clone clone=CloneFont(state.Native,family,selected,size);if(clone!=state.Clone){Detach(state);clone.Users++;state.Clone=clone;Set(label,"font",clone.Font);}}
   else{Detach(state);Set(label,"font",state.Native);}
   float factor=style.Percent/100f;Vector3 scale=state.Base;if(pixel){scale.x=size*Math.Sign(scale.x);scale.y=size*Math.Sign(scale.y);}else{scale.x*=factor;scale.y*=factor;}label.transform.localScale=scale;state.Applied=scale;
   if(state.Reason!=reason)Count(reason);state.Role=role;state.Family=family;state.Reason=reason;state.Percent=style.Percent;state.PixelUnit=unit;
  }catch(Exception e){while(e is TargetInvocationException&&e.InnerException!=null)e=e.InnerException;
   if(state.Reason!="ngui_native_fallback")Debug.LogWarning("CW3Localization NGUI font fallback: "+e);
   Detach(state);Set(label,"font",state.Native);label.transform.localScale=state.Base;state.Applied=state.Base;state.Reason="ngui_native_fallback";state.PixelUnit=0;Count(state.Reason);}
 }
 internal static int LabelPixelUnit(Component label){LabelState state;return label!=null&&labels.TryGetValue(label.GetInstanceID(),out state)?state.PixelUnit:0;}
 internal static void Fitted(Component label){
  LabelState state;if(label==null||!labels.TryGetValue(label.GetInstanceID(),out state))return;
  // Body/title fitting steps in pixel units; rasterize at the final size, never scale a larger glyph.
  if((state.Role==TextStylePolicy.Title||state.Role==TextStylePolicy.Body)&&state.PixelUnit>0&&state.Clone!=null){
   int size=(int)Math.Round(Math.Abs(label.transform.localScale.x));
   if(size>=state.PixelUnit&&size%state.PixelUnit==0&&(int)Get(state.Clone.Font,"dynamicFontSize")!=size){
    Clone clone=CloneFont(state.Native,state.Family,Get(state.Clone.Font,"dynamicFont") as Font,size);
    Detach(state);clone.Users++;state.Clone=clone;Set(label,"font",clone.Font);
   }
  }
  state.Applied=label.transform.localScale;
 }
 internal static void FittedMesh(TextMesh mesh){MeshState state;if(mesh!=null&&meshes.TryGetValue(mesh.GetInstanceID(),out state))state.Applied=mesh.fontSize;}
 internal static Hashtable ApplySizes(TextStylePolicy saved,Action<Component> prepareLabel,Action<TextMesh> refreshMaterial){
  var next=policy.WithSizes(saved);var changed=new HashSet<string>();foreach(string role in TextStylePolicy.Roles)if(next.For(role).Percent!=policy.For(role).Percent)changed.Add(role);policy=next;
  int labelCount=0,meshCount=0,failures=0;
  // Snapshot the owned controls: glyph requests may notify atlas observers during refresh.
  foreach(var state in new List<LabelState>(labels.Values))if(state.Label!=null&&changed.Contains(state.Role))try{
   prepareLabel(state.Label);var mark=state.Label.GetType().GetMethod("MarkAsChanged",Flags);if(mark==null)throw new MissingMethodException("UILabel.MarkAsChanged");mark.Invoke(state.Label,null);labelCount++;
  }catch(Exception e){failures++;Debug.LogWarning("CW3Localization size refresh fallback: "+e.GetType().Name);}
  foreach(var state in new List<MeshState>(meshes.Values))if(state.Mesh!=null&&changed.Contains(state.Role))try{
   // Keep its already-drawn caption and remembered role; never rewrite a named map/model value.
   string display=state.Mesh.text;Mesh(state.Mesh,display,state.Role);state.Mesh.text=display;refreshMaterial(state.Mesh);meshCount++;
  }catch(Exception e){failures++;Debug.LogWarning("CW3Localization mesh size fallback: "+e.GetType().Name);}
  Cleanup();return new Hashtable{{"changed_roles",changed.Count},{"labels",labelCount},{"meshes",meshCount},{"failures",failures}};
 }
 internal static int Percent(Component label){return policy.For(TextStylePolicy.Role(label.name,PathOf(label))).Percent;}
 static string PathOf(Component label){string path="";for(Transform t=label.transform;t!=null;t=t.parent)path=t.name+(path.Length==0?"":"/"+path);return path;}
 internal static Font Mesh(TextMesh mesh,string text,string role){
  int id=mesh.GetInstanceID();MeshState state;if(!meshes.TryGetValue(id,out state)){state=new MeshState{Mesh=mesh,Native=mesh.font,BaseSize=mesh.fontSize,Applied=mesh.fontSize};meshes.Add(id,state);}
  state.Role=role;if(mesh.fontSize!=state.Applied)state.BaseSize=mesh.fontSize;
  var style=policy.For(role);string family,reason;int unit;Font selected=Select(role,text,state.Native,out family,out reason,out unit);if(selected!=null)mesh.font=selected;
  int size=unit>0?TextStylePolicy.PixelSize(state.BaseSize,style.Percent,unit):TextStylePolicy.Size(state.BaseSize,style.Percent);
   mesh.fontSize=size;state.Applied=mesh.fontSize;state.PixelUnit=unit;state.Role=role;state.Family=family;state.Percent=style.Percent;if(state.Reason!=reason)Count(reason);state.Reason=reason;return mesh.font;
 }
 internal static int MeshPixelUnit(TextMesh mesh){MeshState state;return mesh!=null&&meshes.TryGetValue(mesh.GetInstanceID(),out state)?state.PixelUnit:0;}
 internal static void ReleaseMesh(int id){meshes.Remove(id);}
 internal static void ReleaseLabel(int id){LabelState state;if(labels.TryGetValue(id,out state)){Detach(state);labels.Remove(id);}Cleanup();}
 internal static void Cleanup(){var dead=new List<string>();foreach(var pair in clones)if(pair.Value.Users==0){if(pair.Value.Font!=null)UnityEngine.Object.Destroy(pair.Value.Font.gameObject);dead.Add(pair.Key);}foreach(string key in dead)clones.Remove(key);}
 internal static GUIStyle Gui(GUIStyle native,string text,string role){
  if(native==null)return native;if(role==TextStylePolicy.CodeInput&&native.font!=null)return native;var style=policy.For(role);int size=native.fontSize>0?native.fontSize:13;
  string family,reason;int unit;Font selected=Select(role,text,native.font,out family,out reason,out unit);
  GUIStyle copy=native;
  // The shared native asset is 20px; resolve implicit IMGUI 13px explicitly.
  // Rect, control ID, focus, cursor and scrolling still belong to the original call.
  if(selected!=null){int resolved=role==TextStylePolicy.CodeInput?size:unit>0?TextStylePolicy.PixelSize(size,style.Percent,unit):TextStylePolicy.Size(size,style.Percent);
   // Drawing wrappers never mutate the caller; allocate only when an override differs.
   if(native.font!=selected||native.fontSize!=resolved)copy=new GUIStyle(native){font=selected,fontSize=resolved};
  }
  if(diagnostics){string key=role+":"+native.name;if(guiReports.Count<32||guiReports.ContainsKey(key)){Vector2 measured=copy.CalcSize(new GUIContent(text));guiReports[key]=new Hashtable{{"role",role},{"family",family},{"size",copy.fontSize>0?copy.fontSize:13},{"percent",style.Percent},{"fallback",reason},{"measured",measured.ToString()}};}}
  return copy;
 }
 internal static void Rebuilt(Font font,Action<Component> prepareLabel,Action<TextMesh,bool> refreshMaterial){
  if(font==null)return;if(LocalFonts.Owns(font))LocalFonts.KeepAtlas(font);
  foreach(Font smooth in fonts.Values)if(smooth==font)SmoothFilter(smooth);
  // Either the smooth or point font may acquire a new atlas; check both directions.
  foreach(Font point in pointFonts.Values)PixelFilter(point);
  int id=font.GetInstanceID(),n;rebuilds.TryGetValue(id,out n);rebuilds[id]=n+1;
  foreach(var state in new List<LabelState>(labels.Values))if(state.Label!=null&&state.Clone!=null){Font active=Get(state.Clone.Font,"dynamicFont") as Font;
   bool blocked=active!=null&&blockedPoints.Contains(active.GetInstanceID());
   if(active==font||blocked){if(blocked)prepareLabel(state.Label);var mark=state.Label.GetType().GetMethod("MarkAsChanged",Flags);if(mark!=null)mark.Invoke(state.Label,null);}
  }
  foreach(var state in new List<MeshState>(meshes.Values))if(state.Mesh!=null){bool blocked=state.Mesh.font!=null&&blockedPoints.Contains(state.Mesh.font.GetInstanceID());
   if(state.Mesh.font==font||blocked){if(blocked)Mesh(state.Mesh,state.Mesh.text,state.Role);refreshMaterial(state.Mesh,blocked);}
  }
 }
 internal static void Shutdown(){var borrowed=new List<Font>();foreach(string family in fontSources.Keys)borrowed.Add(fonts[family]);LocalFonts.Shutdown(borrowed);}
 internal static bool Owns(Font font){foreach(Font f in fonts.Values)if(f==font)return true;return LocalFonts.Owns(font);}
 internal static void Diagnostics(bool enabled){diagnostics=enabled;if(!enabled)guiReports.Clear();}
 internal static Hashtable Report(Component component){
  var r=new Hashtable();if(component==null)return r;LabelState state;MeshState mesh;
  if(labels.TryGetValue(component.GetInstanceID(),out state)){r["role"]=state.Role;r["family"]=state.Family;r["percent"]=state.Percent;r["fallback"]=state.Reason;r["ui_font_id"]=state.Clone==null?state.Native.GetInstanceID():state.Clone.Font.GetInstanceID();r["font"]=Get(Get(component,"font"),"dynamicFont");r["size"]=Get(Get(component,"font"),"dynamicFontSize");r["scale"]=component.transform.localScale.ToString();r["available_width"]=Get(component,"lineWidth");r["max_lines"]=Get(component,"maxLineCount");
   string text=Get(component,"processedText") as string;Component font=Get(component,"font") as Component;object symbols=Get(component,"symbolStyle");var measure=font==null||symbols==null?null:font.GetType().GetMethod("CalculatePrintedSize",Flags,null,new[]{typeof(string),typeof(bool),symbols.GetType()},null);if(measure!=null&&text!=null)r["measured"]=measure.Invoke(font,new[]{(object)text,Get(component,"supportEncoding"),symbols}).ToString();r["relative_size"]=Get(component,"relativeSize");}
  else if(meshes.TryGetValue(component.GetInstanceID(),out mesh)){r["role"]=mesh.Role;r["family"]=mesh.Family;r["percent"]=mesh.Percent;r["fallback"]=mesh.Reason;r["size"]=mesh.Applied;r["font"]=mesh.Mesh.font;}
  return r;
 }
 internal static Hashtable Status(){var statuses=new Hashtable();foreach(var row in fontStatus)statuses[row.Key]=row.Value;var points=new Hashtable();foreach(var row in pointStatus)points[row.Key]=row.Value;var counts=new Hashtable();foreach(var row in rebuilds)counts[row.Key.ToString()]=row.Value;var fall=new Hashtable();foreach(var row in fallbacks)fall[row.Key]=row.Value;var gui=new ArrayList();foreach(var row in guiReports.Values)gui.Add(row);return new Hashtable{{"point_fonts",points},{"local_fonts",LocalFonts.Status()},{"registry",registryStatus},{"font_status",statuses},{"config",configStatus},{"sans",sansStatus},{"serif",serifStatus},{"fonts",fonts.Count},{"ui_fonts",clones.Count},{"labels",labels.Count},{"meshes",meshes.Count},{"glyph_cache",glyphs.Count},{"atlas_rebuilds",counts},{"fallbacks",fall},{"gui",gui},{"diagnostics",diagnostics}};}
 internal static TextStylePolicy ActivePolicy(){return policy.Copy();}
 internal static IEnumerable<string> FontChoices(){return new List<string>(fontStatus.Keys);}
 internal static Hashtable RoleState(string role){
  var style=policy.For(role);string status;fontStatus.TryGetValue(style.Family,out status);
  int drawn=0,missing=0,other=0;foreach(var s in labels.Values)if(s.Label!=null&&s.Label.gameObject.activeInHierarchy&&s.Role==role){drawn++;if((s.Reason??"").IndexOf("missing_glyph",StringComparison.Ordinal)>=0)missing++;else if(!String.IsNullOrEmpty(s.Reason))other++;}
  foreach(var s in meshes.Values)if(s.Mesh!=null&&s.Mesh.gameObject.activeInHierarchy&&s.Role==role){drawn++;if((s.Reason??"").IndexOf("missing_glyph",StringComparison.Ordinal)>=0)missing++;else if(!String.IsNullOrEmpty(s.Reason))other++;}
  return new Hashtable{{"font",style.Family},{"percent",style.Percent},{"load_status",status??"not_loaded"},{"observed_controls",drawn},{"missing_glyph_controls",missing},{"other_fallback_controls",other}};
 }
}
public sealed class CW3StyleLifetime:MonoBehaviour {internal int Id;void OnDestroy(){TextStyles.ReleaseLabel(Id);}}
