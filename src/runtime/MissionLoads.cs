using System;

// A synchronous native loader invocation owns only its own pending resource.
internal static class MissionLoads {
 sealed class Frame {internal Frame Parent;internal MessageBindings.Resource Resource;}
 [ThreadStatic] static Frame current;
 internal static void Begin(){current=new Frame{Parent=current};}
 internal static void Capture(MessageBindings.Resource resource){if(current!=null)current.Resource=resource;}
 internal static MessageBindings.Resource Take(){if(current==null)return null;var resource=current.Resource;current.Resource=null;return resource;}
 internal static void End(){if(current!=null)current=current.Parent;}
}
