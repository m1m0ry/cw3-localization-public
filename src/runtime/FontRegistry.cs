using System;using System.Collections;using System.Collections.Generic;using System.Text.RegularExpressions;
// The two shipped faces and their resource/source hashes form one matching snapshot.
internal sealed class FontRegistry {
 internal sealed class Face {internal string File,Hash,Family,Coverage;internal int PixelSize,ProbeChar,ProbeAdvance;}
 internal readonly Dictionary<string,Face> Faces=new Dictionary<string,Face>();
 internal string SharedHash,MainHash,RuntimeHash;
 static string S(Hashtable h,string key){var value=h[key] as string;if(value==null)throw new FormatException("font string");return value;}
 static int N(Hashtable h,string key){if(!(h[key] is int))throw new FormatException("font integer");return (int)h[key];}
 static string Hash(Hashtable h,string key){string value=S(h,key);if(!Regex.IsMatch(value,"^[a-f0-9]{64}$"))throw new FormatException("font hash");return value;}
 internal static FontRegistry Parse(string text){
  if(text==null||text.Length>256000)throw new FormatException("font registry size");var root=Json.Read(text) as Hashtable;
  if(root==null||root.Count!=4||N(root,"format")!=1)throw new FormatException("font registry format");var r=root["resources"] as Hashtable;var faces=root["fonts"] as Hashtable;
  if(r==null||r.Count!=2||faces==null||faces.Count!=2||!faces.ContainsKey("sans")||!faces.ContainsKey("serif"))throw new FormatException("font registry structure");
  var result=new FontRegistry{RuntimeHash=Hash(root,"runtime_sha256"),SharedHash=Hash(r,"CW3_Data/sharedassets0.assets"),MainHash=Hash(r,"CW3_Data/mainData")};
  foreach(DictionaryEntry entry in faces){string id=(string)entry.Key;var f=entry.Value as Hashtable;if(f==null||f.Count!=7)throw new FormatException("font entry");
   string file=S(f,"file");if(file!=(id=="sans"?"font.ttf":"serif.ttf"))throw new FormatException("font path");
   var face=new Face{File=file,Hash=Hash(f,"sha256"),Family=S(f,"family"),Coverage=S(f,"coverage"),PixelSize=N(f,"pixel_size"),ProbeChar=N(f,"probe_char"),ProbeAdvance=N(f,"probe_advance")};
   if(face.Family.Length==0||face.Family.Length>256||Convert.FromBase64String(face.Coverage).Length!=8192||face.PixelSize<0||face.PixelSize>64||face.ProbeChar<33||face.ProbeChar>=65536||face.ProbeAdvance<0||face.ProbeAdvance>4096)throw new FormatException("font metadata");result.Faces.Add(id,face);
  }return result;
 }
}
