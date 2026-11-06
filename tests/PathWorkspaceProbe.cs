using System;using System.Collections.Generic;using System.Linq;using System.Reflection;using System.Runtime.Serialization;using System.Diagnostics;
class PathWorkspaceProbe {
 delegate Dictionary<int,int> Find(int start,int end,int min,int max,bool avoid,bool full);
 static BindingFlags F=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance;
 static Type core,space,terrain,cell;static object gs,ter,runner;static Find find;static int width;
 static void Set(Type t,object obj,string name,object value){t.GetField(name,F).SetValue(obj,value);}
 static object Get(Type t,object obj,string name){return t.GetField(name,F).GetValue(obj);}
 static string Map(Dictionary<int,int> d){return d==null?"null":String.Join(",",d.OrderBy(x=>x.Key).Select(x=>x.Key+":"+x.Value).ToArray());}
 static void Setup(int w,int seed,bool barrier){width=w;Set(space,null,"GAMESPACE_WIDTH",w);Set(space,null,"GAMESPACE_HEIGHT",w);var data=Array.CreateInstance(cell,w*w);var occupied=new int[w*w];var random=new Random(seed);for(int i=0;i<data.Length;i++){object c=Activator.CreateInstance(cell);int h=barrier&&i%w==w/2?10:seed==0?0:random.Next(0,6);Set(cell,c,"height",h);Set(cell,c,"height2",seed==0||random.Next(4)!=0?-1:h+1);Set(cell,c,"shape",0);data.SetValue(c,i);occupied[i]=seed==0?0:random.Next(5)==0?1:0;}Set(terrain,ter,"mapData",data);Set(space,gs,"occupiedMap",occupied);}
 static void Need(bool value,string why){if(!value)throw new Exception(why);}
 static void Main(string[] a){
  AppDomain.CurrentDomain.AssemblyResolve+=(sender,ev)=>{string name=new AssemblyName(ev.Name).Name;if(name=="System")return typeof(Uri).Assembly;if(name=="System.Xml")return typeof(System.Xml.XmlWriter).Assembly;if(name=="System.Core")return typeof(HashSet<int>).Assembly;if(name=="mscorlib")return typeof(object).Assembly;return null;};Assembly.LoadFile(a[1]);
  // Only the source-built UI type fixture beside this probe, not an unpinned
  // firstpass DLL from the game input directory. Search IL remains untouched.
  Assembly.LoadFile(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(typeof(PathWorkspaceProbe).Assembly.Location),"Assembly-CSharp-firstpass.dll"));var asm=Assembly.LoadFile(System.IO.Path.GetFullPath(a[0]));core=asm.GetType("CrplCore");space=asm.GetType("GameSpace");terrain=asm.GetType("Terrain");cell=asm.GetType("Terrain+MapData");gs=FormatterServices.GetUninitializedObject(space);ter=FormatterServices.GetUninitializedObject(terrain);runner=FormatterServices.GetUninitializedObject(core);Set(space,null,"instance",gs);Set(space,gs,"terrain",ter);Set(core,null,"openHashSet",new HashSet<int>());Set(core,null,"closedHashSet",new HashSet<int>());var unit=asm.GetType("UnitManager");object baseUnit=FormatterServices.GetUninitializedObject(unit);Set(unit,baseUnit,"footprintDeployedX",-1);Set(core,runner,"baseUnit",baseUnit);find=(Find)Delegate.CreateDelegate(typeof(Find),runner,core.GetMethod("PathFindTerrain",F));
  if(a.Length>2&&a[2]=="bench"){
   foreach(string kind in new[]{"small","large","large_then_small"}){
    Setup(kind=="small"?16:128,0,kind!="small");find(0,width*width-1,0,1,false,true);
    if(kind=="large_then_small")Setup(16,0,false);
    int repeats=kind=="large"?20:1000;GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();long heap=GC.GetTotalMemory(false);int gc0=GC.CollectionCount(0);var watch=Stopwatch.StartNew();for(int n=0;n<repeats;n++)find(0,width*width-1,0,1,false,true);watch.Stop();
    Console.WriteLine(kind+" calls="+repeats+" ms="+watch.Elapsed.TotalMilliseconds.ToString("F3")+" gc0="+(GC.CollectionCount(0)-gc0)+" heap_delta="+(GC.GetTotalMemory(false)-heap)+" runtime="+Environment.Version);
   }return;
  }
  int cases=0;for(int seed=0;seed<12;seed++){Setup(16,seed,false);for(int flags=0;flags<4;flags++){int start=seed*7,end=255-seed*5;var d=find(start,end,seed%3,seed%3+3,(flags&1)!=0,(flags&2)!=0);string kept=Map(d);find(end,start,0,5,false,false);Need(Map(d)==kept,"returned map modified");Console.WriteLine("case="+(cases++)+" "+kept);}}
  Setup(128,0,true);Need(find(0,16383,0,1,false,true)==null,"unreachable");Setup(16,0,false);Need(find(5,5,0,1,false,true).Count==0,"same cell");var first=find(0,255,0,1,false,true);Need(!Object.ReferenceEquals(first,find(0,255,0,1,false,true)),"independent result");
  Set(space,gs,"terrain",null);try{find(0,255,0,1,false,true);throw new Exception("expected pre-acquire exception");}catch(NullReferenceException){}Set(space,gs,"terrain",ter);Set(space,null,"GAMESPACE_WIDTH",0);try{find(0,255,0,1,false,true);throw new Exception("expected acquired exception");}catch(DivideByZeroException){}Set(space,null,"GAMESPACE_WIDTH",16);
  if(core.GetField("__cw3PathBusy",F)!=null){Need(!(bool)Get(core,null,"__cw3PathBusy"),"exception releases lease");}
  Set(core,runner,"baseUnit",null);try{find(0,255,0,1,true,true);throw new Exception("expected dense exception");}catch(NullReferenceException){}Set(core,runner,"baseUnit",baseUnit);if(core.GetField("__cw3PathBusy",F)!=null)Need(!(bool)Get(core,null,"__cw3PathBusy"),"dense finally releases");
  foreach(int invalid in new[]{-1,256}){try{Console.WriteLine("invalid-start="+invalid+" "+Map(find(invalid,255,0,1,false,true)));}catch(Exception e){Console.WriteLine("invalid-start="+invalid+" "+e.GetType().Name);}try{Console.WriteLine("invalid-end="+invalid+" "+Map(find(0,invalid,0,1,false,true)));}catch(Exception e){Console.WriteLine("invalid-end="+invalid+" "+e.GetType().Name);}}
  Set(terrain,ter,"mapData",null);Need(find(5,5,0,1,false,true).Count==0,"null map same-cell original semantics");Setup(16,0,false);
  if(core.GetField("__cw3PathCache",F)!=null){var scores=(float[][])Get(core,null,"__cw3PathCache");foreach(var score in scores)for(int i=0;i<score.Length;i++)score[i]=i%2==0?Single.NaN:Single.PositiveInfinity;}
  Need(Map(first)==Map(find(0,255,0,1,false,true)),"poisoned-cache and exception recovery");Console.WriteLine("cases="+cases+" success/no-path/same-cell/retained-result/exception recovery passed runtime="+Environment.Version);
 }
}
