"""CW3-only hash-locked optional debug module; no eval or network interface."""
from pathlib import Path
import json,sys,hashlib,subprocess,shutil,os,uuid,time,re
import game_target
from player_install import idle
ROOT=Path(__file__).resolve().parents[1];args=sys.argv[1:];config=ROOT/'config.local.json';R=ROOT/'local-only/debug';state=None
while args[:1] and args[0].startswith('--'):
 option,value=args[:2];args=args[2:]
 if option=='--config':config=Path(value)
 elif option=='--debug-build':R=(ROOT/value).resolve();assert R.is_relative_to((ROOT/'local-only').resolve())
 elif option=='--state':state=Path(value).resolve(strict=True)
 else:raise ValueError(option)
C=json.loads(config.read_text());target=game_target.load(C);mac=target['id']==game_target.MACOS
G=Path(C['game']);G=G if G.is_absolute() else ROOT/G
if mac:
 import mac_runtime_debug
 mac_runtime_debug.action(G,state,args,ROOT/'local-only/evidence')
 sys.exit(0)
M=json.loads((R/'manifest.json').read_text())
D=G/'CW3_Data/cw3-debug'
core=game_target.installed(G,'CW3_Data/Managed/Assembly-CSharp.dll',target);helper=core.parent/'CW3Debug.dll';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
M['base']=str(ROOT/M['base'])
(ROOT/'local-only/evidence').mkdir(parents=True,exist_ok=True)
def put(src,dst):
 tmp=dst.with_name(dst.name+'.cw3debug-tmp');assert not tmp.exists();shutil.copy2(src,tmp);assert sha(src)==sha(tmp);os.replace(tmp,dst)
mode=args[0]
if mode in ('enable','disable'):
 idle();expected=M['base_sha256'] if mode=='enable' else M['debug_sha256'];assert sha(core)==expected,'Unknown core version'
 if mode=='enable':
  assert not helper.exists();assert sha(R/'CW3Debug.dll')==M['helper_sha256'];assert sha(R/'Assembly-CSharp.debug.dll')==M['debug_sha256'];D.mkdir(exist_ok=True)
  for n in ('request.txt','response.json','ready.json'):
   if (D/n).exists():(D/n).unlink()
  put(R/'CW3Debug.dll',helper);put(R/'Assembly-CSharp.debug.dll',core);(D/'enabled.txt').write_text(M['debug_sha256']+'\n')
 else:
  assert sha(helper)==M['helper_sha256'];assert sha(Path(M['base']))==M['base_sha256'];put(Path(M['base']),core);helper.unlink()
  for n in ('enabled.txt','request.txt','ready.json'):
   if (D/n).exists():(D/n).unlink()
 print(json.dumps({'mode':mode,'core_sha256':sha(core),'helper_present':helper.exists()}))
elif mode=='command':
 assert sha(core)==M['debug_sha256'];assert (D/'enabled.txt').read_text().strip()==M['debug_sha256'];command=args[1];arg=args[2] if len(args)>2 else '';assert command in ('snapshot','ui_probe','discovery_probe','font_probe','atlas_probe','runtime_probe','style_probe','layout_probe','menu_open','menu_close','dialogue_replay','prelude_replay','prelude_return','archive_next','archive_close','archive_open','message_probe','select_planet','start_mission','load_auto','load_slot','restart_mission','planet_preview','description','settings_native_open','settings_open','settings_probe','settings_change','settings_save','settings_cancel','settings_defaults','screenshot');assert (arg in ('Tempus','Carcere','Tiplex')) if command=='select_planet' else (arg=='Tempus') if command=='planet_preview' else (arg in ('Collector','Relay','Mortar')) if command=='description' else (arg in ('awaken','skip')) if command=='prelude_return' else (arg=='0') if command=='load_slot' else (0<len(arg)<=256 and '\t' not in arg and '\n' not in arg and '\r' not in arg) if command=='layout_probe' else (re.fullmatch(r'(body|title|ui|status)\|(sans|serif)\|(75|80|85|90|95|100|105|110|115|120|125|130|135|140|145|150)',arg) is not None) if command=='settings_change' else arg==''
 ident=uuid.uuid4().hex;req=D/'request.txt';assert not req.exists(),'Outstanding command';tmp=D/'request.tmp';tmp.write_text('\t'.join([ident,command,arg]).rstrip('\t')+'\n');os.replace(tmp,req)
 for _ in range(40):
  p=D/'response.json'
  if p.exists():
   try:result=json.loads(p.read_text())
   except json.JSONDecodeError:result={}
   if result.get('id')==ident:
    evidence=ROOT/'local-only/evidence'/('debug-'+ident+'.json');evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'result_path':str(evidence),'ok':result.get('ok'),'result_summary':result.get('error',result.get('result',{}).get('scene',result.get('result')))},ensure_ascii=False));break
  time.sleep(.25)
 else:raise TimeoutError('Game did not acknowledge; request retained, do not blindly repeat')
else:raise ValueError(mode)
