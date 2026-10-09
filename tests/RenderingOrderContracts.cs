using System;
class RenderingOrderContracts {
 static void Need(bool value,string reason){if(!value)throw new Exception(reason);}
 static void Main(){
  // CW3 level3: root panel z=0, title depth12; dialog panel z=0,
  // but its direct child MessageDialog is one UI unit in front, body depth3.
  Need(CW3Rendering.CompareOrder(0,-1,12,3,1,1)<0,"Map title must draw before the foreground dialog");
  Need(CW3Rendering.CompareOrder(-1,-1,2,3,0,1)<0,"Dialog body must draw after its background");
  Need(CW3Rendering.CompareOrder(-1,-1,3,3,0,1)<0,"Equal-depth text must draw after the atlas widget");
  Need(CW3Rendering.CompareOrder(-2,-1,0,99,0,1)>0,"Foreground group must win over unrelated widget depth");
  Console.WriteLine("PASS foreground dialog, background/text ordering and independent depth groups");
 }
}
