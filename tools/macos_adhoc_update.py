"""Guarded update of an already installed, valid ad-hoc native Mac candidate.

This is a local development entry point. It never changes Gatekeeper settings or
quarantine. The first signed installation requires a separate reviewed route;
this tool accepts only an installer-managed old candidate whose current bundle
has a valid ad-hoc signature. A retained snapshot can restore that old candidate.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import sys

import player_install as player

SNAPSHOT='adhoc-bridge-previous'
SIGNATURE='CW3.app/Contents/_CodeSignature/CodeResources'
ADDED='CW3Localization/Runtime/CW3ExternalRuntime.dll'
EXTERNAL_UPDATE={ADDED,'CW3Localization/fonts.json','CW3Localization/zh-CN.json'}


def external_only(changed):
    return bool(changed) and set(changed)<=EXTERNAL_UPDATE


def recovery_folder(game,new,external=False,initial=False):
    if initial:return game/player.BACKUP/SNAPSHOT
    version=new['version']
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',version):
        raise RuntimeError('Update version is not a safe recovery name')
    return game/player.BACKUP/(('external-' if external else 'adhoc-')+version)


def saved_path(folder,name):
    if name not in (player.TARGETS[player.MACOS]['executable'],SIGNATURE):
        return player.safe(folder/'files',name)
    return folder/'files'/name


def signature(game):
    app=game/'CW3.app'
    seal=game/SIGNATURE
    if app.is_symlink() or seal.is_symlink() or not seal.is_file():
        raise RuntimeError('CW3.app signature layout is missing or linked')
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],
                   check=True,capture_output=True,text=True,timeout=120)
    result=subprocess.run(['codesign','--display','--verbose=2',str(app)],
                          check=True,capture_output=True,text=True,timeout=120)
    if 'flags=0x2(adhoc)' not in result.stdout+result.stderr:
        raise RuntimeError('CW3.app does not have the expected ad-hoc signature')
    return dict(deep=True)


def load_package(folder):
    folder=folder.resolve(strict=True)
    manifest=player.read(folder/'manifest.json')
    if manifest.get('format')!=2 or player.target_layout(manifest)['target_id']!=player.MACOS:
        raise RuntimeError('Expected a complete native Mac package')
    if len(manifest['files']) not in (14,15) or len({row['file'] for row in manifest['files']})!=len(manifest['files']):
        raise RuntimeError('Unexpected native package file list')
    names={row['file'] for row in manifest['files']}
    if (len(names)==15)!=(ADDED in names):
        raise RuntimeError('Unexpected native external runtime layout')
    for row in manifest['files']:
        if player.digest(player.safe(folder,row['file']))!=row['after']:
            raise RuntimeError('Package payload hash mismatch: '+row['file'])
    return folder,manifest


def preflight(game,old_folder,new_folder):
    game=game.resolve(strict=True)
    old_folder,old=load_package(old_folder)
    new_folder,new=load_package(new_folder)
    if player.target_identity(old)!=player.target_identity(new):
        raise RuntimeError('Packages target different native players')
    old_rows={row['file']:row for row in old['files']}
    new_rows={row['file']:row for row in new['files']}
    added=set(new_rows)-set(old_rows)
    if set(old_rows)-set(new_rows) or added not in (set(),{ADDED}) or any(old_rows[name]['before']!=row['before'] for name,row in new_rows.items() if name in old_rows) or any(new_rows[name]['before'] is not None for name in added):
        raise RuntimeError('Update changes the guarded installation file set or original bases')
    state=player.read(game/player.BACKUP/'state.json')
    if player.target_identity(state)!=player.target_identity(old) or state['version']!=old['version']:
        raise RuntimeError('Current backup does not belong to the old package')
    if player.status(game,old,state)!='installed':
        raise RuntimeError('Current installed payload or backup metadata differs from the old package')
    for row in state['files']:
        if row['before'] and player.digest(player.safe(game/player.BACKUP/'original',row['file']))!=row['before']:
            raise RuntimeError('Original backup hash mismatch: '+row['file'])
    if not player.required_originals_match(game,new):
        raise RuntimeError('New package requires different untouched original files')
    exe=game/old['executable']
    if exe.is_symlink() or not exe.is_file():raise RuntimeError('Native executable missing or linked')
    signed=signature(game)
    for name in added:
        if player.installed_path(game,name,new).exists():
            raise RuntimeError('New external runtime path already exists')
    changed=[name for name,row in new_rows.items() if name in added or row['after']!=old_rows[name]['after']]
    if recovery_folder(game,new,external_only(changed),ADDED not in old_rows).exists():
        raise RuntimeError('Previous update snapshot exists; inspect or recover it first')
    return game,old_folder,old,new_folder,new,state,changed,signed


def snapshot(game,old,new,state,changed,signed):
    external=external_only(changed)
    folder=recovery_folder(game,new,external,ADDED not in {row['file'] for row in old['files']})
    folder.mkdir()  # exclusive: never replace a recovery point
    paths=[*changed,old['executable'],SIGNATURE]
    try:
        records=[]
        old_names={row['file'] for row in old['files']}
        new_rows={row['file']:row for row in new['files']}
        for name in paths:
            if name not in old_names and name==ADDED:
                records.append(dict(file=name,absent=True,after_sha256=new_rows[name]['after']))
                continue
            target=player.installed_path(game,name,old) if name.startswith('CW3_Data/') else game/name
            if not target.is_file() or target.is_symlink():raise RuntimeError('Snapshot source missing or linked: '+name)
            saved=saved_path(folder,name)
            saved.parent.mkdir(parents=True,exist_ok=True)
            player.atomic_copy(target,saved)
            records.append(dict(file=name,sha256=player.digest(target),metadata=player.metadata(target),
                                after_sha256=new_rows[name]['after'] if name in new_rows else player.digest(target)))
        player.atomic_copy(game/player.BACKUP/'state.json',folder/'state.json')
        player.put_json(folder/'record.json',dict(format=1,old_version=old['version'],files=records,signature=signed,external_only=external,
                                                  state_sha256=player.digest(folder/'state.json'),phase='ready'))
        return folder
    except BaseException:
        # Keep any partial snapshot for inspection. No game bytes changed yet.
        raise


def progress(folder,phase,in_progress=()):
    player.put_json(folder/'record.json',dict(player.read(folder/'record.json'),phase=phase,in_progress=list(in_progress)))


def retain_dictionary(folder,target):
    if target.stat().st_size>50000000:raise RuntimeError('Edited dictionary is too large; retain it manually before recovery')
    history=folder/'user-retained'
    if history.is_symlink():raise RuntimeError('Dictionary retention directory is linked')
    history.mkdir(exist_ok=True)
    expected=player.digest(target);saved=history/(expected+'-'+target.name)
    if saved.is_symlink():raise RuntimeError('Retained dictionary is linked')
    if not saved.exists():player.atomic_copy(target,saved)
    if player.digest(saved)!=expected:raise RuntimeError('Retained dictionary hash mismatch')
    raise RuntimeError('Edited dictionary retained at '+str(saved)+'; current file changed, recovery refused')


def recover(game,folder):
    player.idle()
    record=player.read(folder/'record.json')
    if record.get('format')!=1 or player.digest(folder/'state.json')!=record.get('state_sha256'):
        raise RuntimeError('Update recovery record or old installer state is invalid')
    old_state=player.read(folder/'state.json')
    # Old applied snapshots did not carry destination hashes. Their matching
    # installed state is the only additional trusted source of those hashes.
    current=player.read(game/player.BACKUP/'state.json')
    installed={}
    if record.get('new_version')==current.get('version') and player.target_identity(current)==player.target_identity(old_state):
        installed={r['file']:r['after'] for r in current['files']}
        installed[old_state['executable']]=current.get('adhoc_exe_sha256')
        installed[SIGNATURE]=current.get('adhoc_seal_sha256')
    pending=record.get('in_progress',[])
    if not isinstance(pending,list) or set(pending)-{r['file'] for r in record['files'] if not r.get('absent')}:
        raise RuntimeError('Invalid interrupted update file list')
    if pending and record.get('phase') not in ('writing','signing','restoring'):
        raise RuntimeError('Invalid interrupted update phase')
    for row in record['files']:
        if row.get('absent'):
            target=player.installed_path(game,row['file'],old_state)
            if target.is_symlink() or player.digest(target) not in (None,row['after_sha256']):
                raise RuntimeError('Added runtime changed before recovery')
            continue
        target=game/row['file'] if row['file'] in (player.TARGETS[player.MACOS]['executable'],SIGNATURE) else player.installed_path(game,row['file'],player.read(folder/'state.json'))
        saved=saved_path(folder,row['file'])
        if player.digest(saved)!=row['sha256'] or not target.is_file() or target.is_symlink():
            raise RuntimeError('Update recovery source or target changed: '+row['file'])
        known={row['sha256'],row.get('after_sha256'),installed.get(row['file'])}-{None}
        partial=row['file'] in pending and player.recoverable_metadata_matches(player.metadata(target),row['metadata'])
        if player.digest(target) not in known and not partial:
            if row['file'] in player.RUNTIME:retain_dictionary(folder,target)
            raise RuntimeError('Update recovery target changed; refusing to overwrite: '+row['file'])
    for row in record['files']:
        if row.get('absent'):
            target=player.installed_path(game,row['file'],old_state)
            if target.exists():
                retained=folder/'added-retained'/row['file']
                retained.parent.mkdir(parents=True,exist_ok=True)
                if retained.exists():raise RuntimeError('Retained added runtime already exists')
                os.replace(target,retained)
                player.sync_directory(target.parent)
            continue
        name=row['file']
        target=game/name if name in (player.TARGETS[player.MACOS]['executable'],SIGNATURE) else player.installed_path(game,name,player.read(folder/'state.json'))
        if player.digest(target)!=row['sha256']:
            progress(folder,'restoring',sorted(set(pending)|{name}))
            player.write_existing(saved_path(folder,name),target,row['metadata'])
        pending=[item for item in pending if item!=name]
        progress(folder,'restoring',pending)
    if any(player.digest(game/r['file'] if r['file'] in (player.TARGETS[player.MACOS]['executable'],SIGNATURE) else player.installed_path(game,r['file'],old_state))!=r['sha256'] for r in record['files'] if not r.get('absent')):
        raise RuntimeError('Old signed candidate bytes were not restored')
    if signature(game)!=record['signature']:
        raise RuntimeError('Recovered signature conditions differ from the prior candidate')
    player.atomic_copy(folder/'state.json',game/player.BACKUP/'state.json')
    player.put_json(folder/'record.json',dict(player.read(folder/'record.json'),phase='recovered',in_progress=[]))
    print('Restored and verified the preceding ad-hoc candidate. Recovery snapshot retained:',folder)


def apply(game,old_folder,new_folder):
    player.idle()
    game,old_folder,old,new_folder,new,state,changed,signed=preflight(game,old_folder,new_folder)
    if not changed:
        print('New package has identical payload bytes; no re-signing needed.')
        return
    folder=snapshot(game,old,new,state,changed,signed)
    try:
        player.idle()
        if player.status(game,old,state)!='installed':raise RuntimeError('Old payload changed during staging')
        if signature(game)!=signed:raise RuntimeError('Signed bundle changed during staging')
        records=player.read(folder/'record.json')['files']
        if any(player.digest((game/r['file'] if r['file'] in (player.TARGETS[player.MACOS]['executable'],SIGNATURE) else player.installed_path(game,r['file'],old)))!=r['sha256'] for r in records if not r.get('absent')):
            raise RuntimeError('Signed bundle changed during staging')
        new_rows={row['file']:dict(row) for row in new['files']}
        old_rows={row['file']:row for row in state['files']}
        for name in changed:
            target=player.installed_path(game,name,new)
            if name==ADDED and name not in old_rows:
                if target.exists() or target.is_symlink():raise RuntimeError('New runtime appeared during staging')
                target.parent.mkdir(exist_ok=False)
                player.atomic_copy(player.safe(new_folder,name),target)
                target.chmod(0o644)
            else:
                before=old_rows[name]
                if not player.row_matches(game,before,'after',state):raise RuntimeError('Current file changed: '+name)
                progress(folder,'writing',[name])
                player.write_existing(player.safe(new_folder,name),target,before['after_metadata'])
                progress(folder,'applying')
            new_rows[name]['after_metadata']=player.metadata(target)
        if not external_only(changed):
            progress(folder,'signing',[old['executable'],SIGNATURE])
            subprocess.run(['codesign','--force','--sign','-',str(game/'CW3.app')],
                           check=True,capture_output=True,text=True,timeout=120)
            record=player.read(folder/'record.json')
            for row in record['files']:
                if row['file'] in (old['executable'],SIGNATURE):row['after_sha256']=player.digest(game/row['file'])
            player.put_json(folder/'record.json',dict(record,phase='applying',in_progress=[]))
        elif any(player.digest(game/r['file'])!=r['sha256'] for r in records if r['file'] in (old['executable'],SIGNATURE)):
            raise RuntimeError('External update changed signed executable or seal')
        if signature(game)!=signed:raise RuntimeError('Signature conditions changed during re-signing')
        for name,row in new_rows.items():
            row['before_metadata']=old_rows[name]['before_metadata'] if name in old_rows else None
            if name not in changed:row['after_metadata']=old_rows[name]['after_metadata']
        updated=dict(state,version=new['version'],files=[new_rows[row['file']] for row in new['files']],
                     adhoc_exe_sha256=player.digest(game/new['executable']),
                     adhoc_seal_sha256=player.digest(game/SIGNATURE))
        if player.status(game,new,updated)!='installed':raise RuntimeError('New payload failed post-sign verification')
        player.put_json(game/player.BACKUP/'state.json',updated)
        player.put_json(folder/'record.json',dict(player.read(folder/'record.json'),phase='applied',in_progress=[],
                                                  new_version=new['version']))
        print('Updated',len(changed),'changed payload files; ad-hoc signature structure verified.')
        if external_only(changed):print('Only external runtime/data changed; no signing command was run.')
        else:print('macOS may require a new app-specific approval in System Settings before launch.')
        print('Old signed candidate recovery snapshot:',folder)
    except BaseException:
        print('Update failed; restoring the preceding signed candidate.',file=sys.stderr)
        recover(game,folder)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,required=True)
    parser.add_argument('--old-package',type=Path)
    parser.add_argument('--new-package',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--recover',action='store_true')
    args=parser.parse_args()
    if args.recover:
        if args.apply or args.old_package:parser.error('--recover does not accept --apply or --old-package')
        game=args.game.resolve(strict=True)
        folder=game/player.BACKUP/SNAPSHOT
        if args.new_package:
            new=load_package(args.new_package)[1]
            choices=[recovery_folder(game,new,side) for side in (False,True)]
            choices=[path for path in choices if path.is_dir()]
            if len(choices)!=1:raise RuntimeError('Expected one retained recovery snapshot for that package version')
            folder=choices[0]
        recover(game,folder)
        return
    if not args.old_package or not args.new_package:parser.error('both package directories are required')
    if args.apply:apply(args.game,args.old_package,args.new_package)
    else:
        result=preflight(args.game,args.old_package,args.new_package)
        print('Ready for guarded update:',len(result[-2]),'changed payload files. Game unchanged.')
        print('External-only update; no re-signing required.' if external_only(result[-2]) else 'Apply only after the game has fully exited. Re-signing may require a new System Settings approval.')


if __name__=='__main__':main()
