using System;using System.IO;using System.Text;using System.Collections.Generic;using System.Security.Cryptography;

// Validate static SFNT source bytes and coverage before native Unity Font loading.
internal sealed class LocalFontFile {
 internal readonly byte[] Data;internal readonly string Hash,Family;internal readonly Dictionary<int,int> Glyphs=new Dictionary<int,int>();
 internal readonly byte[] Coverage=new byte[8192];internal readonly int Probe,Advance;internal readonly float Ascent,LineSpacing;int em,metrics,glyphCount;int[] hmtx;
 struct Table {internal int Start,Size;}
 readonly Dictionary<string,Table> tables=new Dictionary<string,Table>();
 static void Range(byte[] d,int p,int n){if(p<0||n<0||p>d.Length-n)throw new FormatException("font table bounds");}
 int U16(int p){Range(Data,p,2);return Data[p]*256+Data[p+1];}
 int I16(int p){int n=U16(p);return n>=32768?n-65536:n;}
 int U32(int p){Range(Data,p,4);uint n=((uint)Data[p]<<24)|((uint)Data[p+1]<<16)|((uint)Data[p+2]<<8)|Data[p+3];if(n>Int32.MaxValue)throw new FormatException("font integer");return (int)n;}
 Table Get(string name,int minimum){Table t;if(!tables.TryGetValue(name,out t)||t.Size<minimum)throw new FormatException("font table "+name);return t;}
 internal static string Digest(byte[] data){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
 internal float AdvanceAt(int size){return hmtx[Math.Min(Glyphs[Probe],metrics-1)]*size/(float)em;}
 internal LocalFontFile(byte[] data){
  if(data==null||data.Length<12||data.Length>50000000)throw new FormatException("font size");Data=data;Hash=Digest(data);
  string sig=Encoding.ASCII.GetString(data,0,4);if(sig!="OTTO"&&!(data[0]==0&&data[1]==1&&data[2]==0&&data[3]==0))throw new FormatException("static TTF/OTF required");
  int count=U16(4);if(count<1||count>128)throw new FormatException("font tables");Range(data,12,count*16);
  for(int i=0;i<count;i++){int p=12+i*16;string name=Encoding.ASCII.GetString(data,p,4);var t=new Table{Start=U32(p+8),Size=U32(p+12)};Range(data,t.Start,t.Size);if(tables.ContainsKey(name))throw new FormatException("duplicate font table");tables.Add(name,t);}
  if(tables.ContainsKey("fvar")||tables.ContainsKey("CFF2")||!tables.ContainsKey("glyf")&&!tables.ContainsKey("CFF "))throw new FormatException("static outline font required");
  em=U16(Get("head",54).Start+18);glyphCount=U16(Get("maxp",6).Start+4);metrics=U16(Get("hhea",36).Start+34);
  if(em<16||em>16384||glyphCount<1||metrics<1||metrics>glyphCount)throw new FormatException("font metrics");
  Table hm=Get("hmtx",metrics*4+(glyphCount-metrics)*2);hmtx=new int[metrics];for(int i=0;i<metrics;i++)hmtx[i]=U16(hm.Start+i*4);
  int h=Get("hhea",36).Start;Ascent=I16(h+4)*20f/em;LineSpacing=(I16(h+4)-I16(h+6)+I16(h+8))*20f/em;if(LineSpacing<=0||LineSpacing>256)throw new FormatException("font line metrics");
  Family=Name();Cmap();foreach(var entry in Glyphs)Coverage[entry.Key/8]|=(byte)(1<<(entry.Key%8));
  foreach(int c in new[]{(int)'W',0x4e2d,(int)'A'})if(Glyphs.ContainsKey(c)){Probe=c;break;}
  if(Probe==0)foreach(int c in Glyphs.Keys)if(c>=33){Probe=c;break;}
  if(Probe==0)throw new FormatException("font has no BMP probe");Advance=(int)Math.Round(hmtx[Math.Min(Glyphs[Probe],metrics-1)]*20.0/em);
 }
 string Name(){Table t=Get("name",6);int records=U16(t.Start+2),storage=U16(t.Start+4);if(records>4096||6+records*12>t.Size||storage>t.Size)throw new FormatException("font names");int best=-1;string result=null;
  for(int i=0;i<records;i++){int p=t.Start+6+i*12,platform=U16(p),encoding=U16(p+2),language=U16(p+4),id=U16(p+6),length=U16(p+8),offset=U16(p+10);if(id!=1||platform!=0&&!(platform==3&&(encoding==1||encoding==10)))continue;
   if(length%2!=0||storage+offset>t.Size-length)throw new FormatException("font name bounds");int score=(platform==3?2:0)+(language==0x409?1:0);string value=Encoding.BigEndianUnicode.GetString(Data,t.Start+storage+offset,length);if(score>best){best=score;result=value;}}
  if(String.IsNullOrEmpty(result)||result.Length>256||result.IndexOf('\0')>=0)throw new FormatException("font family");return result;
 }
 void Add(int c,int glyph){if(c>0&&c<65536&&glyph>0&&glyph<glyphCount)Glyphs[c]=glyph;}
 void Cmap(){Table t=Get("cmap",4);int count=U16(t.Start+2);if(count>128||4+count*8>t.Size)throw new FormatException("font cmap");int at=-1,format=0,score=-1;
  for(int i=0;i<count;i++){int p=t.Start+4+i*8,platform=U16(p),encoding=U16(p+2),offset=U32(p+4);if(offset>t.Size-2)throw new FormatException("font cmap bounds");int f=U16(t.Start+offset);if((platform==0||platform==3&&(encoding==1||encoding==10))&&(f==4||f==12)){int rank=f==12?2:1;if(rank>score){score=rank;at=t.Start+offset;format=f;}}}
  if(at<0)throw new FormatException("font BMP cmap required");
  int length=format==4?U16(at+2):U32(at+4);if(length<16||at>t.Start+t.Size-length)throw new FormatException("font cmap length");int end=at+length;
  if(format==12){int countGroups=U32(at+12);if(countGroups>(length-16)/12)throw new FormatException("font cmap groups");int last=-1;
   for(int i=0;i<countGroups;i++){int p=at+16+i*12,start=U32(p),stop=U32(p+4),glyph=U32(p+8);if(start>stop||start<=last||stop>0x10ffff||glyph>glyphCount||stop-start>Int32.MaxValue-glyph)throw new FormatException("font cmap group");for(int c=start;c<=Math.Min(stop,65535);c++)Add(c,glyph+c-start);last=stop;}}
  else{int segments=U16(at+6)/2;if(segments<1||16+segments*8>length)throw new FormatException("font cmap segments");int ends=at+14,starts=ends+segments*2+2,deltas=starts+segments*2,ranges=deltas+segments*2;
   for(int i=0;i<segments;i++){int start=U16(starts+i*2),stop=U16(ends+i*2),delta=U16(deltas+i*2),offset=U16(ranges+i*2);if(start>stop)throw new FormatException("font cmap segment");for(int c=start;c<=stop;c++){int glyph;if(offset==0)glyph=(c+delta)&65535;else{int p=ranges+i*2+offset+(c-start)*2;if(p>end-2)throw new FormatException("font glyph bounds");glyph=U16(p);if(glyph!=0)glyph=(glyph+delta)&65535;}Add(c,glyph);}}}
  if(Glyphs.Count==0)throw new FormatException("empty font cmap");
 }
}
