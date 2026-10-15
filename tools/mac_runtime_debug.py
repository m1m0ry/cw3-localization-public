"""Control the fixed diagnostics endpoint in the external native Mac runtime."""
from pathlib import Path
import json
import os
import re
import tempfile
import time
import uuid

import player_install as player

RUNTIME='CW3Localization/Runtime/CW3ExternalRuntime.dll'
COMMANDS={'runtime_probe','style_probe','font_probe','settings_native_open','settings_open',
          'settings_probe','settings_change','settings_save','settings_cancel',
          'settings_defaults','screenshot','display_probe','fonts_probe','fallback_probe',
          'prelude_preview','preview_return','quit','audio_probe'}


def context(game,state):
    if state is None or state.name!='CW3Localization' or not (state/'font-status.json').is_file():
        raise RuntimeError('Pass the existing Unity persistentDataPath/CW3Localization with --state')
    if state.is_symlink():raise RuntimeError('Persistent state path is linked')
    installed=player.read(game/player.BACKUP/'state.json')
    if player.target_layout(installed)['target_id']!=player.MACOS:raise RuntimeError('Installed player is not native Mac')
    rows={row['file']:row for row in installed['files']}
    if RUNTIME not in rows:raise RuntimeError('The bridge candidate is not installed')
    runtime=player.installed_path(game,RUNTIME,installed)
    if runtime.is_symlink() or not runtime.is_file() or player.digest(runtime)!=rows[RUNTIME]['after']:
        raise RuntimeError('External runtime differs from installed candidate')
    folder=state/'cw3-debug'
    if folder.is_symlink():raise RuntimeError('Diagnostics directory is linked')
    return runtime,folder,rows[RUNTIME]['after']


def action(game,state,args,evidence_root):
    runtime,folder,expected=context(game,state)
    mode=args[0]
    marker=folder/'enabled.txt'
    if mode in ('enable','disable'):
        player.idle()
        if mode=='enable':
            folder.mkdir(exist_ok=True)
            if marker.exists() or marker.is_symlink():raise RuntimeError('Diagnostics marker already exists')
            with marker.open('x') as output:output.write(expected+'\n')
            marker.chmod(0o600)
        else:
            if marker.is_symlink() or not marker.is_file() or marker.read_text().strip()!=expected:
                raise RuntimeError('Diagnostics marker is missing or changed')
            marker.unlink()
            request=folder/'request.txt'
            if request.exists() and not request.is_symlink():
                request.rename(folder/('request-retained-'+uuid.uuid4().hex+'.txt'))
        print(json.dumps({'mode':mode,'runtime_sha256':expected,'marker_present':marker.exists()}))
        return
    if mode!='command' or len(args)<2:raise ValueError('Expected enable, disable or command NAME')
    if marker.is_symlink() or not marker.is_file() or marker.read_text().strip()!=expected:
        raise RuntimeError('Diagnostics are not enabled for this runtime')
    command=args[1];arg=args[2] if len(args)>2 else ''
    if len(args)>3 or command not in COMMANDS:raise ValueError('Command not allowed')
    if command=='settings_change':
        if re.fullmatch(r'(body|title|ui|status)\|(sans|serif)\|(75|80|85|90|95|100|105|110|115|120|125|130|135|140|145|150)',arg) is None:
            raise ValueError('Invalid style setting')
    elif arg:raise ValueError('Unexpected command argument')
    request=folder/'request.txt'
    if request.exists() or request.is_symlink():raise RuntimeError('A diagnostics request is outstanding')
    ident=uuid.uuid4().hex
    fd,name=tempfile.mkstemp(prefix='.request-',suffix='.tmp',dir=folder)
    temp=Path(name)
    try:
        with os.fdopen(fd,'w') as output:output.write('\t'.join([ident,command,arg]).rstrip('\t')+'\n')
        os.replace(temp,request)
    finally:temp.unlink(missing_ok=True)
    for _ in range(40):
        response=folder/'response.json'
        if response.exists():
            if response.is_symlink():raise RuntimeError('Diagnostics response is linked')
            try:result=json.loads(response.read_text())
            except json.JSONDecodeError:result={}
            if result.get('id')==ident:
                evidence_root.mkdir(parents=True,exist_ok=True)
                evidence=evidence_root/('debug-'+ident+'.json')
                evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps({'result_path':str(evidence),'ok':result.get('ok'),
                                  'result_summary':result.get('error',result.get('result'))},ensure_ascii=False))
                return
        time.sleep(.25)
    raise TimeoutError('Game did not acknowledge; request retained, do not blindly repeat')
