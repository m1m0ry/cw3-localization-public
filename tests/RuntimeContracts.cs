using System;using System.Collections;using System.IO;
// Executable contracts for pure parsing boundaries; no game/Unity initialization.
class RuntimeContracts {
 static void Need(bool b,string s){if(!b)throw new Exception(s);}
 static void Bad(Action action){try{action();}catch(FormatException){return;}throw new Exception("Malformed input accepted");}
 static void Main(string[] args){
  var value=(Hashtable)Json.Read("{\"汉字\":\"line\\n\\u9f98\",\"rows\":[-2,null,true]}");Need((string)value["汉字"]=="line\n龘","Unicode/escape decoding");Need(((ArrayList)value["rows"]).Count==3,"Arrays");
  foreach(string text in new[]{"{", "{\"x\":1,\"x\":2}","{\"x\":01}","[] trailing","\"bad\\q\""})Bad(()=>Json.Read(text));
  foreach(string text in (ArrayList)Json.Read(File.ReadAllText(args[3])))Bad(()=>Json.Read(text));
  Need(FontFile.Family(args[0]).StartsWith("CW3 Sans SC External "),"Installed external family");Bad(()=>FontFile.Family(args[1]));
  string corrupt=Path.Combine(args[2],"font-invalid-test.ttf");File.WriteAllBytes(corrupt,new byte[]{0,1,0,0,0,1});try{Bad(()=>FontFile.Family(corrupt));}finally{File.Delete(corrupt);}
  Console.WriteLine("PASS strict JSON Unicode/duplicate/truncation contracts and bounded SFNT family selection; no game code executed.");
 }
}
