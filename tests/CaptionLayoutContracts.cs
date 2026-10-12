using System;using System.Collections.Generic;using UnityEngine;
// Only the caption's host contract is simulated; no game or font rasterizer runs.
namespace UnityEngine {
 public struct Vector2 {public float x,y;public Vector2(float a,float b){x=a;y=b;}}
 public struct Vector3 {public float x,y,z;public Vector3(float a,float b,float c){x=a;y=b;z=c;}}
 public class Component {public string name;public Transform transform;}
 public class Transform {public string name;public Transform parent;public Vector3 localScale,localPosition;public Dictionary<string,Transform> children=new Dictionary<string,Transform>();public Transform Find(string n){Transform t;return children.TryGetValue(n,out t)?t:null;}public Component GetComponent(string n){return null;}}
 public static class Screen {public static int width=1280,height=720;}
 public class GUIContent {public GUIContent(string s){}}
 public class GUIStyle {public Vector2 CalcSize(GUIContent c){return new Vector2(10,10);}}
 public class GUILayoutOption {}
 public static class GUILayout {public static GUILayoutOption Width(float n){return new GUILayoutOption();}}
}
public class CaptionFont {public string WrapText(string s,float width,int lines,bool e,CaptionSymbols symbols){int n=Math.Max(1,(int)width);var parts=new List<string>();for(int i=0;i<s.Length;i+=n)parts.Add(s.Substring(i,Math.Min(n,s.Length-i)));return String.Join("\n",parts.ToArray());}public Vector2 CalculatePrintedSize(string s,bool e,CaptionSymbols symbols){string[] lines=s.Split('\n');int width=0;foreach(string line in lines)width=Math.Max(width,line.Length);return new Vector2(width,lines.Length);}}
public enum CaptionSymbols {None}
public class CaptionLabel:Component {public object font{get;set;}public CaptionSymbols symbolStyle{get;set;}public bool supportEncoding{get;set;}public bool password{get;set;}public bool shrinkToFit{get;set;}public int lineWidth{get;set;}public int maxLineCount{get;set;}}
class CaptionLayoutContracts {
 static void Need(bool b,string why){if(!b)throw new Exception(why);}
 static void Main(){
  var parent=new Transform{name="CommandNodePanels"};parent.children.Add("SlicedSprite (ButtonSelection)",new Transform{localScale=new Vector3(400,12,1)});
  var tr=new Transform{parent=parent,localPosition=new Vector3(0,2,0),localScale=new Vector3(16,16,1)};
  var label=new CaptionLabel{name="MapTitleLabel",transform=tr,font=new CaptionFont(),shrinkToFit=true};
  foreach(string title in new[]{"永恒之弧：起航星区：七九塞雷",new string('星',36)}){
   CaptionLayout.Prepare(label,title);
   Need(tr.localPosition.x==0&&tr.localPosition.y==2&&tr.localPosition.z==0,"Native title anchor must remain unchanged");
   // level3 CN0EnergyBar y=-35 + NameLabel y=15 => status row top=-20.
   Need(tr.localPosition.y-tr.localScale.y>-20,"Title must remain above the command-node status row");
   Need(label.maxLineCount==1&&label.lineWidth==384,"Title must retain bounded single-row wrapping");
   Need(tr.localScale.y>=12&&tr.localScale.y<=16,"Title font remains readable");
   CaptionLayout.Prepare(label,title);Need(tr.localPosition.y==2,"Reprocessing must not shift the anchor");
  }
  tr.localPosition=new Vector3(7,5,-1);CaptionLayout.Prepare(label,"星区标题");Need(tr.localPosition.x==7&&tr.localPosition.y==5&&tr.localPosition.z==-1,"Preserve later native anchor adjustments");
  var dialog=new Transform{name="MessageDialog"};var next=new Transform{localPosition=new Vector3(315,-116,0)};next.children.Add("Background",new Transform{localScale=new Vector3(60,20,1)});dialog.children.Add("NextButton",next);
  var bodyTr=new Transform{parent=dialog,localPosition=new Vector3(-216,-12,0),localScale=new Vector3(30,30,1)};var body=new CaptionLabel{name="MessageText",transform=bodyTr,font=new CaptionFont(),lineWidth=561,maxLineCount=5};string text=new string('字',120);
  CaptionLayout.PrepareStyled(body,text,150);float unit=bodyTr.localScale.y;var font=(CaptionFont)body.font;float height=font.CalculatePrintedSize(font.WrapText(text,561/unit,0,false,CaptionSymbols.None),false,CaptionSymbols.None).y*unit;Need(height<=90.1&&unit>=12&&unit<=30,"full body stays above fixed button row");Need(bodyTr.localPosition.y==-12&&body.maxLineCount==5,"body anchor and native limits preserved");CaptionLayout.PrepareStyled(body,text,150);Need(bodyTr.localScale.y==unit,"fitting is idempotent");
  Console.WriteLine("PASS native title anchor, status-row separation, bounded titles and repeat processing");
 }
}
