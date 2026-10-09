using System;using System.Linq;using Mono.Cecil;using Mono.Cecil.Cil;
// Native dispatch accepts the sprite or a child, but reads locked from the hit child.
// Read the already matched owner; keep its original lock and action branches.
internal static class MainMenuClickPatch {
 static string[] Fields={"loadFileSprite","creditsSprite","worldMachineSprite"};
 static Instruction[] Locks(ModuleDefinition module){return module.GetType("MainMenu").Methods.Single(m=>m.Name=="OnMyMouseDown").Body.Instructions.Where(i=>i.OpCode==OpCodes.Callvirt&&i.Operand is MethodReference&&((MethodReference)i.Operand).FullName=="System.Boolean MainMenuSpriteManager::get_locked()").ToArray();}
 static void Need(bool value,string message){if(!value)throw new Exception(message);}
 internal static void Apply(ModuleDefinition module){
  var method=module.GetType("MainMenu").Methods.Single(m=>m.Name=="OnMyMouseDown");var xs=method.Body.Instructions;var locks=Locks(module);Need(locks.Length==3,"Main menu lock site count");
  for(int n=0;n<locks.Length;n++){int at=xs.IndexOf(locks[n]);var receiver=xs[at-2];var read=xs[at-1];var call=read.Operand as GenericInstanceMethod;
   Need(receiver.OpCode==OpCodes.Ldloc_1&&read.OpCode==OpCodes.Callvirt&&call!=null&&call.DeclaringType.FullName=="UnityEngine.GameObject"&&call.Name=="GetComponent"&&call.GenericArguments.Count==1&&call.GenericArguments[0].FullName=="MainMenuSpriteManager","Main menu hit component pattern");
   var owner=module.GetType("MainMenu").Fields.Single(f=>f.Name==Fields[n]);Need(owner.FieldType.FullName=="MainMenuSpriteManager","Main menu owner field type");
   receiver.OpCode=OpCodes.Ldarg_0;receiver.Operand=null;read.OpCode=OpCodes.Ldfld;read.Operand=owner;
  }
 }
 internal static void Reverse(ModuleDefinition original,ModuleDefinition patched){
  var before=original.GetType("MainMenu").Methods.Single(m=>m.Name=="OnMyMouseDown").Body.Instructions;var after=patched.GetType("MainMenu").Methods.Single(m=>m.Name=="OnMyMouseDown").Body.Instructions;var oldLocks=Locks(original);var newLocks=Locks(patched);Need(oldLocks.Length==3&&newLocks.Length==3,"Main menu reverse lock site count");
  for(int n=0;n<newLocks.Length;n++){int at=after.IndexOf(newLocks[n]),oldAt=before.IndexOf(oldLocks[n]);var field=after[at-1].Operand as FieldReference;Need(after[at-2].OpCode==OpCodes.Ldarg_0&&after[at-1].OpCode==OpCodes.Ldfld&&field!=null&&field.Name==Fields[n]&&field.DeclaringType.FullName=="MainMenu","Main menu owner receiver repair");after[at-2].OpCode=before[oldAt-2].OpCode;after[at-2].Operand=before[oldAt-2].Operand;after[at-1].OpCode=before[oldAt-1].OpCode;after[at-1].Operand=patched.ImportReference((MethodReference)before[oldAt-1].Operand);}
 }
}
