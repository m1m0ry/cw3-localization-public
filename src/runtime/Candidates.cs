using System;using System.IO;using System.Text;using System.Collections.Generic;using System.Diagnostics;using System.Security.Cryptography;using System.Text.RegularExpressions;using System.Threading;
// Local, opt-in observations of existing display boundaries. Never edits game values.
internal sealed class Candidates {
 internal const int Limit=256; const int PerFrame=128;
 volatile bool enabled;volatile bool finishTimedOut;readonly Action beforeWrite;internal bool Enabled {get{return enabled;}} Thread writer;readonly string path;readonly string session=Guid.NewGuid().ToString("N");
 sealed class Row {internal string key,source,kind,scene,context,reason,id;internal int count;}
 readonly Dictionary<string,Row> rows=new Dictionary<string,Row>();int frame=-1,inFrame,events,filtered,frameLimited,capacityLimited,writes;long ticks,peakTicks,flushTicks,snapshotTicks;double next=30;bool dirty;volatile string error="";
 internal Candidates(bool enabled,string output,Action beforeWrite=null){this.enabled=enabled;path=output;this.beforeWrite=beforeWrite;dirty=enabled;next=enabled?0:30;}
 internal static bool Useful(string source,bool bound=false){
  if(String.IsNullOrEmpty(source)||source.Length>1024)return false;string s=source.Trim();bool latin=false;foreach(char c in s){if(c<' '&&c!='\n'&&c!='\r'&&c!='\t')return false;if((c>='A'&&c<='Z')||(c>='a'&&c<='z'))latin=true;}if(!latin)return false;if(Regex.IsMatch(s,@"^[0-9][0-9\s.,:/%xX+\-]*$"))return false;
  if(s.StartsWith("http",StringComparison.OrdinalIgnoreCase)||s.StartsWith("www.",StringComparison.OrdinalIgnoreCase)||s.StartsWith("file:",StringComparison.OrdinalIgnoreCase)||s.StartsWith("/",StringComparison.Ordinal)||s.StartsWith("\\",StringComparison.Ordinal)||Regex.IsMatch(s,@"^(?:[A-Za-z]:[\\/]|[^\s]+\.(?:cw3|crpl|dll|exe|ttf|xml|json|png|jpg|wav|ogg)$)",RegexOptions.IgnoreCase))return false;
  if(Regex.IsMatch(s,@"^[^\s@]+@[^\s@]+$")||s.StartsWith(":",StringComparison.Ordinal)||Regex.IsMatch(s,@"^(?:[0-9.-]+\s+)?(?:->|<-)[A-Za-z_]\w*")||s.IndexOf("==",StringComparison.Ordinal)>=0||s.IndexOf(";",StringComparison.Ordinal)>=0&&s.IndexOf('{')>=0)return false;
  if(!bound&&Regex.IsMatch(s,@"^(?:Alpha[0-9]|F[0-9]{1,2}|Mouse[0-9]|Joystick\w*|Left(?:Shift|Control|Alt)|Right(?:Shift|Control|Alt)|KeyCode\.\w+|ACTIVATE|DEACTIVATE|ARM|DISARM|RESUPPLY|STOP RESUPPLY)$"))return false;
  return true;
 }
 internal void Record(int currentFrame,string source,string kind,string scene,string context,string reason,string id){
  if(!Enabled)return;long start=Stopwatch.GetTimestamp();try{
   if(frame!=currentFrame){frame=currentFrame;inFrame=0;}if(inFrame++>=PerFrame){frameLimited++;dirty=rows.Count>0;return;}events++;
   if(!Useful(source,!String.IsNullOrEmpty(id))){filtered++;return;}scene=Bound(scene,64);context=Bound(context,256);kind=Bound(kind,32);reason=Bound(reason,48);id=Bound(id,64);
   string key=String.Join("\0",new[]{source,kind,scene,context,reason,id});Row row;
   if(rows.TryGetValue(key,out row)){if(row.count<Int32.MaxValue)row.count++;dirty=true;return;}
   if(rows.Count>=Limit){capacityLimited++;dirty=true;return;}using(var hash=SHA256.Create())key=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(key))).Replace("-","").ToLowerInvariant();
   row=new Row{key=key,source=source,kind=kind,scene=scene,context=context,reason=reason,id=id,count=1};rows.Add(String.Join("\0",new[]{source,kind,scene,context,reason,id}),row);dirty=true;
  }finally{long elapsed=Stopwatch.GetTimestamp()-start;ticks+=elapsed;if(elapsed>peakTicks)peakTicks=elapsed;}
 }
 static string Bound(string s,int n){if(s==null)return "";if(s.Length<=n)return s;using(var hash=SHA256.Create()){string suffix=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(s))).Replace("-","").Substring(0,16);return s.Substring(0,n-19)+"..."+suffix;}}
 internal static string Q(string s){var b=new StringBuilder("\"");foreach(char c in s??"")switch(c){case '"':b.Append("\\\"");break;case '\\':b.Append("\\\\");break;case '\n':b.Append("\\n");break;case '\r':b.Append("\\r");break;case '\t':b.Append("\\t");break;default:if(c<' ')b.Append("\\u"+((int)c).ToString("x4"));else b.Append(c);break;}return b.Append('"').ToString();}
 static long Us(long t){return t*1000000/Stopwatch.Frequency;}
 internal string Status(int pendingWrites=0){return "{\"enabled\":"+(Enabled?"true":"false")+",\"rows\":"+rows.Count+",\"events\":"+events+",\"filtered\":"+filtered+",\"frame_limited\":"+frameLimited+",\"capacity_limited\":"+capacityLimited+",\"writes\":"+(writes+pendingWrites)+",\"record_us\":"+Us(ticks)+",\"peak_record_us\":"+Us(peakTicks)+",\"max_flush_us\":"+Us(Interlocked.Read(ref flushTicks))+",\"max_snapshot_us\":"+Us(snapshotTicks)+",\"write_pending\":"+((writer!=null&&writer.IsAlive)?"true":"false")+",\"finish_timed_out\":"+(finishTimedOut?"true":"false")+",\"io_error\":"+Q(error)+"}";}
 internal void Tick(double now){if(!Enabled||now<next)return;next=now+30;Flush();}
 internal void Flush(){
  if(!Enabled||!dirty||(writer!=null&&writer.IsAlive))return;long start=Stopwatch.GetTimestamp();try{
   var b=new StringBuilder("{\"format\":1,\"session\":"+Q(session)+",\"stats\":"+Status(1)+",\"candidates\":[");bool first=true;
   foreach(var r in rows.Values){if(!first)b.Append(',');first=false;b.Append("{\"key\":"+Q(r.key)+",\"source\":"+Q(r.source)+",\"kind\":"+Q(r.kind)+",\"scene\":"+Q(r.scene)+",\"context\":"+Q(r.context)+",\"reason\":"+Q(r.reason)+",\"id\":"+Q(r.id)+",\"count\":"+r.count+"}");}b.Append("]}\n");
   byte[] bytes=Encoding.UTF8.GetBytes(b.ToString());if(bytes.Length>2000000)throw new IOException("Candidate snapshot limit");
   // The worker receives only immutable bytes/path; all Unity objects and rows stay on the main thread.
   writer=new Thread(()=>Write(bytes));writer.IsBackground=true;writer.Start();dirty=false;
  }catch(Exception e){error=e.GetType().Name;enabled=false;}finally{long elapsed=Stopwatch.GetTimestamp()-start;if(elapsed>snapshotTicks)snapshotTicks=elapsed;}
 }
 void Write(byte[] bytes){long start=Stopwatch.GetTimestamp();try{string temp=path+".tmp";if(beforeWrite!=null)beforeWrite();File.WriteAllBytes(temp,bytes);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);Interlocked.Increment(ref writes);}catch(Exception e){error=e.GetType().Name;enabled=false;}finally{try{if(File.Exists(path+".tmp"))File.Delete(path+".tmp");}catch{}long elapsed=Stopwatch.GetTimestamp()-start;if(elapsed>Interlocked.Read(ref flushTicks))Interlocked.Exchange(ref flushTicks,elapsed);}}
 internal bool Finish(){
  if(writer!=null&&!writer.Join(1000)){finishTimedOut=true;return false;}
  Flush();if(writer!=null&&!writer.Join(1000)){finishTimedOut=true;return false;}
  return String.IsNullOrEmpty(error);
 }
}
