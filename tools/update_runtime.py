"""Validate and replace only CW3's external dictionary/font while the game is closed."""
from pathlib import Path
import argparse,json,hashlib,subprocess,shutil,os
import translation_contract
ROOT=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
def location(c,key):
 p=Path(c[key]);return p if p.is_absolute() else ROOT/p
def validate(dictionary,font):
 from fontTools.ttLib import TTFont
 doc=translation_contract.read(dictionary)
 locks=translation_contract.read(ROOT/'translations/targets.lock.json')
 with TTFont(font) as f:
  assert 'fvar' not in f,'Use a static weight400 font for Unity 5'
  names={n.toUnicode() for n in f['name'].names if n.nameID in (1,16)}
  assert any(name.startswith('CW3 Sans SC External')for name in names),'External font family must remain CW3 Sans SC External'
  cps=set(f.getBestCmap())
 return len(translation_contract.check(doc,locks,cps))
def put(source,target):
 target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.runtime-update-tmp');assert not temp.exists()
 try:
  shutil.copyfile(source,temp);assert sha(temp.read_bytes())==sha(source.read_bytes());os.replace(temp,target)
 finally:
  temp.unlink(missing_ok=True)
def update(config,dictionary,font=None,serif=None,style=None):
 game=location(config,'game');package=location(config,'package');build=location(config,'build');manifest=package/'manifest.json';m=json.loads(manifest.read_text());assert m['revision']=='independent-v12-candidate'
 assert not (game/'CW3_Data/Managed/CW3Debug.dll').exists(),'Disable debug first'
 for row in m['files']:assert sha((game/row['file']).read_bytes())==row['after'],'Installed file differs: '+row['file']
 result=subprocess.run(['pgrep','-fl','[C]W3[.]exe|[/]CW3[.]app/Contents/MacOS/Menu Helper'],capture_output=True,text=True);assert result.returncode==1,'Exit CW3 before updating: '+result.stdout
 n=validate(dictionary,font or game/'CW3Localization/font.ttf')
 if serif or style or m.get('controlled_fonts'):
  from text_style import validate_font,validate_style
  controlled=m.get('controlled_fonts');assert isinstance(controlled,dict) and set(controlled)=={'sans','serif'},'Build a controlled Text Style candidate first'
  validate_font(font or game/'CW3Localization/font.ttf','sans',controlled['sans'])
  validate_font(serif or game/'CW3Localization/serif.ttf','serif',controlled['serif'])
  registry_path=game/'CW3Localization/fonts.json'
  registered=__import__('font_registry').load(registry_path)['fonts'] if registry_path.exists() else {'sans','serif'}
  validate_style(style or game/'CW3Localization/text-style.json',registered)
 changes={'CW3Localization/zh-CN.json':dictionary}
 if font:changes['CW3Localization/font.ttf']=font
 if serif:changes['CW3Localization/serif.ttf']=serif
 if style:changes['CW3Localization/text-style.json']=style
 declared={f['file'] for f in m['files']};assert set(changes)<=declared,'Runtime file is absent from this installed version'
 # Keep the local install manifest and recovery output in sync with approved updates.
 # Original resources/assemblies are neither rebuilt nor written.
 backup=package/'runtime-update-backup';assert not backup.exists(),'Previous interrupted update needs inspection';backup.mkdir()
 shutil.copy2(manifest,backup/'manifest.json')
 for name in changes:
  for root,label in ((game,'installed'),(build,'build')):dst=backup/label/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dst)
 try:
  for name,source in changes.items():
   put(source,game/name);put(source,build/name)
   row=next(f for f in m['files']if f['file']==name);row['after']=sha(source.read_bytes());row['bytes']=source.stat().st_size
  temp=package/'manifest.runtime-update-tmp'
  try:
   temp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');os.replace(temp,manifest)
  finally:temp.unlink(missing_ok=True)
 except BaseException:
  for name in changes:
   for root,label in ((game,'installed'),(build,'build')):put(backup/label/name,root/name)
  put(backup/'manifest.json',manifest);raise
 else:shutil.rmtree(backup)
 print('Updated only '+', '.join(changes)+'; '+str(n)+' valid entries. Restart CW3; no resource/DLL rebuild.')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--dictionary',default=str(ROOT/'translations/zh-CN.json'));p.add_argument('--font');p.add_argument('--serif');p.add_argument('--style');p.add_argument('--check',action='store_true');a=p.parse_args();c=json.loads(Path(a.config).read_text());d=Path(a.dictionary);f=Path(a.font)if a.font else None;s=Path(a.serif)if a.serif else None;t=Path(a.style)if a.style else None
 if a.check:
  print('Validated',validate(d,f or location(c,'game')/'CW3Localization/font.ttf'),'entries')
  if t:__import__('text_style').validate_style(t)
  m=json.loads((location(c,'package')/'manifest.json').read_text())
  if m.get('controlled_fonts'):
   __import__('text_style').validate_font(f or location(c,'game')/'CW3Localization/font.ttf','sans',m['controlled_fonts']['sans'])
   __import__('text_style').validate_font(s or location(c,'game')/'CW3Localization/serif.ttf','serif',m['controlled_fonts']['serif'])
   __import__('text_style').validate_style(t or location(c,'game')/'CW3Localization/text-style.json')
  elif s:raise ValueError('Build a controlled Text Style candidate first')
 else:update(c,d,f,s,t)
if __name__=='__main__':main()
