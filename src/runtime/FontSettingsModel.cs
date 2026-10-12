using System;using System.IO;using System.Collections.Generic;

// The settings transaction knows only the existing policy format, not the font renderer.
internal sealed class FontSettingsModel {
 internal TextStylePolicy Active;
 internal TextStylePolicy Draft, Saved;
 internal string Notice="";
 readonly string path;
 string original;
 internal FontSettingsModel(string folder,TextStylePolicy active){path=Path.Combine(folder,"text-style.json");Active=active.Copy();Open();}
 internal void Open(){original=File.Exists(path)?File.ReadAllText(path):null;try{Saved=original==null?new TextStylePolicy():TextStylePolicy.Parse(original);Notice=original==null?"尚未保存配置，使用默认值。":"";}catch(FormatException){Saved=new TextStylePolicy();Notice="配置无效；保存可恢复默认值。";}Draft=Saved.Copy();}
 internal bool Pending {get{return Saved.Serialize()!=Active.Serialize();}}
 internal bool Dirty {get{return Draft.Serialize()!=Saved.Serialize();}}
 internal void Cancel(){Draft=Saved.Copy();}
 internal void Defaults(){Draft=new TextStylePolicy();}
 internal void Save(){
  string current=File.Exists(path)?File.ReadAllText(path):null;
  if(current!=original)throw new IOException("配置已被外部修改，请取消并重新打开。");
  string text=Draft.Serialize();TextStylePolicy.Parse(text);
  string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
  try{File.WriteAllText(temp,text);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}
  finally{if(File.Exists(temp))File.Delete(temp);}
  original=text;Saved=Draft.Copy();Notice="已保存；字号将在下一帧应用。";
 }
 internal void Applied(TextStylePolicy active,int failures){Active=active.Copy();Notice=failures>0?"字号已启用；部分控件刷新失败，重新打开对应界面后重试。":Pending?"字号已应用；字体或像素基准改动需重启游戏。":"已保存；字号已即时应用。";}
 internal static string[] Choices(string folder,IEnumerable<string> registered,TextStylePolicy saved){
  var values=new List<string>{"sans","serif"};foreach(string id in registered)if(TextStylePolicy.FontReference(id)&&!values.Contains(id))values.Add(id);
  string dir=Path.Combine(folder,"fonts");if(Directory.Exists(dir))foreach(string file in Directory.GetFiles(dir)){string name=Path.GetFileName(file);if(values.Count<64&&TextStylePolicy.FontReference(name)&&!values.Contains(name)&&(File.GetAttributes(file)&FileAttributes.ReparsePoint)==0)values.Add(name);}
  values.Sort(StringComparer.OrdinalIgnoreCase);values.Remove("sans");values.Remove("serif");values.Insert(0,"serif");values.Insert(0,"sans");
  foreach(string role in TextStylePolicy.Roles){string id=saved.For(role).Family;if(!values.Contains(id))values.Add(id);}return values.ToArray();
 }
}
