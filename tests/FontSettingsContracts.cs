using System;using System.IO;
class FontSettingsContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(){string dir=Path.Combine(Path.GetTempPath(),"cw3-settings-"+Guid.NewGuid());Directory.CreateDirectory(dir);
  try{
   string path=Path.Combine(dir,"text-style.json");var active=new TextStylePolicy();active.Change("ui","missing.ttf",113,12);string original=active.Serialize();File.WriteAllText(path,original);
   var m=new FontSettingsModel(dir,active);m.Draft.Change("ui","文楷 Screen.ttf",125,0);m.Cancel();Need(File.ReadAllText(path)==original&&m.Draft.For("ui").PixelSize==12&&!m.Dirty&&!m.Pending,"cancel preserves bytes, pixel metadata and active settings");
   m.Draft.Change("body","文楷 Screen.ttf",145,0);m.Save();Need(m.Pending&&!m.Dirty&&m.Active.For("body").Family=="sans","save records restart requirement without changing active renderer");
   var reopened=new FontSettingsModel(dir,active);Need(reopened.Pending&&reopened.Draft.For("body").Family=="文楷 Screen.ttf"&&reopened.Draft.For("ui").Percent==113,"reentry keeps saved choices and arbitrary valid percentage");
   var running=active.WithSizes(reopened.Saved);reopened.Applied(running,0);Need(reopened.Pending&&reopened.Active.For("body").Family=="sans"&&reopened.Active.For("body").Percent==145,"mixed font change applies size to current face and retains restart flag");
   var sizeOnly=new FontSettingsModel(dir,running);sizeOnly.Draft.Change("ui","missing.ttf",125,12);sizeOnly.Save();sizeOnly.Applied(running.WithSizes(sizeOnly.Saved),0);Need(sizeOnly.Active.For("ui").Percent==125&&sizeOnly.Pending,"different pending role remains pending");
   var restored=new TextStylePolicy();File.WriteAllText(path,restored.Serialize());var live=new FontSettingsModel(dir,restored);live.Draft.Change("body","sans",125,0);live.Save();live.Applied(restored.WithSizes(live.Saved),0);Need(!live.Pending&&live.Notice.Contains("即时"),"size-only save reports immediate application");string liveSaved=File.ReadAllText(path);live.Draft.Change("body","sans",150,0);live.Cancel();Need(live.Active.For("body").Percent==125&&File.ReadAllText(path)==liveSaved,"cancel keeps prior committed live size");
   File.WriteAllText(path,m.Saved.Serialize());
   string saved=File.ReadAllText(path);m.Defaults();m.Cancel();Need(File.ReadAllText(path)==saved&&m.Draft.For("ui").Family=="missing.ttf","default then cancel does not write");
   m.Defaults();m.Save();foreach(string role in TextStylePolicy.Roles)Need(TextStylePolicy.Parse(File.ReadAllText(path)).For(role).Family=="sans","explicit default save");
   m.Draft.Change("title","serif",150,0);File.WriteAllText(path,original);bool conflict=false;try{m.Save();}catch(IOException){conflict=true;}Need(conflict&&File.ReadAllText(path)==original,"external edit is never overwritten");
   Directory.CreateDirectory(Path.Combine(dir,"fonts"));File.WriteAllText(Path.Combine(dir,"fonts/汉字字体.otf"),"fixture");File.WriteAllText(Path.Combine(dir,"fonts/font.woff"),"fixture");var choices=FontSettingsModel.Choices(dir,new[]{"sans","serif","legacy"},active);Need(Array.IndexOf(choices,"汉字字体.otf")>=0&&Array.IndexOf(choices,"missing.ttf")>=0&&Array.IndexOf(choices,"font.woff")<0,"discover supported files and retain missing current choice");
   File.WriteAllText(path,"invalid");var invalid=new FontSettingsModel(dir,active);Need(invalid.Notice.Length>0&&File.ReadAllText(path)=="invalid","bad config is not rewritten on open");invalid.Save();Need(TextStylePolicy.Parse(File.ReadAllText(path)).For("ui").Family=="sans","save repairs bad config");
   Need(Directory.GetFiles(dir,"*.tmp").Length==0,"no transaction leftovers");Console.WriteLine("PASS settings persistence, cancel/default transactions, restart separation, reentry, conflict protection and font discovery");
  }finally{Directory.Delete(dir,true);}
 }
}
