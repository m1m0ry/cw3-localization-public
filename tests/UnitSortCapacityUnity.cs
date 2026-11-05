// Separate assembly keeps the production UnityEngine scope contract in fixtures.
using System;
namespace UnityEngine {public class GameObject {
 public object unit;public GameObject(object value){unit=value;}public T GetComponent<T>() where T:class{return unit as T;}
 public static GameObject[] Input;public static GameObject[] FindGameObjectsWithTag(string tag){if(tag!="UnitTag")throw new Exception("wrong tag");return Input;}
}}
