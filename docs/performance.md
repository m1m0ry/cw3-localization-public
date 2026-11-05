# 原版运行开销

性能调整保持原版 30 FPS、模拟步进、集合遍历顺序、寻路规则和存档格式。构建时独立执行优化与逆向审计，不把性能改动混入汉化绑定。

## 枚举器释放的临时分配

原版旧编译器在部分 `foreach` 的 `finally` 中，将集合的值类型枚举器装箱，再调用 `IDisposable.Dispose()`。它不是集合内容的快照，但每次执行都会产生一个只用于释放的短命对象。这个模式出现在单位更新、能量分配和 CRPL 寻路等路径。当前 Mac Steam 2.12 原版程序集识别到 406 处。

`src/performance/EnumeratorDisposePatch.cs` 只处理已知 BCL 集合的枚举器：List、HashSet、Dictionary（含 Keys/Values）、Queue 和 Stack。构建器核对真实类型为实现 IDisposable 的结构体，然后把装箱替换为“保存到新增局部变量、取得副本地址、constrained 调用原 Dispose”。它不会省略释放，也不会直接修改原来的枚举器局部变量，因此保留原先对副本执行 Dispose 的语义。所有原循环与异常处理边界保持不变；不改 ManagerPool 返回的快照或 A* 的开放集合与平局选择。

优化没有新增运行时组件、公共接口、缓存或依赖，仍作用于 Assembly-CSharp.dll。它不属于包外渲染更新：安装包含此项的完整候选会更新 app 内程序集，应按现有安装器处理签名。只改源码不影响已安装游戏。

构建会执行行为契约和单独的逆向审计：检查泛型、空集合、原枚举器继续使用、嵌套循环、提前返回、异常、遍历时集合修改，以及未经支持的自定义枚举器。审计精确移除每个新增指令和局部变量后，再比较整份程序集的字段、方法、原指令与异常处理范围。不能完整还原时构建失败。

验证入口：

```sh
python3 tools/test.py --config /path/to/build-config.json --suite EnumeratorDisposeContracts
```

该测试只需 Mono 和 Cecil，不需要游戏或字体文件。分配量检查在宿主提供 `GC.GetAllocatedBytesForCurrentThread` 时运行；它证明此模式的临时分配被移除，不代表整局游戏的 CPU、帧率或输入延迟收益。实机收益还取决于地图、单位数量、脚本负载及游戏内 Mono 的 GC 行为。若新的受支持原版不再使用此模式，或类型/结构审计不通过，应停止应用并重新检查，而非放松校验。
