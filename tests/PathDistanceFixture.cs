using System;using System.Diagnostics;using UnityEngine;
class UnitManager:Component {}
class Path {
 public int mode;public UnitManager startUnit,endUnit;public float startX,startY,endX,endY;
 public float GetDistance(){float x,y;if(mode==1){x=endUnit.transform.localPosition.x-startX;y=endUnit.transform.localPosition.y-startY;}else if(mode==2){x=endX-startX;y=endY-startY;}else{x=endUnit.transform.localPosition.x-startUnit.transform.localPosition.x;y=endUnit.transform.localPosition.y-startUnit.transform.localPosition.y;}return Mathf.Sqrt(x*x+y*y);}
}
class PathDistanceFixture {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static int Bits(float x){return BitConverter.ToInt32(BitConverter.GetBytes(x),0);}
 static UnitManager Unit(string name,float x,float y){return new UnitManager{name=name,target=new Transform{name=name,value=new Vector3(x,y,913)}};}
 static Path Make(int mode){return new Path{mode=mode,startUnit=Unit("start",2,3),endUnit=Unit("end",5,7),startX=2,startY=3,endX=5,endY=7};}
 static void Throws<T>(Action f,string why)where T:Exception{bool ok=false;try{f();}catch(T){ok=true;}Need(ok,why);}
 static void Main(string[] a){
  bool patched=a.Length>0&&a[0]=="patched";
  if(a.Length>1&&a[1]=="bench"){
   Component.trace=null;var p=Make(0);double sink=0;for(int j=0;j<10000;j++)sink+=p.GetDistance();var timer=Stopwatch.StartNew();for(int j=0;j<1000000;j++)sink+=p.GetDistance();timer.Stop();Console.WriteLine("managed_fixture_only="+a[0]+" iterations=1000000 ms="+timer.Elapsed.TotalMilliseconds.ToString("F3",System.Globalization.CultureInfo.InvariantCulture)+" checksum="+sink);return;
  }
  foreach(int mode in new[]{0,1,2,3,-1}){
   var p=Make(mode);Component.trace="";Need(p.GetDistance()==5,"3-4-5 path all branches");
   int each=patched?1:2;Need(p.endUnit.reads==(mode==2?0:each)&&p.endUnit.target.reads==(mode==2?0:each),"one endpoint snapshot per call");Need(p.startUnit.reads==((mode==1||mode==2)?0:each),"preserve mode-specific endpoint access");
   string prefix=mode==2?"":"transform:end,position:end,";if(mode!=1&&mode!=2)prefix+="transform:start,position:start,";Need(Component.trace.StartsWith(prefix),"first native-access order preserved");
   p.endUnit.target.value=new Vector3(8,11,0);p.endX=8;p.endY=11;Need(p.GetDistance()==10,"movement visible next call");
   p.startX=8;p.startY=11;p.startUnit=Unit("new-start",8,11);Need(p.GetDistance()==0,"changed endpoint and coordinates visible next call");
  }
  Component.trace=null;
  foreach(float x in new[]{0f,-0f,0.125f,-1.75f,1e-20f,1e20f,float.NaN,float.PositiveInfinity,float.NegativeInfinity})foreach(float y in new[]{0f,-0f,0.375f,-2.25f,1e-20f,1e20f,float.NaN,float.PositiveInfinity,float.NegativeInfinity})foreach(int mode in new[]{0,1,2}){
   var p=Make(mode);p.endUnit.target.value=new Vector3(x,y,0);p.endX=x;p.endY=y;float dx=x-2f,dy=y-3f;float expected=Mathf.Sqrt(dx*dx+dy*dy),actual=p.GetDistance();Need(Bits(actual)==Bits(expected),"identical float operation result");
  }
  {var p=Make(2);p.startUnit=null;p.endUnit=null;Need(p.GetDistance()==5,"fixed coordinates do not dereference endpoints");}
  {var p=Make(1);p.startUnit=null;Need(p.GetDistance()==5,"mode one does not dereference start");}
  {var p=Make(0);p.endUnit=null;Component.trace="";Throws<NullReferenceException>(()=>p.GetDistance(),"null end");Need(Component.trace=="","null end occurs before start access");}
  {var p=Make(0);p.startUnit=null;Component.trace="";Throws<NullReferenceException>(()=>p.GetDistance(),"null start");Need(Component.trace=="transform:end,position:end,","end position is read before null start");}
  {var p=Make(0);p.endUnit.fail=true;Component.trace="";Throws<InvalidOperationException>(()=>p.GetDistance(),"destroyed end transform");Need(Component.trace=="transform:end,","no later getters after failing first transform");}
  {var p=Make(0);p.startUnit.target.fail=true;Component.trace="";Throws<InvalidOperationException>(()=>p.GetDistance(),"destroyed start position");Need(Component.trace=="transform:end,position:end,transform:start,position:start,","first-access exception ordering");}
  {var p=Make(0);p.endUnit.target=null;Throws<NullReferenceException>(()=>p.GetDistance(),"missing transform");}
  Console.WriteLine("Path distance behavior checks="+checks+" mode="+(patched?"patched":"original"));
 }
}
