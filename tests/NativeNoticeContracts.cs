using System;using System.Collections;using System.Collections.Generic;using System.IO;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
class NativeNoticeContracts {
 static void Need(bool b,string s){if(!b)throw new Exception(s);}
 static void Main(string[]a){var asm=AssemblyDefinition.ReadAssembly(a[0]);var root=(Hashtable)Json.Read(File.ReadAllText(a[1]));var defs=new Dictionary<string,Hashtable>();var translations=new Dictionary<string,string>();var sites=new Dictionary<string,Hashtable>();int keyNames=0;
 foreach(Hashtable e in (ArrayList)root["entries"]){defs.Add((string)e["id"],e);translations.Add((string)e["id"],(string)e["translation"]);var t=(Hashtable)e["target"];if((string)t["kind"]=="managed")sites.Add(t["method_token"]+":"+t["instruction_index"],e);if(((string)e["context"]).EndsWith("/ pickup display name"))keyNames++;}
 var eventMethod=asm.MainModule.GetType("GameEventManager").Methods.Single(m=>m.Name=="ShowEvent"&&m.Parameters[0].ParameterType.FullName=="GameEventManager/GAME_EVENT");int captions=0,icons=0;var xs=eventMethod.Body.Instructions;
 for(int at=0;at<xs.Count-1;at++){var i=xs[at];if(i.OpCode!=OpCodes.Ldstr)continue;var next=xs[at+1];bool caption=next.OpCode==OpCodes.Stloc_3||next.OpCode==OpCodes.Stloc_S&&((VariableDefinition)next.Operand).Index==4;bool icon=next.OpCode==OpCodes.Stloc_2;
  if(caption){NativeEventCaptionAudit.Require(eventMethod,i);Hashtable e;Need(sites.TryGetValue(eventMethod.MetadataToken.ToInt32()+":"+at,out e),"Every native event caption must be bound");Need((string)e["source"]==(string)i.Operand,"Event source guard");string reason;Need(FixedText.Resolve(defs,translations,(string)e["id"],(string)i.Operand,out reason)!=(string)i.Operand,"Native event caption translates");captions++;}
  if(icon){bool rejected=false;try{NativeEventCaptionAudit.Require(eventMethod,i);}catch(Exception){rejected=true;}Need(rejected,"Icon key must be rejected");Need(!sites.ContainsKey(eventMethod.MetadataToken.ToInt32()+":"+at),"Internal icon key must stay English");icons++;}
 }
 int notices=0;foreach(string type in new[]{"GameSpace","ShieldKeyManager"})foreach(var m in asm.MainModule.GetType(type).Methods.Where(m=>new[]{"GameUpdate","FailMission","ArrivedInOrbit"}.Contains(m.Name)))for(int at=0;at<m.Body.Instructions.Count;at++){
  var i=m.Body.Instructions[at];if(i.OpCode!=OpCodes.Ldstr||!new[]{"World Secure!\n Completion Time: ","Claim Victory!","Continue Playing","Mission Failure","Restart Mission","Exit Mission","Collected: "}.Contains((string)i.Operand))continue;
  Hashtable e;Need(sites.TryGetValue(m.MetadataToken.ToInt32()+":"+at,out e),"Native outcome/pickup caption missing");GuiCaptionAudit.Require(m,i);Need((string)e["source"]==(string)i.Operand,"Outcome source guard");notices++;
 }
 int liveCaptions=0;foreach(string type in new[]{"CommandCenter","BuildHandlers","WorldMachineManager"})foreach(var m in asm.MainModule.GetType(type).Methods.Where(m=>new[]{"UnitsSelected","UpdateTechLabels","DoWorldMachineWindow","SeedSetting"}.Contains(m.Name)))for(int at=0;at<m.Body.Instructions.Count;at++){
  var i=m.Body.Instructions[at];if(i.OpCode!=OpCodes.Ldstr||!new[]{"Upgrade to Lvl: "," for ","Price: ","Map Code:","Rand"}.Contains((string)i.Operand))continue;
  Hashtable e;Need(sites.TryGetValue(m.MetadataToken.ToInt32()+":"+at,out e),"Live upgrade/price/map-code caption missing");GuiCaptionAudit.Require(m,i);Need((string)e["source"]==(string)i.Operand,"Live caption source guard");liveCaptions++;
 }
 Need(liveCaptions==10,"Expected 10 live upgrade/price/map-code captions");
 Need(captions==30&&icons>20&&notices==7&&keyNames==22,"Expected bounded CW3 native notice inventory");Console.WriteLine("PASS 30 event captions, "+icons+" protected icon keys, 7 outcome/pickup captions and 22 adopted key names; 10 live upgrade/price/map-code captions");
 }
}
