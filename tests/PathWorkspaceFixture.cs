using System;using System.Reflection;
class Terrain {public int[] mapData=new int[256];}
class GameSpace {public static GameSpace instance=new GameSpace();public Terrain terrain=new Terrain();public static int GAMESPACE_WIDTH=16,GAMESPACE_HEIGHT=16;}
class CrplCore {}
class PathWorkspaceFixture {
 static int checks;static BindingFlags F=BindingFlags.Static|BindingFlags.NonPublic;
 static void Need(bool ok,string name){checks++;if(!ok)throw new Exception(name);}
 static float[][] Borrow(int start,int end){return (float[][])typeof(CrplCore).GetMethod("__cw3PathBorrow",F).Invoke(null,new object[]{start,end});}
 static void Return(float[][] lease){typeof(CrplCore).GetMethod("__cw3PathRelease",F).Invoke(null,new object[]{lease});}
 static bool Busy(){return (bool)typeof(CrplCore).GetField("__cw3PathBusy",F).GetValue(null);}
 static void Main(){
  Return(null);Need(!Busy(),"null no owner");var a=Borrow(0,255);Need(a.Length==3&&a[0]!=a[1]&&a[1]!=a[2]&&a[0].Length==256,"three bounded vectors");a[0][7]=123;a[1][7]=Single.NaN;a[2][7]=Single.PositiveInfinity;
  Need(Borrow(0,255)==null,"busy fallback to original");Return(null);Return(new float[3][]);Need(Busy(),"null/foreign do not release owner");Return(a);Need(!Busy(),"normal unlock");var b=Borrow(0,255);Need(Object.ReferenceEquals(a,b)&&b[0][7]==123&&Single.IsNaN(b[1][7])&&Single.IsPositiveInfinity(b[2][7]),"primitive contents deliberately not cleared");Return(b);
  foreach(int n in new[]{-1,256,Int32.MaxValue}){Need(Borrow(n,0)==null&&!Busy(),"invalid start fallback");Need(Borrow(0,n)==null&&!Busy(),"invalid end fallback");}Need(Borrow(5,5)==null,"no-op path does not allocate workspace");
  GameSpace.GAMESPACE_WIDTH=0;Need(Borrow(0,5)==null,"zero width");GameSpace.GAMESPACE_WIDTH=16;GameSpace.GAMESPACE_HEIGHT=0;Need(Borrow(0,5)==null,"zero height");GameSpace.GAMESPACE_HEIGHT=15;Need(Borrow(0,5)==null,"mismatched dimensions");GameSpace.GAMESPACE_WIDTH=65536;GameSpace.GAMESPACE_HEIGHT=65536;Need(Borrow(0,5)==null,"overflow product rejected");
  GameSpace.GAMESPACE_WIDTH=256;GameSpace.GAMESPACE_HEIGHT=256;GameSpace.instance.terrain.mapData=new int[65536];a=Borrow(0,65535);Need(a[0].Length==65536&&a[1].Length==65536&&a[2].Length==65536,"maximum budget");Return(a);
  GameSpace.GAMESPACE_WIDTH=257;GameSpace.GAMESPACE_HEIGHT=256;GameSpace.instance.terrain.mapData=new int[65792];Need(Borrow(0,1)==null,"over budget fallback");GameSpace.instance.terrain.mapData=null;Need(Borrow(0,1)==null,"null map fallback");
  GameSpace.GAMESPACE_WIDTH=16;GameSpace.GAMESPACE_HEIGHT=16;GameSpace.instance.terrain.mapData=new int[256];b=Borrow(0,255);Need(Object.ReferenceEquals(a,b),"large-to-small reuses without clearing");try{throw new InvalidOperationException();}catch(InvalidOperationException){}finally{Return(b);}Need(!Busy(),"exceptional caller releases");Return(b);Need(!Busy(),"duplicate completed return harmless");
  Console.WriteLine("Path workspace helper checks="+checks+" runtime="+Environment.Version);
 }
}
