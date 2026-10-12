using System;using System.IO;
class FontSettingsContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(){string dir=Path.Combine(Path.GetTempPath(),"cw3-settings-"+Guid.NewGuid());Directory.CreateDirectory(dir);
  try{
   string first=Path.Combine(dir,"text-style.json");var fresh=new FontSettingsModel(dir,new TextStylePolicy());Need(!File.Exists(first),"missing config stays absent until save");
   foreach(string role in TextStylePolicy.Roles){var d=fresh.Saved.For(role);Need(d.Family=="sans"&&d.Percent==100&&d.PixelSize==0,"missing config uses shared defaults");}
   File.WriteAllText(first,"{\n  \"format\":1,\n  \"roles\":{}\n}\n");var unchanged=new FontSettingsModel(dir,new TextStylePolicy());Need(!unchanged.Dirty,"unchanged values are not dirty");unchanged.Save();
   var normalized=TextStylePolicy.Parse(File.ReadAllText(first));foreach(string role in TextStylePolicy.Roles){var d=normalized.For(role);Need(d.Family=="sans"&&d.Percent==100&&d.PixelSize==0,"no-change save keeps parsed defaults");}File.Delete(first);
   string path=Path.Combine(dir,"text-style.json");var active=new TextStylePolicy();active.Change("ui","missing.ttf",113,12);string original=active.Serialize();File.WriteAllText(path,original);
   var m=new FontSettingsModel(dir,active);m.Draft.Change("ui","文楷 Screen.ttf",125,0);m.Cancel();Need(File.ReadAllText(path)==original&&m.Draft.For("ui").PixelSize==12&&!m.Dirty&&!m.Pending,"cancel preserves bytes, pixel metadata and active settings");
   m.Draft.Change("body","文楷 Screen.ttf",145,0);m.Save();Need(m.Pending&&!m.Dirty&&m.Active.For("body").Family=="sans","save records restart requirement without changing active renderer");
   var reopened=new FontSettingsModel(dir,active);Need(reopened.Pending&&reopened.Draft.For("body").Family=="文楷 Screen.ttf"&&reopened.Draft.For("ui").Percent==113,"reentry keeps saved choices and arbitrary valid percentage");
   var running=active.WithSizes(reopened.Saved);reopened.Applied(running,0);Need(reopened.Pending&&reopened.Active.For("body").Family=="sans"&&reopened.Active.For("body").Percent==145,"mixed font change applies size to current face and retains restart flag");
   var sizeOnly=new FontSettingsModel(dir,running);sizeOnly.Draft.Change("ui","missing.ttf",125,12);sizeOnly.Save();sizeOnly.Applied(running.WithSizes(sizeOnly.Saved),0);Need(sizeOnly.Active.For("ui").Percent==125&&sizeOnly.Pending,"different pending role remains pending");
   var restored=new TextStylePolicy();File.WriteAllText(path,restored.Serialize());var live=new FontSettingsModel(dir,restored);live.Draft.Change("body","sans",125,0);live.Save();live.Applied(restored.WithSizes(live.Saved),0);Need(!live.Pending&&live.Notice.Contains("即时"),"size-only save reports immediate application");string liveSaved=File.ReadAllText(path);live.Draft.Change("body","sans",150,0);live.Cancel();Need(live.Active.For("body").Percent==125&&File.ReadAllText(path)==liveSaved,"cancel keeps prior committed live size");
   File.WriteAllText(path,m.Saved.Serialize());
   string saved=File.ReadAllText(path);m.Defaults();m.Cancel();Need(File.ReadAllText(path)==saved&&m.Draft.For("ui").Family=="missing.ttf","default then cancel does not write");
   m.Defaults();m.Save();foreach(string role in TextStylePolicy.Roles){var d=TextStylePolicy.Parse(File.ReadAllText(path)).For(role);Need(d.Family=="sans"&&d.Percent==100&&d.PixelSize==0,"explicit default save uses shared parsed defaults");}
   m.Draft.Change("title","serif",150,0);File.WriteAllText(path,original);bool conflict=false;try{m.Save();}catch(IOException){conflict=true;}Need(conflict&&File.ReadAllText(path)==original,"external edit is never overwritten");
   Directory.CreateDirectory(Path.Combine(dir,"fonts"));File.WriteAllText(Path.Combine(dir,"fonts/汉字字体.otf"),"fixture");File.WriteAllText(Path.Combine(dir,"fonts/font.woff"),"fixture");var choices=FontSettingsModel.Choices(dir,new[]{"sans","serif","legacy"},active);Need(Array.IndexOf(choices,"汉字字体.otf")>=0&&Array.IndexOf(choices,"missing.ttf")>=0&&Array.IndexOf(choices,"font.woff")<0,"discover supported files and retain missing current choice");
   File.WriteAllText(path,"invalid");var invalid=new FontSettingsModel(dir,active);Need(invalid.Notice.Length>0&&File.ReadAllText(path)=="invalid","bad config is not rewritten on open");invalid.Save();foreach(string role in TextStylePolicy.Roles){var d=TextStylePolicy.Parse(File.ReadAllText(path)).For(role);Need(d.Family=="sans"&&d.Percent==100&&d.PixelSize==0,"bad config save uses shared defaults");}
   Need(Directory.GetFiles(dir,"*.tmp").Length==0,"no transaction leftovers");Console.WriteLine("PASS settings persistence, cancel/default transactions, restart separation, reentry, conflict protection and font discovery");
  }finally{Directory.Delete(dir,true);}
 }
}
