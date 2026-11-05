using System;using System.IO;
class NativeFontBundleContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Exact(string path,byte[] expected){byte[] actual=File.ReadAllBytes(path);Need(actual.Length==expected.Length,"exact cache length");for(int i=0;i<actual.Length;i++)if(actual[i]!=expected[i])throw new Exception("exact cache content at "+i);}
 static void Main(string[] args){var face=new LocalFontFile(File.ReadAllBytes(args[0]));byte[] bytes=NativeFontBundle.Build(face);File.WriteAllBytes(args[1],bytes);byte[] point=NativeFontBundle.Build(face,true);File.WriteAllBytes(args[1]+".point",point);Need(NativeFontBundle.Name(face)!=NativeFontBundle.Name(face,true)&&LocalFontFile.Digest(bytes)!=LocalFontFile.Digest(point),"sampling modes have independent native identities");Need(bytes.Length>face.Data.Length,"native payload has a complete container");
  string cache=args[1]+".cache";try{
   Need(!NativeFontBundle.EnsureCached(cache,face),"missing cache regenerated");Exact(cache,bytes);
   DateTime stamp=new DateTime(2001,2,3,4,5,6,DateTimeKind.Utc);File.SetLastWriteTimeUtc(cache,stamp);
   Need(NativeFontBundle.EnsureCached(cache,face),"native cache reused");Need(File.GetLastWriteTimeUtc(cache)==stamp,"cache hit does not rewrite");
   foreach(int at in new[]{0,60,112,32767,32768,bytes.Length/2,bytes.Length-1}){if(at>=bytes.Length)continue;using(var s=new FileStream(cache,FileMode.Open,FileAccess.Write)){s.Position=at;s.WriteByte((byte)(bytes[at]^1));}Need(!NativeFontBundle.EnsureCached(cache,face),"same-length corruption rejected at "+at);Exact(cache,bytes);}
   using(var s=new FileStream(cache,FileMode.Open,FileAccess.Write))s.SetLength(bytes.Length-1);Need(!NativeFontBundle.EnsureCached(cache,face),"truncated cache rejected");Exact(cache,bytes);
   using(var s=new FileStream(cache,FileMode.Append,FileAccess.Write))s.WriteByte(0);Need(!NativeFontBundle.EnsureCached(cache,face),"trailing byte rejected");Exact(cache,bytes);
   Need(!NativeFontBundle.EnsureCached(cache,face,true),"sampling change rejects previous cache");Exact(cache,point);Need(NativeFontBundle.EnsureCached(cache,face,true),"point cache reused");
   // Valid SFNT files may have trailing bytes. Exercise source identity and every
   // alignment residue without depending on a particular input font's size.
   for(int extra=1;extra<=8;extra++){byte[] changed=new byte[face.Data.Length+extra];Buffer.BlockCopy(face.Data,0,changed,0,face.Data.Length);var other=new LocalFontFile(changed);Need(!NativeFontBundle.EnsureCached(cache,other),"source change rejects previous cache");Exact(cache,NativeFontBundle.Build(other));Need(NativeFontBundle.EnsureCached(cache,other),"aligned source cache reused");}
   Need(Directory.GetFiles(Path.GetDirectoryName(cache),Path.GetFileName(cache)+".*.tmp").Length==0,"transaction leftovers removed");
   File.Delete(cache);Directory.CreateDirectory(cache);bool failed=false;try{NativeFontBundle.EnsureCached(cache,face);}catch(IOException){failed=true;}Need(failed&&Directory.Exists(cache),"failed publication preserves existing target");Need(Directory.GetFiles(Path.GetDirectoryName(cache),Path.GetFileName(cache)+".*.tmp").Length==0,"failed publication removes temporary file");
  }finally{if(File.Exists(cache))File.Delete(cache);if(Directory.Exists(cache))Directory.Delete(cache);}
  Console.WriteLine("PASS native bundle creation, exact content cache, source/sampling changes, corruption regeneration and atomic publication cleanup; output requires independent Unity parsing");
 }
}
