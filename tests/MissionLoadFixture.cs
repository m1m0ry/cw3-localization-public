using System;

// Native-shaped non-void loader, existing catch/finally, early return and nested retry.
public static class CW3Runtime {
 public static void BeginMissionLoad(){MissionLoads.Begin();}
 public static void EndMissionLoad(){MissionLoads.End();}
}
public static class MissionLoadFixture {
 static readonly MessageBindings.Resource outer=new MessageBindings.Resource{Key="outer"},inner=new MessageBindings.Resource{Key="inner"};
 static readonly object result=new object();static readonly Exception failure=new InvalidOperationException("native failure");static int nativeFinally;
 static void Need(bool value,string why){if(!value)throw new Exception(why);}
 static object Load(int mode){
  MissionLoads.Capture(mode==9?inner:outer);
  try{
   if(mode==1||mode==4)throw failure;
   if(mode==2)return null;
   if(mode==3){try{Load(1);}catch(Exception e){Need(Object.ReferenceEquals(e,failure),"Nested native exception identity");}Need(MissionLoads.Take()==outer,"Nested failure preserves parent resource");}
   if(mode==5){Need(Load(9)==result,"Nested return value");Need(MissionLoads.Take()==outer,"Nested success preserves parent resource");}
   if(mode==6){Need(Load(2)==null,"Nested cancellation return");Need(MissionLoads.Take()==outer,"Nested cancellation preserves parent resource");}
   if(mode==7){Need(MissionLoads.Take()==outer&&MissionLoads.Take()==null,"Resource consumed once");}
   return result;
  }catch(InvalidOperationException){if(mode==4)return result;throw;}
  finally{nativeFinally++;}
 }
 static void VoidLoad(bool fail){MissionLoads.Capture(inner);if(fail)throw failure;}
 public static void Verify(){
  for(int mode=0;mode<=7;mode++){
   int before=nativeFinally;
   try{var value=Load(mode);Need(mode==2?value==null:value==result,"Native return identity");Need(mode!=1,"Native exception propagated");}
   catch(InvalidOperationException e){Need(mode==1&&Object.ReferenceEquals(e,failure),"Unchanged native exception object");}
   Need(nativeFinally>before,"Existing native finally ran");Need(MissionLoads.Take()==null,"No pending resource after success/failure/cancellation/retry");
   MissionLoads.Capture(outer);Need(MissionLoads.Take()==null,"Unscoped load cannot inherit stale resource");
  }
  VoidLoad(false);Need(MissionLoads.Take()==null,"Void success cleanup");
  try{VoidLoad(true);throw new Exception("Void exception swallowed");}catch(InvalidOperationException e){Need(Object.ReferenceEquals(e,failure),"Void native exception identity");}
  Need(MissionLoads.Take()==null,"Void exception cleanup");
  Console.WriteLine("PASS executed production Cecil scope: non-void/void returns, existing catch/finally, native exception identity, early cancellation, nested failure/success/cancel, retry and no stale resource.");
 }
}
