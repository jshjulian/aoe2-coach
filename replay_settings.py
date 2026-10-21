"""Private startup-only replay folder selection. Reads JSON, never executes or rewrites it."""
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEFAULT_CONFIG=ROOT/'agewise.local.json'


def _directories(values,base):
    if not isinstance(values,list) or len(values)>16 or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in values):
        raise ValueError('replay_directories must be a list of up to 16 nonempty folder paths.')
    result=[]
    for value in values:
        path=Path(value).expanduser()
        if not path.is_absolute():path=base/path
        path=path.resolve()
        if not path.is_dir():raise ValueError(f'Replay folder does not exist: {path}. On WSL use /mnt/c/... rather than a Windows drive path.')
        if path not in result:result.append(path)
    return result


def select_directories(cli=None,config=None,*,environment=None,default_config=None,cwd=None):
    """Precedence: repeated CLI --replays > environment > explicit/default JSON > discovery.

    None means auto-discover; [] explicitly selects no folders. Empty existing folders
    are valid. A bad configured path is an error, never fallback to another user's saves.
    """
    environment=os.environ if environment is None else environment
    cwd=Path.cwd() if cwd is None else Path(cwd)
    if cli is not None:return _directories([str(v) for v in cli],cwd),'command line'
    env=environment.get('AOE2_REPLAY_DIR')
    if env:
        values=[v for v in env.split(os.pathsep) if v]
        return _directories(values,cwd),'AOE2_REPLAY_DIR'
    path=Path(config).expanduser() if config is not None else Path(default_config or DEFAULT_CONFIG)
    if not path.is_absolute():path=cwd/path
    if not path.exists():
        if config is not None:raise ValueError(f'Local settings file not found: {path}')
        return None,'auto-discovery'
    with path.open('rb') as handle:raw=handle.read(65537)
    if len(raw)>65536:raise ValueError('Local settings file exceeds 64 KiB.')
    try:settings=json.loads(raw)
    except (ValueError,UnicodeError) as exc:raise ValueError('Local settings must contain valid JSON; existing settings were not changed.') from exc
    if not isinstance(settings,dict) or set(settings)!={'version','replay_directories'} or type(settings['version']) is not int or settings['version']!=1:
        raise ValueError('Local settings require exactly version: 1 and replay_directories.')
    return _directories(settings['replay_directories'],path.resolve().parent),'local settings'
