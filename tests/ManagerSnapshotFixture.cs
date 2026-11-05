using System;using System.Collections.Generic;using System.Reflection;using System.Diagnostics;
class Unit {internal int Id;internal bool destroyed;internal Action Tick;internal virtual void GameUpdate(){if(Tick!=null)Tick();}}
class PacketManager:Unit {internal new bool destroyed;internal new void GameUpdate(){base.GameUpdate();}} class MistManager:Unit {internal new void GameUpdate(){base.GameUpdate();}} class EffectManager:Unit {
 internal new void GameUpdate(){base.GameUpdate();}
 internal static MultiManagerPool<EffectManager> effectPool;
 internal static void EffectsUpdate(){if(effectPool==null)return;EffectManager[] xs=effectPool.GetActiveManagers();foreach(var x in xs)x.GameUpdate();}
}
class ManagerPool<T> where T:Unit {
 internal HashSet<T> activeManagers=new HashSet<T>();
 public T[] GetActiveManagers(){var xs=new T[activeManagers.Count];activeManagers.CopyTo(xs);return xs;}
}
class MultiManagerPool<T> where T:Unit {
 internal HashSet<T> activeManagers=new HashSet<T>();
 public T[] GetActiveManagers(){var xs=new T[activeManagers.Count];activeManagers.CopyTo(xs);return xs;}
}
class GameSpace {
 internal ManagerPool<PacketManager> packetPool=new ManagerPool<PacketManager>(),packetOrePool=new ManagerPool<PacketManager>(),packetACPool=new ManagerPool<PacketManager>();internal ManagerPool<MistManager> mistPool=new ManagerPool<MistManager>();
 internal void PacketsUpdate(){PacketManager[] xs=packetPool.GetActiveManagers();foreach(var x in xs)if(!x.destroyed)x.GameUpdate();xs=packetOrePool.GetActiveManagers();foreach(var x in xs)if(!x.destroyed)x.GameUpdate();xs=packetACPool.GetActiveManagers();foreach(var x in xs)if(!x.destroyed)x.GameUpdate();}
 internal void MistUpdate(){MistManager[] xs=mistPool.GetActiveManagers();foreach(var x in xs)x.GameUpdate();}
}
class ManagerSnapshotFixture {
 static int checks;static bool patched;static List<string> trace=new List<string>();static void Need(bool b,string s){checks++;if(!b)throw new Exception(s);}
 static void ClearReference(){Array.Clear(new object[0],0,0);}
 static object Field(object p,string n){return p.GetType().GetField("__cw3Snapshot"+n,BindingFlags.Instance|BindingFlags.NonPublic).GetValue(p);}
 static void Released(object p){if(!patched)return;Need(!(bool)Field(p,"Busy"),"busy cleared");var a=Field(p,"Buffer") as Array;if(a!=null)foreach(var x in a)Need(x==null,"all returned slots clear");}
 static PacketManager Packet(int n,Action action=null){return new PacketManager{Id=n,Tick=action??(()=>trace.Add(n.ToString()))};}
 static void Trace(string s){Need(String.Join(",",trace.ToArray())==s,"trace "+s+" actual "+String.Join(",",trace.ToArray()));trace.Clear();}
 static void Behavior(){
 var g=new GameSpace();g.PacketsUpdate();g.MistUpdate();EffectManager.effectPool=null;EffectManager.EffectsUpdate();Need(true,"empty/null pools");
 var a=Packet(1);var b=Packet(2);var c=Packet(3);g.packetPool.activeManagers.Add(a);g.packetPool.activeManagers.Add(b);
 // Public snapshots retain independent array ownership.
 var old=g.packetPool.GetActiveManagers();old[0]=c;Need(g.packetPool.GetActiveManagers()[0]==a,"public owned array unchanged");
 a.Tick=()=>{trace.Add("1");g.packetPool.activeManagers.Remove(b);g.packetPool.activeManagers.Add(c);};g.PacketsUpdate();Trace("1,2");Released(g.packetPool);
 a.Tick=()=>trace.Add("1");g.PacketsUpdate();Trace("1,3");
 // ABA reference reuse: the old snapshot still sees the reference's new state.
 g.packetPool.activeManagers.Remove(c);g.packetPool.activeManagers.Add(b);a.Tick=()=>{trace.Add("1");g.packetPool.activeManagers.Remove(b);b.Tick=()=>trace.Add("reused");g.packetPool.activeManagers.Add(b);};g.PacketsUpdate();Trace("1,reused");
 // Same-pool reentry gets an independent snapshot without clearing outer slots.
 bool inside=false;a.Tick=()=>{trace.Add(inside?"inner1":"outer1");if(!inside){inside=true;g.PacketsUpdate();inside=false;}};b.Tick=()=>trace.Add(inside?"inner2":"outer2");g.PacketsUpdate();Trace("outer1,inner1,inner2,outer2");Released(g.packetPool);
 // Each later pool is captured only at its own loop start.
 g=new GameSpace();var late=Packet(7);g.packetPool.activeManagers.Add(Packet(4,()=>{trace.Add("4");g.packetOrePool.activeManagers.Add(late);}));g.packetACPool.activeManagers.Add(Packet(8));g.PacketsUpdate();Trace("4,7,8");
 // Captured owner survives replacement of a game field in callback.
 var previous=g.packetPool;previous.activeManagers.Clear();previous.activeManagers.Add(Packet(5,()=>{trace.Add("5");g.packetPool=new ManagerPool<PacketManager>();}));g.PacketsUpdate();Trace("5,7,8");Released(previous);
 // Exception returns the rental; later updates remain valid.
 g=new GameSpace();a=Packet(1,()=>{throw new InvalidOperationException("expected");});g.packetPool.activeManagers.Add(a);bool failed=false;try{g.PacketsUpdate();}catch(InvalidOperationException){failed=true;}Need(failed,"callback exception preserved");Released(g.packetPool);a.Tick=()=>trace.Add("after");g.PacketsUpdate();Trace("after");
 // Original Packet destroyed gate, no new gates for Mist or Effect.
 g.packetPool.activeManagers.Add(new PacketManager{destroyed=true,Tick=()=>{throw new Exception("destroyed packet");}});g.PacketsUpdate();Trace("after");
 g.mistPool.activeManagers.Add(new MistManager{destroyed=true,Tick=()=>trace.Add("mist")});g.MistUpdate();Trace("mist");Released(g.mistPool);
 var effect=new MultiManagerPool<EffectManager>();EffectManager.effectPool=effect;effect.activeManagers.Add(new EffectManager{destroyed=true,Tick=()=>{trace.Add("effect");EffectManager.effectPool=null;}});EffectManager.EffectsUpdate();Trace("effect");Released(effect);
 // Capacity bound and shrink: retained high-water array never retains objects.
 g=new GameSpace();for(int i=0;i<17000;i++)g.packetPool.activeManagers.Add(new PacketManager());g.PacketsUpdate();if(patched)Need(Field(g.packetPool,"Buffer")==null,"oversized fallback not retained");g.packetPool.activeManagers.Clear();g.packetPool.activeManagers.Add(new PacketManager());g.PacketsUpdate();Released(g.packetPool);if(patched)Need(((Array)Field(g.packetPool,"Buffer")).Length<=16384,"bounded capacity");
 }
 static void InternalContracts(){if(!patched)return;
 var pool=new ManagerPool<PacketManager>();var t=pool.GetType();var acquire=t.GetMethod("__cw3SnapshotBorrow",BindingFlags.Instance|BindingFlags.NonPublic);var release=t.GetMethod("__cw3SnapshotRelease",BindingFlags.Instance|BindingFlags.NonPublic);var first=Packet(1);pool.activeManagers.Add(first);object[] args={0};var outer=(PacketManager[])acquire.Invoke(pool,args);int count=(int)args[0];Need(count==1&&outer[0]==first,"acquired prefix");var nested=(PacketManager[])acquire.Invoke(pool,args);Need(!Object.ReferenceEquals(outer,nested),"nested independent");release.Invoke(pool,new object[]{nested,1});Need((bool)Field(pool,"Busy")&&outer[0]==first,"fallback return leaves outer busy/intact");pool.activeManagers.Clear();Need(acquire.Invoke(pool,args)==null&&(int)args[0]==0,"empty nested capture");release.Invoke(pool,new object[]{null,0});Need((bool)Field(pool,"Busy"),"empty return does not unlock outer");release.Invoke(pool,new object[]{outer,count});Released(pool);
 for(int i=0;i<16384;i++)pool.activeManagers.Add(new PacketManager());outer=(PacketManager[])acquire.Invoke(pool,args);Need(outer.Length==16384&&(int)args[0]==16384,"exact upper bound");release.Invoke(pool,new object[]{outer,16384});pool.activeManagers.Add(new PacketManager());var oversized=(PacketManager[])acquire.Invoke(pool,args);Need(oversized.Length==16385&&!Object.ReferenceEquals(outer,oversized)&&!(bool)Field(pool,"Busy"),"over-limit independent fallback");release.Invoke(pool,new object[]{oversized,16385});pool.activeManagers.Clear();pool.activeManagers.Add(first);var small=(PacketManager[])acquire.Invoke(pool,args);Need(Object.ReferenceEquals(small,outer)&&(int)args[0]==1,"reuse high-water with captured count");release.Invoke(pool,new object[]{small,1});Need(Array.TrueForAll(small,x=>x==null),"high-water tail remains clear");
 var g=new GameSpace();g.packetPool.activeManagers.Add(new PacketManager());g.packetOrePool=null;bool failed=false;try{g.PacketsUpdate();}catch(NullReferenceException){failed=true;}Need(failed,"second acquisition failure preserved");Released(g.packetPool);
 }
 static void CopyFault(){var g=new GameSpace();g.packetPool.activeManagers.Add(new PacketManager());bool failed=false;try{g.PacketsUpdate();}catch(InvalidOperationException){failed=true;}Need(failed,"copy exception preserved");Released(g.packetPool);Console.WriteLine("PASS "+checks+" populated-copy fault cleanup checks");}
 static void Workload(){var method=typeof(GC).GetMethod("GetAllocatedBytesForCurrentThread");if(method==null){Console.WriteLine("Allocation API unavailable");return;}var bytes=(Func<long>)Delegate.CreateDelegate(typeof(Func<long>),method);var g=new GameSpace();var all=new List<PacketManager>();for(int i=0;i<256;i++){var p=new PacketManager();all.Add(p);g.packetPool.activeManagers.Add(p);}for(int i=0;i<20;i++)g.PacketsUpdate();var watch=new Stopwatch();long before=bytes();watch.Start();for(int i=0;i<10000;i++){var p=all[i%all.Count];g.packetPool.activeManagers.Remove(p);g.packetPool.activeManagers.Add(p);g.PacketsUpdate();}watch.Stop();long amount=bytes()-before;Console.WriteLine("WORKLOAD turnover 256 packets x10000 updates: bytes="+amount+" elapsed_ms="+watch.Elapsed.TotalMilliseconds+" (host synthetic, not game FPS)");if(patched)Need(amount<2048,"steady-state snapshot allocation removed");else Need(amount>20000000,"original arrays observed");}
 static void Main(string[] args){patched=args.Length>0&&args[0]!="original";if(args.Length>0&&args[0]=="copyfault"){CopyFault();return;}ClearReference();Behavior();InternalContracts();Workload();Console.WriteLine("PASS "+checks+" snapshot behavior checks "+(patched?"patched":"original"));}
}
