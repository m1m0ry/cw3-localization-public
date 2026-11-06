using System;using UnityEngine;
public class CreeperSimulation {
 public static void setUVs(int i,Vector2[] a,float x,float y,float xv,float yv){a[i]=new Vector2(x,y);a[i+1]=new Vector2(x+xv,y);a[i+2]=new Vector2(x+xv,y+yv);a[i+3]=new Vector2(x,y+yv);}
 static void Expected(int i,Vector2[] a,float x,float y,float xv,float yv){a[i]=new Vector2(x,y);a[i+1]=new Vector2(x+xv,y);a[i+2]=new Vector2(x+xv,y+yv);a[i+3]=new Vector2(x,y+yv);}
 // This source is also the independently compiled IL parity oracle, not the
 // runtime reference result. The expected result above stays the original code.
 public static void TestedLocal(int i,Vector2[] a,float x,float y,float xv,float yv){a[i].x=x;a[i].y=y;float right=x+xv;a[i+1].x=right;a[i+1].y=y;float top=y+yv;a[i+2].x=right;a[i+2].y=top;a[i+3].x=x;a[i+3].y=top;}
 static int Bits(float x){return BitConverter.ToInt32(BitConverter.GetBytes(x),0);}static float Float(int x){return BitConverter.ToSingle(BitConverter.GetBytes(x),0);}
 static int checks;static void Need(bool ok,string why){if(!ok)throw new Exception(why);}
 static Vector2[] Array(int n){if(n<0)return null;var a=new Vector2[n];for(int i=0;i<n;i++)a[i]=new Vector2(Float(unchecked((int)0xffc12345)),Float(unchecked((int)0x80000000)));return a;}
 static void Case(int n,int start,float x,float y,float xv,float yv){var a=Array(n);var b=Array(n);string ea="",eb="";try{Expected(start,a,x,y,xv,yv);}catch(Exception e){ea=e.GetType().FullName;}try{setUVs(start,b,x,y,xv,yv);}catch(Exception e){eb=e.GetType().FullName;}Need(ea==eb,"exception type");if(a!=null)for(int i=0;i<a.Length;i++)Need(Bits(a[i].x)==Bits(b[i].x)&&Bits(a[i].y)==Bits(b[i].y),"float bits or partial write @"+i);checks++;}
 static void Main(){float[] values={0f,Float(unchecked((int)0x80000000)),1f,-1f,float.MaxValue,float.MinValue,float.NaN,float.PositiveInfinity,float.NegativeInfinity,1e-20f,1e20f,Float(0x7fc00001),Float(unchecked((int)0xffc12345)),Float(0x7f800001),Float(unchecked((int)0xff800001))};foreach(float x in values)foreach(float y in values)foreach(float xv in values)foreach(float yv in values)Case(4,0,x,y,xv,yv);for(int n=-1;n<8;n++){for(int i=-1;i<=n+1;i++)Case(n,i,1,2,3,4);foreach(int i in new[]{int.MinValue,int.MaxValue,int.MaxValue-1})Case(n,i,1,2,3,4);}Console.WriteLine("Creeper UV exact float/NaN-payload/exception/partial-write cases="+checks);}
}
