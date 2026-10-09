using System;
namespace UnityEngine {public class GameObject {public object component;public GameObject parent;public T GetComponent<T>()where T:class{return component as T;}}}
public class MainMenuSpriteManager {public UnityEngine.GameObject gameObject=new UnityEngine.GameObject();public bool locked{get;set;}public MainMenuSpriteManager(){gameObject.component=this;}}
public class MainMenu {
 public MainMenuSpriteManager loadFileSprite=new MainMenuSpriteManager(),creditsSprite=new MainMenuSpriteManager(),worldMachineSprite=new MainMenuSpriteManager();public UnityEngine.GameObject selected;public int action;
 public void OnMyMouseDown(){int marker=0;var hit=selected;action=marker;
  if(hit==loadFileSprite.gameObject||hit.parent==loadFileSprite.gameObject){if(!hit.GetComponent<MainMenuSpriteManager>().locked)action=1;return;}
  if(hit==creditsSprite.gameObject||hit.parent==creditsSprite.gameObject){if(!hit.GetComponent<MainMenuSpriteManager>().locked)action=2;return;}
  if(hit==worldMachineSprite.gameObject||hit.parent==worldMachineSprite.gameObject){if(!hit.GetComponent<MainMenuSpriteManager>().locked)action=3;return;}
 }
}
class MenuClickFixture {
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 static void Main(string[] args){bool patched=args[0]=="patched";var m=new MainMenu();var owners=new[]{m.loadFileSprite,m.creditsSprite,m.worldMachineSprite};for(int i=0;i<3;i++){
  m.selected=owners[i].gameObject;m.OnMyMouseDown();Need(m.action==i+1,"Root click preserves action");
  m.selected=new UnityEngine.GameObject{parent=owners[i].gameObject};bool nullChild=false;try{m.OnMyMouseDown();}catch(NullReferenceException){nullChild=true;}Need(patched?!nullChild&&m.action==i+1:nullChild,"Child click repaired only in patched output");
  owners[i].locked=true;m.selected=owners[i].gameObject;m.OnMyMouseDown();Need(m.action==0,"Locked root stays blocked");if(patched){m.selected=new UnityEngine.GameObject{parent=owners[i].gameObject};m.OnMyMouseDown();Need(m.action==0,"Locked child stays blocked");}owners[i].locked=false;
 }
 m.selected=new UnityEngine.GameObject();m.OnMyMouseDown();Need(m.action==0,"Unmatched hit remains a no-op");Console.WriteLine("PASS "+args[0]+": three root/child clicks, original lock conditions, unmatched hit");}
}
