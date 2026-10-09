using System;using System.Reflection;using UnityEngine;

// Semantic roles at ProcessText, not a scene scan. Keep native clipping and materials.
internal static class CaptionLayout {
 const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance;
 static object Get(object o,string n){if(o==null)return null;var p=o.GetType().GetProperty(n,Flags);return p==null?null:p.GetValue(o,null);}
 static void Set(object o,string n,object value){var p=o.GetType().GetProperty(n,Flags);if(p!=null&&p.CanWrite&&!System.Object.Equals(p.GetValue(o,null),value))p.SetValue(o,value,null);}
 static float Measure(object label,string text,float width,bool wrap){
  object font=Get(label,"font"),symbols=Get(label,"symbolStyle");if(font==null||symbols==null)return 0;
  bool encoding=(bool)Get(label,"supportEncoding");Type t=font.GetType();
  if(wrap){var m=t.GetMethod("WrapText",new[]{typeof(string),typeof(float),typeof(int),typeof(bool),symbols.GetType()});text=(string)m.Invoke(font,new object[]{text,width,0,encoding,symbols});}
  var size=(Vector2)t.GetMethod("CalculatePrintedSize",new[]{typeof(string),typeof(bool),symbols.GetType()}).Invoke(font,new object[]{text,encoding,symbols});return wrap?size.y:size.x;
 }
 static bool Chinese(string text){foreach(char c in text)if(c>='\u3400'&&c<='\u9fff')return true;return false;}
 internal static void Prepare(Component label,string display){
  if(label==null||String.IsNullOrEmpty(display)||!Chinese(display)||(bool)Get(label,"password"))return;
  Transform tr=label.transform;Vector3 scale=tr.localScale,pos=tr.localPosition;
  if(label.name=="CharacterName"&&tr.parent!=null&&tr.parent.name.StartsWith("MessageDialog",StringComparison.Ordinal)){
   Transform portrait=tr.parent.Find("Texture");if(portrait==null||portrait.localScale.x<=0)return;
   float width=Math.Abs(portrait.localScale.x);Set(label,"shrinkToFit",false);Set(label,"lineWidth",(int)Math.Floor(width));Set(label,"maxLineCount",2);
   float unit=16;while(unit>12&&Measure(label,display,width/unit,true)>2.01f)unit--;
   scale.x=scale.y=unit;tr.localScale=scale;float height=Measure(label,display,width/unit,true)*unit;
   float bottom=portrait.localPosition.y-Math.Abs(portrait.localScale.y)*0.5f;
   pos.y=Math.Max(-113,bottom+Math.Min(2*unit,height));tr.localPosition=pos;
  }else if(label.name=="MapTitleLabel"&&tr.parent!=null&&tr.parent.name=="CommandNodePanels"){
   Transform strip=tr.parent.Find("SlicedSprite (ButtonSelection)");if(strip==null)return;
   float width=Math.Abs(strip.localScale.x)-16;
   for(Transform root=tr;root!=null;root=root.parent){Component ui=root.GetComponent("UIRoot");if(ui!=null){object height=Get(ui,"activeHeight");if(height is int&&Screen.height>0)width=Math.Min(width,(int)height*(float)Screen.width/Screen.height-32);break;}}
   if(width<96)return;Set(label,"shrinkToFit",false);Set(label,"lineWidth",(int)Math.Floor(width));Set(label,"maxLineCount",1);
   float measured=Measure(label,display,0,false)*16,unit=measured>width?Math.Max(12,(float)Math.Floor(16*width/measured)):16;
   // Native title/anchor position reserves the row above the command-node bars.
   // Only fit its width; moving it down overlaps CN name/production labels.
   scale.x=scale.y=unit;tr.localScale=scale;
  }
 }
 // GUILayout uses these same options for drawing and hit testing. Retain caller styles/limits.
 internal static GUILayoutOption[] ButtonOptions(string text,GUIStyle style,GUILayoutOption[] options){
  if(style==null||options==null)return options;float needed=(float)Math.Ceiling(style.CalcSize(new GUIContent(text)).x);if(needed>256)return options;
  int fixedAt=-1;float width=0;
  var type=typeof(GUILayoutOption).GetField("type",Flags);var value=typeof(GUILayoutOption).GetField("value",Flags);if(type==null||value==null)return options;
  for(int i=0;i<options.Length;i++){
   if(options[i]==null)return options;string kind=type.GetValue(options[i]).ToString();
   if(kind!="maxWidth"&&kind!="fixedWidth")continue;float amount=Convert.ToSingle(value.GetValue(options[i]));
   if(kind=="maxWidth"&&amount<needed)return options;if(kind=="fixedWidth"){fixedAt=i;width=amount;}
  }
  if(fixedAt<0||width>=needed)return options;var adjusted=(GUILayoutOption[])options.Clone();adjusted[fixedAt]=GUILayout.Width(needed);return adjusted;
 }
}
