using System;
using System.IO;
using System.Text;

// Read the installed static SFNT font's family; no Unity/registry dependency.
// Unique family names prevent an older face with the same name winning selection.
internal static class FontFile {
 static int U16(byte[] data,int at){Range(data,at,2);return data[at]*256+data[at+1];}
 static int U32(byte[] data,int at){Range(data,at,4);uint n=((uint)data[at]<<24)|((uint)data[at+1]<<16)|((uint)data[at+2]<<8)|data[at+3];if(n>Int32.MaxValue)throw new FormatException("Font offset");return (int)n;}
 static void Range(byte[] data,int at,int count){if(at<0||count<0||at>data.Length-count)throw new FormatException("Font table bounds");}
 internal static string Family(string file){
  if(new FileInfo(file).Length>50000000)throw new FormatException("Font too large");
  byte[] data=File.ReadAllBytes(file);int tables=U16(data,4),table=-1,size=0;
  for(int i=0;i<tables;i++){int at=12+i*16;Range(data,at,16);if(Encoding.ASCII.GetString(data,at,4)=="name"){table=U32(data,at+8);size=U32(data,at+12);break;}}
  if(table<0)throw new FormatException("Font name table missing");Range(data,table,size);
  int records=U16(data,table+2),storage=U16(data,table+4),best=-1;string family=null;
  for(int i=0;i<records;i++){
   int at=table+6+i*12;Range(data,at,12);int platform=U16(data,at),encoding=U16(data,at+2),language=U16(data,at+4),id=U16(data,at+6),length=U16(data,at+8),offset=U16(data,at+10);
   if(id!=1&&id!=16)continue;if(platform!=0&&!(platform==3&&(encoding==1||encoding==10)))continue;
   int start=table+storage+offset;Range(data,start,length);if(start<table||start+length>table+size||length%2!=0)throw new FormatException("Font name bounds");
   string name=Encoding.BigEndianUnicode.GetString(data,start,length);if(!name.StartsWith("CW3 Sans SC External",StringComparison.Ordinal))continue;
   int score=(id==16?4:0)+(platform==3?2:0)+(language==0x409?1:0);if(score>best){best=score;family=name;}
  }
  if(family==null)throw new FormatException("Expected CW3 external OFL font family");return family;
 }
}
