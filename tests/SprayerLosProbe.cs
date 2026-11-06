using System;using System.Linq;
// These are data-only identities for the copied query/LOS bodies, not a mock
// of their decisions. Only RANGE is supplied: production leaves its getter intact.
public class GameSpace {public static GameSpace instance;public static int GAMESPACE_WIDTH,GAMESPACE_HEIGHT;public Terrain terrain;public Digitalis digitalis;public CreeperSimulation creeperSimulation;}
public class Terrain {public int[] terrain,walls;public MapData[] mapData;public struct MapData {public int GetFauxHeight(){throw new Exception("Unused faux-height branch reached");}}}
public class Digitalis {public int[] digitalisData;}
public class CreeperSimulation {public int[] data;}
public class SprayerBarrelManager {public int range;public int RANGE {get{return range;}}}
public static class SprayerQueries {
 public static void Original(SprayerBarrelManager self,int x,int y,ref int cx,ref int cy,ref int dx,ref int dy,ref float cd,ref float dd){throw new Exception("Copy original IL");}
 public static void Candidate(SprayerBarrelManager self,int x,int y,ref int cx,ref int cy,ref int dx,ref int dy,ref float cd,ref float dd){throw new Exception("Copy patched IL");}
}
public class Util {
 public static bool hasLOS(int a,int b,int c,int d,bool e,bool f){throw new Exception("Copy original IL");}
 public static bool hasLOS(int a,int b,int c,int d,bool e,bool f,bool g){throw new Exception("Copy original IL");}
 public static bool hasLOS(int a,int b,int c,int d,bool e,bool f,bool g,bool h,bool i){throw new Exception("Copy original IL");}
 public static bool heightOK(int a,int b,int c,int d,double e,bool f,bool g){throw new Exception("Copy original IL");}
}
class SprayerLosProbe {
 static int checks;static void Need(bool value,string why){checks++;if(!value)throw new Exception(why);}
 static int Bits(float f){return BitConverter.ToInt32(BitConverter.GetBytes(f),0);}
 static int[] Query(int x,int y,int range,bool candidate){int cx=-9,cy=-9,dx=-9,dy=-9;float cd=-9,dd=-9;var b=new SprayerBarrelManager{range=range};if(candidate)SprayerQueries.Candidate(b,x,y,ref cx,ref cy,ref dx,ref dy,ref cd,ref dd);else SprayerQueries.Original(b,x,y,ref cx,ref cy,ref dx,ref dy,ref cd,ref dd);return new[]{cx,cy,dx,dy,Bits(cd),Bits(dd)};}
 static GameSpace Setup(int w,int h){GameSpace.GAMESPACE_WIDTH=w;GameSpace.GAMESPACE_HEIGHT=h;return GameSpace.instance=new GameSpace{terrain=new Terrain{terrain=new int[w*h],walls=new int[w*h]},digitalis=new Digitalis{digitalisData=new int[w*h]},creeperSimulation=new CreeperSimulation{data=new int[w*h]}};}
 static void Main(){
  // Creeper blocking must not discard the independent Digitalis target. The
  // scan reaches x=2 before the nearer Creeper at x=5, so both goals can improve.
  var g=Setup(7,3);g.creeperSimulation.data[5+7]=1;g.creeperSimulation.data[2+7]=1;g.digitalis.digitalisData[2+7]=1;
  var expected=new[]{5,1,2,1,Bits(1f),Bits(16f)};Need(Query(6,1,6,false).SequenceEqual(expected),"original independent targets");Need(Query(6,1,6,true).SequenceEqual(expected),"Digitalis survives Creeper-blocking LOS");
  int queries=0;
  for(int mode=0;mode<8;mode++){
   const int w=17,h=15;g=Setup(w,h);
   for(int y=0;y<h;y++)for(int x=0;x<w;x++){
    int i=x+y*w;g.terrain.terrain[i]=mode==3?(x<8?0:5):mode==4?(x+y)%3:mode==5?((x+y)%7==0?500:0):0;
    g.terrain.walls[i]=mode==6&&x==8?1:0;
    g.creeperSimulation.data[i]=mode==0?0:mode==1||mode==2?1:(x*13+y*7)%4==0?10:((x+y)%5==0?-5:0);
    g.digitalis.digitalisData[i]=mode==2||mode==4||mode==5||mode==7?((x+y)%3==0?100:0):0;
   }
   var arrays=new[]{g.terrain.terrain,g.terrain.walls,g.creeperSimulation.data,g.digitalis.digitalisData};var kept=arrays.Select(a=>(int[])a.Clone()).ToArray();
   foreach(int range in new[]{0,3,7,13})foreach(int x in new[]{0,8,16})foreach(int y in new[]{0,7,14}){Need(Query(x,y,range,false).SequenceEqual(Query(x,y,range,true)),"query targets/distance bits mode="+mode+" range="+range+" origin="+x+","+y);queries++;}
   for(int n=0;n<arrays.Length;n++)Need(arrays[n].SequenceEqual(kept[n]),"query changed map data");
  }
  Console.WriteLine("Sprayer LOS exact-IL behavior: "+queries+" mixed-terrain/range/edge queries, independent Digitalis target and unchanged maps; checks="+checks);
 }
}
