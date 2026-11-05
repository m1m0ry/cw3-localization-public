using System;
using System.Collections;
using System.Reflection;
using System.Reflection.Emit;
using UnityEngine;

class RenderingBindingContracts {
 const BindingFlags Private=BindingFlags.NonPublic|BindingFlags.Static;
 static int checks;
 static void Need(bool value,string name){if(!value)throw new Exception(name);checks++;}
 public static class Good {
  public static int Calls;
  public static void BindRenderingV1(out Func<Material,object,Material> ordered,out Action<object> sync){Calls++;ordered=(m,o)=>m;sync=o=>{};}
 }
 public static class Half {public static void BindRenderingV1(out Func<Material,object,Material> a,out Action<object> b){a=(m,o)=>m;b=null;}}
 public static class Broken {public static void BindRenderingV1(out Func<Material,object,Material> a,out Action<object> b){throw new InvalidOperationException("fixture");}}
 public static class LateBroken {public static void BindRenderingV1(out Func<Material,object,Material> a,out Action<object> b){a=(m,o)=>m;b=o=>{};throw new InvalidOperationException("fixture after assigning both");}}
 public static class Wrong {public static void BindRenderingV1(out Func<Material,object,Material> a){a=null;}}
 static void Target(Type type){
  var root=typeof(CW3Runtime);root.GetField("implementation",Private).SetValue(null,type);root.GetField("attempted",Private).SetValue(null,true);
  root.GetField("failure",Private).SetValue(null,null);root.GetField("notice",Private).SetValue(null,null);
  ((IDictionary)root.GetField("calls",Private).GetValue(null)).Clear();
 }
 static Type Interface(bool omit){
  var module=AppDomain.CurrentDomain.DefineDynamicAssembly(new AssemblyName("RenderContract"+Guid.NewGuid().ToString("N")),AssemblyBuilderAccess.Run).DefineDynamicModule("test");
  var type=module.DefineType("CW3Runtime",TypeAttributes.Public|TypeAttributes.Abstract|TypeAttributes.Sealed);
  foreach(var method in typeof(CW3Runtime).GetMethods(BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly)){
   if(method.Name=="BridgeStatus"||omit&&method.Name=="BindRenderingV1")continue;
   var pars=method.GetParameters();var args=new Type[pars.Length];for(int i=0;i<args.Length;i++)args[i]=pars[i].ParameterType;
   var build=type.DefineMethod(method.Name,MethodAttributes.Public|MethodAttributes.Static,method.ReturnType,args);
   var il=build.GetILGenerator();if(method.ReturnType!=typeof(void)){if(method.ReturnType.IsValueType)il.Emit(OpCodes.Ldc_I4_0);else il.Emit(OpCodes.Ldnull);}il.Emit(OpCodes.Ret);
  }
  return type.CreateType();
 }
 static void Main(){
  var check=typeof(CW3Runtime).GetMethod("CheckInterface",Private);check.Invoke(null,new object[]{Interface(false)});checks++;
  bool rejected=false;try{check.Invoke(null,new object[]{Interface(true)});}catch(TargetInvocationException e){rejected=e.InnerException is MissingMethodException;}Need(rejected,"V1 missing is ABI mismatch");
  Func<Material,object,Material> ordered;Action<object> sync;
  Target(typeof(Good));CW3Runtime.BindRenderingV1(out ordered,out sync);Need(ordered!=null&&sync!=null,"pair bound");Need(CW3Runtime.BridgeStatus()=="ready","healthy bridge");
  var source=new Material();Need(ordered(source,null)==source,"typed delegate call");Need(Good.Calls==1,"single bind request");
  foreach(Type bad in new[]{typeof(Half),typeof(Broken),typeof(LateBroken),typeof(Wrong)}){
   Target(bad);CW3Runtime.BindRenderingV1(out ordered,out sync);Need(ordered==null&&sync==null,"no partially published pair");
   Need(CW3Runtime.BridgeStatus()!="ready","failure visible in status");Need(typeof(CW3Runtime).GetField("notice",Private).GetValue(null)!=null,"failure notice created");
  }
  Console.WriteLine("PASS "+checks+" rendering binding/version/failure checks");
 }
}
