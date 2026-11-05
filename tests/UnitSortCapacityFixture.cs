using System;using System.Collections.Generic;using UnityEngine;
class UnitManager{public int unitUID;public bool destroyed;public Action callback;public UnitManager(int id){unitUID=id;}}
class GameSpace {
 public List<string> trace=new List<string>();
 public void UnitsUpdate(){
  GameObject[] units=GameObject.FindGameObjectsWithTag("UnitTag");
  var ordered=new SortedList<int,UnitManager>();
  foreach(var go in units){var u=go.GetComponent<UnitManager>();ordered.Add(u.unitUID,u);}
  foreach(var item in ordered){var u=item.Value;if(!u.destroyed){trace.Add("update:"+item.Key+":"+u.unitUID);if(u.callback!=null)u.callback();}}
  foreach(var item in ordered){var u=item.Value;if(!u.destroyed)trace.Add("clear:"+item.Key+":"+u.unitUID);}
 }
}
class UnitSortCapacityFixture {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static void Reset(params UnitManager[] units){GameObject.Input=Array.ConvertAll(units,u=>new GameObject(u));}
 static void Throws<T>(Action action,string why)where T:Exception{bool yes=false;try{action();}catch(T){yes=true;}Need(yes,why);}
 static void Main(){
  foreach(int size in new[]{0,1,15,16,17,34,35,422,695,1000})foreach(int order in new[]{0,1,2}){
   var rng=new Random(451+size);var units=new UnitManager[size];for(int n=0;n<size;n++)units[n]=new UnitManager(n);
   if(order==1)Array.Reverse(units);if(order==2)for(int n=size-1;n>0;n--){int k=rng.Next(n+1);var t=units[k];units[k]=units[n];units[n]=t;}
   Reset(units);var g=new GameSpace();g.UnitsUpdate();Need(g.trace.Count==size*2,"both captured passes");for(int n=0;n<size;n++){Need(g.trace[n]=="update:"+n+":"+n,"original sorted updates");Need(g.trace[n+size]=="clear:"+n+":"+n,"original sorted clears");}
  }
  {var g=new GameSpace();var a=new UnitManager(2);var b=new UnitManager(9);Reset(b,a);a.callback=()=>{a.unitUID=200;b.unitUID=-1;Reset(new UnitManager(300));};g.UnitsUpdate();Need(String.Join(",",g.trace.ToArray())=="update:2:2,update:9:-1,clear:2:200,clear:9:-1","captured keys, references and membership");}
  {var g=new GameSpace();var a=new UnitManager(2);var b=new UnitManager(9);Reset(b,a);a.callback=()=>b.destroyed=true;g.UnitsUpdate();Need(String.Join(",",g.trace.ToArray())=="update:2:2,clear:2:2","existing destruction filters");}
  {var outer=new GameSpace();var nested=new GameSpace();var a=new UnitManager(2);Reset(a);a.callback=()=>{Reset(new UnitManager(4));nested.UnitsUpdate();};outer.UnitsUpdate();Need(outer.trace.Count==2&&nested.trace.Count==2,"independent reentrant tables");}
  {var g=new GameSpace();var a=new UnitManager(2);a.callback=()=>{throw new InvalidOperationException();};Reset(a);Throws<InvalidOperationException>(()=>g.UnitsUpdate(),"callback exception");Need(g.trace.Count==1,"no second pass after throw");}
  {var g=new GameSpace();Reset(new UnitManager(4),new UnitManager(4));Throws<ArgumentException>(()=>g.UnitsUpdate(),"duplicate UID");Need(g.trace.Count==0,"duplicate rejected before callbacks");}
  {var g=new GameSpace();Reset((UnitManager)null);Throws<NullReferenceException>(()=>g.UnitsUpdate(),"missing component");Need(g.trace.Count==0,"missing rejected before callbacks");}
  {var g=new GameSpace();Reset(new UnitManager(4),new UnitManager(4),null);Throws<ArgumentException>(()=>g.UnitsUpdate(),"duplicate precedes later missing component");}
  {var g=new GameSpace();GameObject.Input=null;Throws<NullReferenceException>(()=>g.UnitsUpdate(),"null discovery fixture");}
  {var g=new GameSpace();GameObject.Input=new GameObject[]{null};Throws<NullReferenceException>(()=>g.UnitsUpdate(),"null game object fixture");}
  Console.WriteLine("Unit capacity behavior checks="+checks);
 }
}
