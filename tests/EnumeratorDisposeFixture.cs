using System;
using System.Collections.Generic;
using System.Diagnostics;
class EnumeratorDisposeFixture {
 static readonly List<int> List=new List<int>{3,5,7};static int sink,checks;
 static void Need(bool value,string label){checks++;if(!value)throw new Exception(label);}
 static void RetainedLocals(){
  var list=List.GetEnumerator();Need(list.MoveNext()&&list.Current==3,"list first");((IDisposable)list).Dispose();Need(list.MoveNext()&&list.Current==5,"list local survives disposed copy");
  var set=new HashSet<int>{3,5,7}.GetEnumerator();set.MoveNext();int first=set.Current;((IDisposable)set).Dispose();Need(set.MoveNext()&&set.Current!=first,"set local survives disposed copy");
  var dict=new Dictionary<int,int>{{3,4},{5,6},{7,8}};var entries=dict.GetEnumerator();entries.MoveNext();first=entries.Current.Key;((IDisposable)entries).Dispose();Need(entries.MoveNext()&&entries.Current.Key!=first,"dictionary local survives disposed copy");
  var keys=dict.Keys.GetEnumerator();keys.MoveNext();first=keys.Current;((IDisposable)keys).Dispose();Need(keys.MoveNext()&&keys.Current!=first,"keys local survives disposed copy");
  var values=dict.Values.GetEnumerator();values.MoveNext();first=values.Current;((IDisposable)values).Dispose();Need(values.MoveNext()&&values.Current!=first,"values local survives disposed copy");
  var queue=new Queue<int>(List).GetEnumerator();queue.MoveNext();((IDisposable)queue).Dispose();Need(queue.MoveNext()&&queue.Current==5,"queue local survives disposed copy");
  var stack=new Stack<int>(List).GetEnumerator();stack.MoveNext();((IDisposable)stack).Dispose();Need(stack.MoveNext()&&stack.Current==5,"stack local survives disposed copy");
 }
 static int Nested(bool stop,bool fail){int sum=0;var outer=List.GetEnumerator();try{while(outer.MoveNext()){var inner=List.GetEnumerator();try{while(inner.MoveNext()){sum+=outer.Current*inner.Current;if(stop)return sum;if(fail)throw new InvalidOperationException("fixture");}}finally{((IDisposable)inner).Dispose();}}}finally{((IDisposable)outer).Dispose();}return sum;}
 static void Mutation(){var source=new List<int>{1,2,3};var e=source.GetEnumerator();bool threw=false;try{e.MoveNext();source.Add(4);try{e.MoveNext();}catch(InvalidOperationException){threw=true;}}finally{((IDisposable)e).Dispose();}Need(threw,"enumeration mutation exception preserved");}
 static void Defaults(){var e=default(List<int>.Enumerator);((IDisposable)e).Dispose();var empty=new HashSet<int>().GetEnumerator();try{Need(!empty.MoveNext(),"empty enumeration");}finally{((IDisposable)empty).Dispose();}Need(true,"default disposal");}
 static T Generic<T>(T first,T second){var e=new List<T>{first,second}.GetEnumerator();e.MoveNext();((IDisposable)e).Dispose();Need(e.MoveNext(),"generic local retained");return e.Current;}
 static void BoxedLoop(int count){for(int n=0;n<count;n++){var e=List.GetEnumerator();try{while(e.MoveNext())sink+=e.Current;}finally{((IDisposable)e).Dispose();}}}
 // Ineligible user structs must not silently be rewritten by the BCL-only pass.
 struct CustomEnumerator:IDisposable {internal static int Count;public void Dispose(){Count++;}}
 static void Custom(){var e=new CustomEnumerator();((IDisposable)e).Dispose();Need(CustomEnumerator.Count==1,"custom disposal retained");}
 static void Benchmark(string mode){
  var info=typeof(GC).GetMethod("GetAllocatedBytesForCurrentThread",Type.EmptyTypes);if(info==null){Console.WriteLine("Allocation counter unavailable");return;}
  var allocated=(Func<long>)Delegate.CreateDelegate(typeof(Func<long>),info);BoxedLoop(10000);const int count=250000;
  long start=allocated();var watch=Stopwatch.StartNew();BoxedLoop(count);watch.Stop();long bytes=allocated()-start;
  Console.WriteLine("mode="+mode+" iterations="+count+" bytes="+bytes+" elapsed_ms="+watch.Elapsed.TotalMilliseconds.ToString("F3"));
  Need(mode=="patched"?bytes<4096:bytes>=count*16L,"disposal allocation regression");
 }
 static void Main(string[] args){RetainedLocals();Defaults();Need(Generic(1,2)==2,"value generic");Need(Generic("a","b")=="b","reference generic");Need(Nested(false,false)==225,"nested order/content");Need(Nested(true,false)==9,"early return finally");bool threw=false;try{Nested(false,true);}catch(InvalidOperationException e){threw=e.Message=="fixture";}Need(threw,"exception preserved");Mutation();Custom();Console.WriteLine("PASS "+checks+" enumerator behavior contracts");if(args.Length>0)Benchmark(args[0]);GC.KeepAlive(sink);}
}
