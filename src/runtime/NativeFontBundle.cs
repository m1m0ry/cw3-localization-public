using System;using System.IO;using System.Text;

// Fixed Windows/Unity-5.2.3 envelope. Font objects are constructed from trusted metadata;
// variable user bytes never become field names, paths, callbacks or game resource IDs.
internal static class NativeFontBundle {
 static byte[] Part(string value){return Convert.FromBase64String(value);}
 static void Align(BinaryWriter w,int unit){while(w.BaseStream.Position%unit!=0)w.Write((byte)0);}
 static void String(BinaryWriter w,string value){byte[] bytes=Encoding.UTF8.GetBytes(value);w.Write(bytes.Length);w.Write(bytes);Align(w,4);}
 static void UInt(byte[] data,int at,int value,bool big){byte[] b=BitConverter.GetBytes(value);if(big)Array.Reverse(b);Buffer.BlockCopy(b,0,data,at,4);}
 static void BE(BinaryWriter w,int value){byte[] b=BitConverter.GetBytes(value);Array.Reverse(b);w.Write(b);}
 static void Z(BinaryWriter w,string value){w.Write(Encoding.ASCII.GetBytes(value));w.Write((byte)0);}
 static string Identity(LocalFontFile face,bool point){return point?LocalFontFile.Digest(Encoding.UTF8.GetBytes("point:"+face.Hash+":"+NativeFontTemplate.Key)):face.Hash;}
 internal static string Name(LocalFontFile face,bool point=false){return "CW3Local_"+(point?"Point_":"")+Identity(face,point).Substring(0,12);}
 internal static byte[] Build(LocalFontFile face,bool point=false){
  string identity=Identity(face,point);
  byte[] prefix=Part(NativeFontTemplate.FontPrefix),middle=Part(NativeFontTemplate.FontMiddle);Buffer.BlockCopy(BitConverter.GetBytes(face.LineSpacing),0,prefix,NativeFontTemplate.LineSpacing,4);Buffer.BlockCopy(BitConverter.GetBytes(face.Ascent),0,middle,NativeFontTemplate.Ascent,4);
  byte[] font,bundle;
  using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){String(w,Name(face,point));w.Write(prefix);w.Write(face.Data.Length);w.Write(face.Data);Align(w,4);w.Write(middle);String(w,face.Family);w.Write(Part(NativeFontTemplate.FontSuffix));font=s.ToArray();}
  using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){w.Write(Part(NativeFontTemplate.BundlePrefix));String(w,"cw3-local-"+identity.Substring(0,32));w.Write(Part(NativeFontTemplate.BundleSuffix));bundle=s.ToArray();}
  byte[] meta=Part(NativeFontTemplate.Metadata),assets;byte[][] objects={bundle,font,Part(NativeFontTemplate.Material),Part(NativeFontTemplate.Texture)};
  using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){for(int i=0;i<objects.Length;i++){UInt(meta,NativeFontTemplate.OffsetFields[i],checked((int)s.Position),false);UInt(meta,NativeFontTemplate.SizeFields[i],objects[i].Length,false);w.Write(objects[i]);Align(w,8);}UInt(meta,4,checked(meta.Length+(int)s.Length),true);assets=new byte[meta.Length+s.Length];Buffer.BlockCopy(meta,0,assets,0,meta.Length);Buffer.BlockCopy(s.ToArray(),0,assets,meta.Length,(int)s.Length);}
  using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){
   int total=checked(60+52+assets.Length);Z(w,"UnityRaw");BE(w,3);Z(w,"5.x.x");Z(w,"5.2.3f1");foreach(int value in new[]{total,60,1,1,52+assets.Length,52+assets.Length,total,52})BE(w,value);Align(w,4);
   BE(w,1);Z(w,"CAB-"+identity.Substring(0,32));BE(w,52);BE(w,assets.Length);Align(w,4);w.Write(assets);return s.ToArray();
  }
 }
 internal static bool Cached(string path,byte[] expected){if(!File.Exists(path)||new FileInfo(path).Length!=expected.Length)return false;return LocalFontFile.Digest(File.ReadAllBytes(path))==LocalFontFile.Digest(expected);}
 internal static void Save(string path,byte[] bytes){string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";try{File.WriteAllBytes(temp,bytes);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}finally{if(File.Exists(temp))File.Delete(temp);}}
}
