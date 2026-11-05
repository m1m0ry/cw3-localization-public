// GUI surface needed to compile the real stable runtime bridge in the isolated
// cross-assembly test. Rendering ownership lives in RenderingFixture.cs.
namespace UnityEngine {
 public enum TextAnchor {UpperLeft}
 public class GUIContent {public string text;}
 public class GUILayoutOption {}
 public class GUIStyle {public bool wordWrap;public int fontSize;public TextAnchor alignment;public GUIStyle(){}public GUIStyle(GUIStyle other){}}
 public class GUISkin {public GUIStyle box=new GUIStyle();}
 public struct Rect {public Rect(float a,float b,float c,float d){}}
 public class TextMesh:Component {public string text;}
 public static class Screen {public static int width=1280;}
 public static class Debug {public static void LogError(string message){}}
 public static class GUI {public static GUISkin skin=new GUISkin();public static int depth;public static void Box(params object[] args){}public static void Label(params object[] args){}public static bool Button(params object[] args){return false;}}
 public static class GUILayout {
  public static bool Button(params object[] args){return false;}
  public static bool Toggle(bool value,params object[] args){return value;}
  public static string TextField(string value,params object[] args){return value;}
  public static string TextArea(string value,params object[] args){return value;}
  public static int SelectionGrid(int value,params object[] args){return value;}
  public static void BeginArea(params object[] args){}
  public static void Label(params object[] args){}public static void Box(params object[] args){}
 }
}
