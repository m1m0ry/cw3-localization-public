using System;
using System.Collections;

// Script source strings are immutable. Cache by reference, not script name, so
// edits/replacements are never confused with the prior source. Weak owners keep
// unloaded scripts/command graphs collectible; ordinal storage is strictly bounded.
internal sealed class ScriptContextCache {
 internal const int HashCapacity=16,OrdinalCapacity=8,OrdinalBudget=32768,MaxCommands=16384;
 sealed class HashEntry {internal WeakReference Source;internal string Value;}
 sealed class OrdinalEntry {internal WeakReference Commands;internal string Hash;internal int[] Values;}
 readonly HashEntry[] hashes=new HashEntry[HashCapacity];
 readonly OrdinalEntry[] ordinals=new OrdinalEntry[OrdinalCapacity];
 readonly Func<string,string> digest;readonly Func<object,int> statement;
 int hashCount,ordinalCount,ordinalItems;
 internal ScriptContextCache(Func<string,string> digest,Func<object,int> statement){this.digest=digest;this.statement=statement;}
 static void Recent<T>(T[] entries,int index){T value=entries[index];for(int i=index;i>0;i--)entries[i]=entries[i-1];entries[0]=value;}
 internal string Hash(string source){
  if(source==null)return null;
  for(int i=0;i<hashCount;i++)if(Object.ReferenceEquals(hashes[i].Source.Target,source)){Recent(hashes,i);return hashes[0].Value;}
  string value=digest(source); // Publish only after successful hashing.
  HashEntry entry;
  if(hashCount<HashCapacity){entry=new HashEntry{Source=new WeakReference(source)};hashes[hashCount++]=entry;}
  else{entry=hashes[hashCount-1];entry.Source.Target=source;}
  entry.Value=value;Recent(hashes,hashCount-1);return value;
 }
 void RemoveOrdinal(int at){ordinalItems-=ordinals[at].Values.Length;for(int i=at;i<ordinalCount-1;i++)ordinals[i]=ordinals[i+1];ordinals[--ordinalCount]=null;}
 internal int[] Ordinals(IList commands,string sourceHash){
  if(commands==null)throw new ArgumentNullException("commands");int count=commands.Count;
  if(count>MaxCommands)throw new ArgumentOutOfRangeException("commands","Script command limit");
  for(int i=0;i<ordinalCount;i++){
   object owner=ordinals[i].Commands.Target;
   if(owner==null){RemoveOrdinal(i--);continue;}
   if(!Object.ReferenceEquals(owner,commands))continue;
   if(ordinals[i].Values.Length==count&&ordinals[i].Hash==sourceHash){Recent(ordinals,i);return ordinals[0].Values;}
   RemoveOrdinal(i);break;
  }
  var values=new int[count];int ordinal=-1;
  for(int i=0;i<count;i++){int kind=statement(commands[i]);bool output=kind==291||kind==292;if(output)ordinal++;values[i]=output?ordinal:-1;}
  while(ordinalCount>0&&(ordinalCount==OrdinalCapacity||ordinalItems+count>OrdinalBudget))RemoveOrdinal(ordinalCount-1);
  ordinals[ordinalCount++]=new OrdinalEntry{Commands=new WeakReference(commands),Hash=sourceHash,Values=values};ordinalItems+=count;Recent(ordinals,ordinalCount-1);return values;
 }
 internal void Clear(){Array.Clear(hashes,0,hashes.Length);Array.Clear(ordinals,0,ordinals.Length);hashCount=ordinalCount=ordinalItems=0;}
 internal int RetainedOrdinals{get{return ordinalItems;}}
}
