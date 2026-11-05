using System;using System.IO;
class GameSettings {public static bool useCustomDataPath;public static string customDataPath="";public static bool NextCustom;public static string NextPath;public static void Read(){useCustomDataPath=NextCustom;customDataPath=NextPath;}}
class FileManager {
 public static string Documents;public static int Probes;
 public static string GetDocumentsDir(){Probes++;return Documents+"/";}
 public static void MigrateToLowerCase(){RenameDir(GetDocumentsDir(),"CreeperWorld3");RenameDir(GetDocumentsDir()+"creeperworld3/","ColonialSpace");}
 static void RenameDir(string root,string name){}
 public static string GetBaseDataDir(){string path;try{if(GameSettings.useCustomDataPath)path=GameSettings.customDataPath.Trim()+"/creeperworld3/";else path=GetDocumentsDir()+"creeperworld3/";if(!Directory.Exists(path))Directory.CreateDirectory(path);}catch(Exception){path=GetDocumentsDir()+"creeperworld3/";Directory.CreateDirectory(path);}return path;}
}
class SplashManager {public void Awake(){FileManager.MigrateToLowerCase();GC.KeepAlive(30);GameSettings.Read();}}
class CustomSavePathFixture {
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Main(string[] a){string root=a[0];FileManager.Documents=Path.Combine(root,"documents");Directory.CreateDirectory(FileManager.Documents);string custom=Path.Combine(root,"support");
  GameSettings.NextCustom=true;GameSettings.NextPath=custom;new SplashManager().Awake();Need(FileManager.Probes==0,"Custom migration must not probe Documents");
  string data=FileManager.GetBaseDataDir();Need(data==custom+"/creeperworld3/","Custom path shape");Need(Directory.Exists(data),"Custom directory created");File.WriteAllText(Path.Combine(data,"fixture-save.dat"),"saved");Need(File.ReadAllText(Path.Combine(data,"fixture-save.dat"))=="saved","Custom save/read");Need(FileManager.Probes==0,"Custom saves must not probe Documents");
  string blocked=Path.Combine(root,"blocked");File.WriteAllText(blocked,"file");GameSettings.NextPath=blocked;new SplashManager().Awake();bool failed=false;try{FileManager.GetBaseDataDir();}catch(IOException){failed=true;}Need(failed&&FileManager.Probes==0,"Invalid custom location fails without Documents fallback");
  GameSettings.NextCustom=false;new SplashManager().Awake();Need(FileManager.Probes==2,"Default migration retained");Need(FileManager.GetBaseDataDir()==FileManager.Documents+"/creeperworld3/","Default path retained");Console.WriteLine("PASS 8 custom save path contracts");
 }
}
