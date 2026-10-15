using System;using System.IO;using System.Collections;using System.Collections.Generic;
class TranslationFileContracts {
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static string Doc(string entries){return "{\"format\":1,\"language\":\"zh-CN\",\"entries\":["+entries+"]}";}
 static string Row(string id,string source,string value){return "{\"id\":\""+id+"\",\"source\":\""+source+"\",\"translation\":\""+value+"\"}";}
 static void Main(string[] args){
  string folder=args[0],defaults=Path.Combine(folder,"zh-CN.default.json"),user=Path.Combine(folder,"zh-CN.user.json");
  var defs=new Dictionary<string,Hashtable>();foreach(string id in new[]{"edited","corrected","added","guarded"})defs[id]=new Hashtable{{"source",id=="guarded"?"Count {0}":id}};
  File.WriteAllText(Path.Combine(folder,"zh-CN.json"),Doc(Row("corrected","corrected","OLD LEGACY")));
  File.WriteAllText(defaults,Doc(Row("edited","edited","DEFAULT")+","+Row("corrected","corrected","CORRECTION")+","+Row("added","added","NEW ENTRY")+","+Row("guarded","Count {0}","数量 {0}")));
  string custom=Doc(Row("edited","edited","USER")+","+Row("guarded","Count {0}","BROKEN PLACEHOLDER")+","+Row("added","WRONG SOURCE","BAD SOURCE"));File.WriteAllText(user,custom);
  int warnings=0;var values=TranslationFiles.Load(folder,defs,message=>warnings++);
  Need(values["edited"]=="USER"&&values["corrected"]=="CORRECTION"&&values["added"]=="NEW ENTRY"&&values["guarded"]=="数量 {0}","User overrides only matching valid entries; legacy defaults cannot shadow the release");
  File.WriteAllText(defaults,Doc(Row("edited","edited","NEXT DEFAULT")+","+Row("corrected","corrected","NEXT CORRECTION")+","+Row("added","added","NEXT ENTRY")));
  values=TranslationFiles.Load(folder,defs,message=>warnings++);Need(values["edited"]=="USER"&&values["corrected"]=="NEXT CORRECTION"&&values["added"]=="NEXT ENTRY"&&File.ReadAllText(user)==custom,"Default upgrades and new entries are visible while user bytes survive");
  File.WriteAllText(user,Doc(Row("corrected","corrected","BAD PARTIAL")+","+Row("corrected","corrected","DUPLICATE")));
  values=TranslationFiles.Load(folder,defs,message=>warnings++);Need(values["corrected"]=="NEXT CORRECTION"&&warnings==1,"Malformed override cannot partially overwrite defaults");
  File.Delete(user);File.Delete(defaults);values=TranslationFiles.Load(folder,defs,message=>warnings++);Need(values.Count==0&&warnings==2,"A missing release file cannot silently reactivate retired legacy defaults");
  Console.WriteLine("PASS release defaults, corrections/new entries, persistent user overrides, source/token guards and malformed override isolation");
 }
}
