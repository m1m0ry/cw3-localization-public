using System;using System.IO;
class NativeFontBundleContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(string[] args){var face=new LocalFontFile(File.ReadAllBytes(args[0]));byte[] bytes=NativeFontBundle.Build(face);File.WriteAllBytes(args[1],bytes);byte[] point=NativeFontBundle.Build(face,true);File.WriteAllBytes(args[1]+".point",point);Need(NativeFontBundle.Name(face)!=NativeFontBundle.Name(face,true)&&LocalFontFile.Digest(bytes)!=LocalFontFile.Digest(point),"sampling modes have independent native identities");Need(bytes.Length>face.Data.Length,"native payload has a complete container");
  string cache=args[1]+".cache";try{Need(!NativeFontBundle.Cached(cache,bytes),"missing cache detected");NativeFontBundle.Save(cache,bytes);Need(NativeFontBundle.Cached(cache,bytes),"native cache roundtrip");File.WriteAllBytes(cache,new byte[bytes.Length]);Need(!NativeFontBundle.Cached(cache,bytes),"same-length corruption rejected");NativeFontBundle.Save(cache,bytes);Need(NativeFontBundle.Cached(cache,bytes),"atomic corrupt-cache regeneration");Need(Directory.GetFiles(Path.GetDirectoryName(cache),Path.GetFileName(cache)+".*.tmp").Length==0,"transaction leftovers removed");}finally{if(File.Exists(cache))File.Delete(cache);}
  Console.WriteLine("PASS native bundle creation, content cache and corruption regeneration; output requires independent Unity parsing");
 }
}
