using System;using System.Collections;using System.Collections.Generic;using System.Text;using System.Globalization;

// Display roles are about the final control. Translation target kinds never enter this policy.
internal sealed class TextStylePolicy {
 internal const string Body="body",Title="title",Ui="ui",Status="status",CodeInput="code_input";
 internal static readonly string[] Roles={Body,Title,Ui,Status};
 internal sealed class Style {internal readonly string Family;internal readonly int Percent,PixelSize;internal Style(string family,int percent,int pixel=0){Family=family;Percent=percent;PixelSize=pixel;}}
 static readonly Style DefaultStyle=new Style("sans",100);
 readonly Dictionary<string,Style> roles=new Dictionary<string,Style>();
 internal TextStylePolicy(){foreach(string role in new[]{Body,Title,Ui,Status})roles.Add(role,DefaultStyle);}
 internal Style For(string role){Style value;return roles.TryGetValue(role,out value)?value:DefaultStyle;}
 internal void Change(string role,string font,int percent,int pixel){if(!roles.ContainsKey(role)||!FontReference(font)||percent<75||percent>150||pixel<0||pixel>64)throw new FormatException("style value");roles[role]=new Style(font,percent,pixel);}
 internal TextStylePolicy Copy(){return Parse(Serialize());}
 // Sizes can change live; keep the active face and its pixel baseline until restart.
 internal TextStylePolicy WithSizes(TextStylePolicy saved){var result=Copy();foreach(string role in Roles){var active=For(role);result.Change(role,active.Family,saved.For(role).Percent,active.PixelSize);}return result;}
 internal string Serialize(){var rows=new List<string>();foreach(string role in Roles){var s=For(role);rows.Add("\""+role+"\":{\"font\":"+Quote(s.Family)+",\"size_percent\":"+s.Percent.ToString(CultureInfo.InvariantCulture)+(s.PixelSize>0?",\"pixel_size\":"+s.PixelSize.ToString(CultureInfo.InvariantCulture):"")+"}");}return "{\"format\":1,\"roles\":{"+String.Join(",",rows.ToArray())+"}}\n";}
 static string Quote(string value){var b=new StringBuilder("\"");foreach(char c in value){if(c=='\\'||c=='\"')b.Append('\\');b.Append(c);}return b.Append('"').ToString();}
 internal static TextStylePolicy Parse(string text){
  if(text==null||text.Length>32768)throw new FormatException("style size");
  var root=Json.Read(text) as Hashtable;if(root==null||root.Count!=2||!(root["format"] is int)||(int)root["format"]!=1||!(root["roles"] is Hashtable))throw new FormatException("style format");
  var result=new TextStylePolicy();foreach(DictionaryEntry entry in (Hashtable)root["roles"]){
   string role=entry.Key as string;var value=entry.Value as Hashtable;
   if(role==null||!result.roles.ContainsKey(role)||value==null||(value.Count!=2&&value.Count!=3)||!(value["font"] is string)||!(value["size_percent"] is int))throw new FormatException("style role");
   string font=(string)value["font"];int percent=(int)value["size_percent"];
   int pixel=0;if(value.ContainsKey("pixel_size")){if(!(value["pixel_size"] is int))throw new FormatException("pixel size");pixel=(int)value["pixel_size"];}
   if(value.Count==3&&!value.ContainsKey("pixel_size")||!FontReference(font)||percent<75||percent>150||pixel<0||pixel>64)throw new FormatException("style value");
   result.roles[role]=new Style(font,percent,pixel);
  }return result;
 }
 internal static bool FontId(string value){if(String.IsNullOrEmpty(value)||value.Length>32||value[0]<'a'||value[0]>'z')return false;foreach(char c in value)if(!(c>='a'&&c<='z'||c>='0'&&c<='9'||c=='_'||c=='-'))return false;return true;}
 internal static bool FontReference(string value){if(FontId(value))return true;if(String.IsNullOrEmpty(value)||value.Length>128||value[0]=='.'||!(value.EndsWith(".ttf",StringComparison.OrdinalIgnoreCase)||value.EndsWith(".otf",StringComparison.OrdinalIgnoreCase)))return false;foreach(char c in value)if(Char.IsControl(c)||"/\\:\"<>|*?".IndexOf(c)>=0)return false;return true;}
 internal static string Role(string name,string path){
  name=name??"";path=path??"";
  if(path.StartsWith("EntryPoints/",StringComparison.Ordinal))return Ui;
  if(name=="PreludeText"||(name=="MessageText"&&path.IndexOf("MessageDialog",StringComparison.Ordinal)>=0))return Body;
  if(name=="CharacterName"||name=="MapTitleLabel"||name=="SunTitle"||name=="EntryTitle"||name=="EntryTitle2"||name.EndsWith("TitleLabel",StringComparison.Ordinal))return Title;
  foreach(string token in new[]{"Energy","Aether","Ore","Score","Production","Supply","Timer","FPS"})if(name.IndexOf(token,StringComparison.Ordinal)>=0)return Status;
  return Ui;
 }
 internal static int Size(int native,int percent){if(percent==100)return native;return Math.Max(1,Math.Min(192,(native*percent+50)/100));}
 internal static int PixelSize(int native,int percent,int unit){int wanted=Size(native<=0?unit:native,percent);return Math.Max(unit,Math.Min(192/unit*unit,((wanted+unit/2)/unit)*unit));}
 internal static string Family(string requested,bool available,bool glyphs,out string reason){reason="";if(requested!="sans"&&!available){reason=requested+"_unavailable";return "sans";}if(requested!="sans"&&!glyphs){reason=requested+"_missing_glyph";return "sans";}return requested;}
}
