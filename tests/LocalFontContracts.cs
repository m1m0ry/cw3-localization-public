using System;using System.IO;
class LocalFontContracts {
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Reject(byte[] data){try{new LocalFontFile(data);}catch(FormatException){return;}throw new Exception("damaged font accepted");}
 static void Main(string[] args){byte[] data=File.ReadAllBytes(args[0]);var face=new LocalFontFile(data);Need(face.Family==args[1],"actual source family");Need(face.Hash==LocalFontFile.Digest(data),"exact source bytes");Need(Convert.ToBase64String(face.Coverage)==args[2],"source cmap matches independent fontTools parser");Need(face.Probe==87&&face.Advance==Int32.Parse(args[3]),"actual W advance at 20px");
  Reject(new byte[0]);Reject(new byte[30]);var copy=(byte[])data.Clone();copy[0]=0x74;copy[1]=0x74;copy[2]=0x63;copy[3]=0x66;Reject(copy);copy=(byte[])data.Clone();copy[4]=0xff;copy[5]=0xff;Reject(copy);copy=(byte[])data.Clone();for(int i=0;i<4;i++)copy[20+i]=0xff;Reject(copy);
  Console.WriteLine("PASS static SFNT family, full byte identity, independent BMP cmap/advance and malformed table rejection");
 }
}
