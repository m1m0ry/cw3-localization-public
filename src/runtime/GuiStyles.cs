using UnityEngine;
// Same native calls and arguments; only owned GUIStyle copies cross the display boundary.
public static partial class CW3Runtime {
 static GUIStyle Style(GUIStyle native,string text,string role){Load();return TextStyles.Gui(native,text,role);}
 public static void StyleLabel(string text,GUILayoutOption[] options,string role){GUILayout.Label(text,Style(GUI.skin.label,text,role),options);}
 public static void StyleLabelWith(string text,GUIStyle style,GUILayoutOption[] options,string role){GUILayout.Label(text,Style(style,text,role),options);}
 public static void StyleBox(string text,GUIStyle style,GUILayoutOption[] options){GUILayout.Box(text,Style(style,text,TextStylePolicy.Ui),options);}
 public static bool StyleContentButton(GUIContent text,GUILayoutOption[] options){return GUILayout.Button(text,Style(GUI.skin.button,text.text,TextStylePolicy.Ui),options);}
 public static bool StyleContentButtonWith(GUIContent text,GUIStyle style,GUILayoutOption[] options){return GUILayout.Button(text,Style(style,text.text,TextStylePolicy.Ui),options);}
 public static bool StyleToggle(bool value,string text,GUILayoutOption[] options){return GUILayout.Toggle(value,text,Style(GUI.skin.toggle,text,TextStylePolicy.Ui),options);}
 public static bool StyleToggleWith(bool value,string text,GUIStyle style,GUILayoutOption[] options){return GUILayout.Toggle(value,text,Style(style,text,TextStylePolicy.Ui),options);}
 public static string StyleTextField(string text,GUILayoutOption[] options){return GUILayout.TextField(text,Style(GUI.skin.textField,text,TextStylePolicy.CodeInput),options);}
 public static string StyleReadOnlyField(string text,GUILayoutOption[] options){return GUILayout.TextField(text,Style(GUI.skin.textField,text,TextStylePolicy.Ui),options);}
 public static string StyleTextArea(string text,GUILayoutOption[] options){return GUILayout.TextArea(text,Style(GUI.skin.textArea,text,TextStylePolicy.CodeInput),options);}
 public static void StyleArea(Rect rect,string text){GUILayout.BeginArea(rect,text,Style(GUI.skin.box,text,TextStylePolicy.Title));}
 public static void StyleAreaWith(Rect rect,string text,GUIStyle style){GUILayout.BeginArea(rect,text,Style(style,text,TextStylePolicy.Title));}
 public static bool StyleRectButton(Rect rect,string text){return GUI.Button(rect,text,Style(GUI.skin.button,text,TextStylePolicy.Ui));}
 public static bool StyleRectButtonWith(Rect rect,string text,GUIStyle style){return GUI.Button(rect,text,Style(style,text,TextStylePolicy.Ui));}
 public static void StyleRectLabel(Rect rect,string text,GUIStyle style){GUI.Label(rect,text,Style(style,text,TextStylePolicy.Body));}
 public static int StyleGrid(int selected,GUIContent[] text,int columns,GUIStyle style,GUILayoutOption[] options){string joined="";if(text!=null)foreach(var c in text)if(c!=null)joined+=c.text;return GUILayout.SelectionGrid(selected,text,columns,Style(style,joined,TextStylePolicy.Ui),options);}
}
