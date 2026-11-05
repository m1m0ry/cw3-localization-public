using System;using System.IO;using System.Text;

// Target-generated Unity-5.2.3 envelope. Font objects are constructed from trusted metadata;
// variable user bytes never become field names, paths, callbacks or game resource IDs.
internal static class NativeFontBundle {
 static byte[] Part(string value){return Convert.FromBase64String(value);}
 static void Align(BinaryWriter w,int unit,int start=0){while((start+w.BaseStream.Position)%unit!=0)w.Write((byte)0);}
 static void String(BinaryWriter w,string value,int start=0){byte[] bytes=Encoding.UTF8.GetBytes(value);w.Write(bytes.Length);w.Write(bytes);Align(w,4,start);}
 static void UInt(byte[] data,int at,int value,bool big){byte[] b=BitConverter.GetBytes(value);if(big)Array.Reverse(b);Buffer.BlockCopy(b,0,data,at,4);}
 static void BE(BinaryWriter w,int value){byte[] b=BitConverter.GetBytes(value);Array.Reverse(b);w.Write(b);}
 static void Z(BinaryWriter w,string value){w.Write(Encoding.ASCII.GetBytes(value));w.Write((byte)0);}
 static string Identity(LocalFontFile face,bool point){return point?LocalFontFile.Digest(Encoding.UTF8.GetBytes("point:"+face.Hash+":"+NativeFontTemplate.Key)):face.Hash;}
 internal static string Name(LocalFontFile face,bool point=false){return "CW3Local_"+(point?"Point_":"")+Identity(face,point).Substring(0,12);}
 static void Object(BinaryWriter w,byte[] meta,int index,byte[] data,int start=0){UInt(meta,NativeFontTemplate.OffsetFields[index],checked(start+(int)w.BaseStream.Position),false);UInt(meta,NativeFontTemplate.SizeFields[index],data.Length,false);w.Write(data);Align(w,8,start);}
 // The source is the only large field. Keep it between two small envelope segments,
 // so cache hits can compare every byte without building/copying the full bundle or
 // hashing both copies. Segment offsets retain the original object alignment.
 static byte[][] Segments(LocalFontFile face,bool point){
  string identity=Identity(face,point);
  byte[] prefix=Part(NativeFontTemplate.FontPrefix),middle=Part(NativeFontTemplate.FontMiddle);Buffer.BlockCopy(BitConverter.GetBytes(face.LineSpacing),0,prefix,NativeFontTemplate.LineSpacing,4);Buffer.BlockCopy(BitConverter.GetBytes(face.Ascent),0,middle,NativeFontTemplate.Ascent,4);
  byte[] bundle;using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){w.Write(Part(NativeFontTemplate.BundlePrefix));String(w,"cw3-local-"+identity.Substring(0,32));w.Write(Part(NativeFontTemplate.BundleSuffix));bundle=s.ToArray();}
  byte[] meta=Part(NativeFontTemplate.Metadata);
  using(var before=new MemoryStream())using(var head=new BinaryWriter(before))using(var after=new MemoryStream())using(var tail=new BinaryWriter(after)){
   Object(head,meta,0,bundle);int fontOffset=checked((int)before.Position);
   String(head,Name(face,point));head.Write(prefix);head.Write(face.Data.Length);
   int afterStart=checked((int)before.Length+face.Data.Length);
   Align(tail,4,afterStart);tail.Write(middle);String(tail,face.Family,afterStart);tail.Write(Part(NativeFontTemplate.FontSuffix));
   UInt(meta,NativeFontTemplate.OffsetFields[1],fontOffset,false);UInt(meta,NativeFontTemplate.SizeFields[1],checked(afterStart+(int)after.Length-fontOffset),false);Align(tail,8,afterStart);
   Object(tail,meta,2,Part(NativeFontTemplate.Material),afterStart);Object(tail,meta,3,Part(NativeFontTemplate.Texture),afterStart);
   int assetsLength=checked(meta.Length+afterStart+(int)after.Length);UInt(meta,4,assetsLength,true);
   using(var s=new MemoryStream())using(var w=new BinaryWriter(s)){
    int total=checked(60+52+assetsLength);Z(w,"UnityRaw");BE(w,3);Z(w,"5.x.x");Z(w,"5.2.3f1");foreach(int value in new[]{total,60,1,1,52+assetsLength,52+assetsLength,total,52})BE(w,value);Align(w,4);
    BE(w,1);Z(w,"CAB-"+identity.Substring(0,32));BE(w,52);BE(w,assetsLength);Align(w,4);w.Write(meta);w.Write(before.ToArray());
    return new[]{s.ToArray(),face.Data,after.ToArray()};
   }
  }
 }
 static int Length(byte[][] segments){int length=0;foreach(byte[] part in segments)length=checked(length+part.Length);return length;}
 internal static byte[] Build(LocalFontFile face,bool point=false){byte[][] segments=Segments(face,point);byte[] bytes=new byte[Length(segments)];int at=0;foreach(byte[] part in segments){Buffer.BlockCopy(part,0,bytes,at,part.Length);at+=part.Length;}return bytes;}
 static bool Cached(string path,byte[][] segments){
  if(!File.Exists(path))return false;
  using(var s=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read)){
   if(s.Length!=Length(segments))return false;byte[] buffer=new byte[32768];
   foreach(byte[] part in segments)for(int at=0;at<part.Length;){int count=s.Read(buffer,0,Math.Min(buffer.Length,part.Length-at));if(count==0)return false;for(int i=0;i<count;i++)if(buffer[i]!=part[at+i])return false;at+=count;}
   return s.ReadByte()==-1;
  }
 }
 // True means an intact existing cache was reused; false means atomic regeneration.
 internal static bool EnsureCached(string path,LocalFontFile face,bool point=false){byte[][] segments=Segments(face,point);if(Cached(path,segments))return true;
  string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";try{using(var s=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None))foreach(byte[] part in segments)s.Write(part,0,part.Length);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}finally{if(File.Exists(temp))File.Delete(temp);}return false;
 }
}
