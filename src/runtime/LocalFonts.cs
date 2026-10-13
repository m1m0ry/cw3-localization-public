using System;using System.IO;using System.Collections;using System.Collections.Generic;using UnityEngine;

// Local files become native dynamic Fonts. Unity owns glyph generation and its atlas;
// this module owns validation, content-addressed bundle caches and font lifetimes.
internal static class LocalFonts {
 sealed class Face {internal Font Font;internal byte[] Coverage;internal string Hash,Path;internal int Bytes,Pixel;}
 static readonly Dictionary<string,Face> sources=new Dictionary<string,Face>();
 static readonly Dictionary<string,Face> hashes=new Dictionary<string,Face>();
 static readonly Dictionary<string,Face> points=new Dictionary<string,Face>();
 static int hits,builds,bytes;
 internal static string Add(string root,string id){
  if(sources.ContainsKey(id))return "ready";
  try{
   string dir=Path.Combine(root,"fonts");if(!Directory.Exists(dir))return "missing";NoLink(dir);string path;
   if(TextStylePolicy.FontId(id)){string t=Path.Combine(dir,id+".ttf"),o=Path.Combine(dir,id+".otf");if(File.Exists(t)&&File.Exists(o))return "ambiguous_files";path=File.Exists(t)?t:o;}
   else{if(!TextStylePolicy.FontReference(id))throw new FormatException("font filename");path=Path.Combine(dir,id);}
   if(!File.Exists(path))return "missing";NoLink(path);if(new FileInfo(path).Length>50000000)throw new FormatException("font size");var source=new LocalFontFile(File.ReadAllBytes(path));Face face;
   if(hashes.TryGetValue(source.Hash,out face)){sources.Add(id,face);return "ready";}
   if(hashes.Count>=4||bytes+source.Data.Length>200000000)throw new FormatException("font source budget");
   Font font=LoadBundle(root,source,false);
   face=new Face{Font=font,Coverage=source.Coverage,Hash=source.Hash,Path=path,Bytes=source.Data.Length,Pixel=source.Family=="Zpix"?12:0};hashes.Add(source.Hash,face);sources.Add(id,face);bytes+=source.Data.Length;return "ready";
  }catch(Exception e){return "unavailable:"+e.GetType().Name+(e is FormatException?":"+e.Message.Replace(" ","_"):"");}
 }
 // At most one extra native font/atlas per selected source, shared across
 // roles and sizes. Source bytes are transient; this is not a native-memory cap.
 internal static Font Point(string root,string id){Face face;if(!sources.TryGetValue(id,out face))return null;return Point(root,face.Path,face.Hash);}
 internal static Font Point(string root,string path,string expected){
  Face face;if(points.TryGetValue(expected,out face))return face.Font;
  if(points.Count>=TextStylePolicy.Roles.Length)throw new FormatException("point font budget");
  NoLink(Path.GetDirectoryName(path));NoLink(path);if(new FileInfo(path).Length>50000000)throw new FormatException("font size");
  var source=new LocalFontFile(File.ReadAllBytes(path));if(source.Hash!=expected)throw new FormatException("point font hash");
  Font font=LoadBundle(root,source,true);points.Add(expected,new Face{Font=font,Hash=source.Hash});return font;
 }
 static Font LoadBundle(string root,LocalFontFile source,bool point){
  string cache=Path.Combine(root,"font-bundles");if(Directory.Exists(cache))NoLink(cache);else Directory.CreateDirectory(cache);
  string target=Path.Combine(cache,source.Hash+"-"+NativeFontTemplate.Key.Substring(0,16)+(point?"-point":"")+".bundle");byte[] data=NativeFontBundle.Build(source,point);
  if(File.Exists(target))NoLink(target);
  if(NativeFontBundle.Cached(target,data))hits++;else{NativeFontBundle.Save(target,data);builds++;}
  AssetBundle bundle=null;
  try{
   bundle=AssetBundle.CreateFromFile(target);if(bundle==null)throw new FormatException("native bundle rejected");
   Font font=bundle.LoadAsset("fonts/local",typeof(Font)) as Font;
   if(font==null||!font.dynamic||font.name!=NativeFontBundle.Name(source,point)||font.fontNames.Length!=1||font.fontNames[0]!=source.Family||font.lineHeight<=0)throw new FormatException("native font identity");
   foreach(int size in new[]{20,32}){CharacterInfo ci;font.RequestCharactersInTexture(((char)source.Probe).ToString(),size,FontStyle.Normal);if(!font.GetCharacterInfo((char)source.Probe,out ci,size,FontStyle.Normal)||Math.Abs(ci.advance-source.AdvanceAt(size))>1)throw new FormatException("native source glyph");}
   UnityEngine.Object.DontDestroyOnLoad(font);KeepAtlas(font);
   // Keep the native objects; release only the container's registration.
   bundle.Unload(false);bundle=null;return font;
  }finally{if(bundle!=null)bundle.Unload(true);}
 }
 static void NoLink(string path){if((File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new FormatException("font path link");}
 internal static Font FontFor(string id){Face face;return sources.TryGetValue(id,out face)?face.Font:null;}
 internal static byte[] Coverage(string id){return sources[id].Coverage;}
 internal static int PixelUnit(string id){Face face;return sources.TryGetValue(id,out face)?face.Pixel:0;}
 internal static bool Owns(Font font){foreach(Face face in hashes.Values)if(face.Font==font)return true;foreach(Face face in points.Values)if(face.Font==font)return true;return false;}
 internal static void KeepAtlas(Font font){if(font!=null&&font.material!=null){UnityEngine.Object.DontDestroyOnLoad(font.material);if(font.material.mainTexture!=null)UnityEngine.Object.DontDestroyOnLoad(font.material.mainTexture);}}
 internal static void Shutdown(IEnumerable<Font> borrowed){
  var protectedFonts=new HashSet<Font>(borrowed);var materials=new HashSet<Material>();var fonts=new HashSet<Font>();
  foreach(Font font in protectedFonts)if(font!=null&&font.material!=null)materials.Add(font.material);
  var owned=new List<Face>(hashes.Values);owned.AddRange(points.Values);
  foreach(Face face in owned)if(face.Font!=null&&!protectedFonts.Contains(face.Font)&&fonts.Add(face.Font)){
   if(face.Font.material!=null&&materials.Add(face.Font.material))UnityEngine.Object.Destroy(face.Font.material);UnityEngine.Object.Destroy(face.Font);
  }sources.Clear();hashes.Clear();points.Clear();bytes=0;
 }
 internal static Hashtable Status(){return new Hashtable{{"point_fonts",points.Count},{"sources",hashes.Count},{"aliases",sources.Count},{"cache_hits",hits},{"bundle_builds",builds},{"backend","unity_native_dynamic"}};}
}
