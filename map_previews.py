"""Bounded, content-bound initial-header map previews. No body simulation or disk cache."""
from __future__ import annotations
import hashlib
import io
import math
import struct
import threading
import zlib
from collections import OrderedDict
from pathlib import Path

VERSION=1
MAX_COMPRESSED=16*1024*1024
MAX_EXPANDED=64*1024*1024
_LOCK=threading.Lock()
_SLOTS=threading.BoundedSemaphore(2)
_CACHE=OrderedDict()


def eligible_players(players):
    """Conservative automatic previews: explicit opposing 1v1 with one reported winner.

    Team resignation flags can identify a nominal winner before all teammates stop;
    do not automatically reveal those header maps while a recording may be active.
    """
    if not isinstance(players,list) or len(players)!=2 or sum(p.get('won') is True for p in players)!=1 or sum(p.get('won') is False for p in players)!=1: return False
    keys=[]
    for p in players:
        team=p.get('team_id')
        if isinstance(team,(list,tuple)):
            if len(team)!=1 or type(team[0]) is not int or team[0]!=p.get('id'): return False
            keys.append(('members',team[0]))
        elif type(team) is int and team>0: keys.append(('team',team))
        else:return False
    return keys[0][0]==keys[1][0] and keys[0]!=keys[1]


def _stamp(stat):
    return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)


def _header(handle):
    """Preflight bounded zlib before invoking the installed parser on header bytes only."""
    from mgz.fast import header as parser
    from mgz.util import Version
    prefix=handle.read(8)
    if len(prefix)!=8: raise ValueError('Map header unavailable.')
    length,_=struct.unpack('<II',prefix)
    if not 8<length<=MAX_COMPRESSED: raise ValueError('Map header exceeds preview limit.')
    compressed=handle.read(length-8);log=handle.read(4)
    if len(compressed)!=length-8 or len(log)!=4: raise ValueError('Incomplete map header.')
    decoder=zlib.decompressobj(-15)
    expanded=decoder.decompress(compressed,MAX_EXPANDED+1)
    if len(expanded)>MAX_EXPANDED or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise ValueError('Map header expansion unavailable or exceeds preview limit.')
    header=io.BytesIO(expanded)
    version,game,save,log_version=parser.parse_version(header,io.BytesIO(log))
    if version not in (Version.DE,Version.HD,Version.USERPATCH15): raise ValueError('Unsupported preview header version.')
    de=parser.parse_de(header,version,save);parser.parse_hd(header,version,save)
    _,players=parser.parse_metadata(header,save)
    if not 1<=players<=9: raise ValueError('Unsupported preview player count.')
    pos=header.tell()
    if version is Version.DE: header.read(8)
    width,height,zones=struct.unpack('<III',header.read(12));header.seek(pos)
    if not 1<=width<=480 or height!=width or zones>32: raise ValueError('Unsupported preview map dimensions.')
    map_=parser.parse_map(header,version,save)
    parsed_players,_,_=parser.parse_players(header,players,version,save)
    return {'version':version,'save_version':save,'de':de,'map':map_,'players':parsed_players}


def _render(data,sha):
    """Copy a sampled initial terrain grid; never replace unknown terrain IDs."""
    from mgz.fast import header
    map_=data['map'];dim=map_['dimension'];tiles=map_['tiles']
    if type(dim) is not int or not 1<=dim<=480 or len(tiles)!=dim*dim:
        raise ValueError('Map dimensions unavailable for preview.')
    step=max(1,math.ceil(dim/96));size=math.ceil(dim/step)
    terrain=[]
    for y in range(0,dim,step):
        for x in range(0,dim,step):
            value=tiles[y*dim+x][0]
            if type(value) is not int: raise ValueError('Invalid terrain identity.')
            terrain.append(value)
    starts=[]
    de_colors={p.get('number'):p.get('color_id') for p in (data.get('de') or {}).get('players',[]) if type(p.get('number')) is int and p['number']>0}
    for player in data.get('players',[]):
        p=player.get('position');number=player.get('number');color=de_colors.get(number) if data.get('de') else player.get('color_id')
        if not number or not isinstance(p,dict): continue
        x,y=p.get('x'),p.get('y')
        if all(type(v) in (int,float) and math.isfinite(v) for v in (x,y)) and 0<=x<dim and 0<=y<dim:
            starts.append({'player_id':number,'color_id':color if type(color) is int and 0<=color<=7 else None,'x':x,'y':y})
    return {'preview_version':VERSION,'match_id':sha,'dimension':dim,'sample_step':step,'grid_size':size,'terrain_ids':terrain,'starts':starts,
            'source':{'kind':'recorded_header_snapshot','adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'parser_header_sha256':hashlib.sha256(Path(header.__file__).read_bytes()).hexdigest(),
                      'edition':getattr(data.get('version'),'name',None),'build_version':(data.get('de') or {}).get('build'),
                      'save_version':data.get('save_version'),'restore_time_ms':map_.get('restore_time')},
            'limitations':'Stylized sampled recorded-header terrain and start positions; not live positions, explored area, traversability or a complete resource map.'}


def preview(path:Path,expected_sha:str,indexed_stamp:tuple[int,int]):
    if len(expected_sha)!=64 or any(c not in '0123456789abcdef' for c in expected_sha): raise ValueError('Invalid preview content identity.')
    path=Path(path)
    before=path.stat()
    if (before.st_size,before.st_mtime_ns)!=indexed_stamp: raise ValueError('Replay changed; refresh the library before requesting its map.')
    stamp=_stamp(before);key=(str(path.resolve()),expected_sha,stamp,VERSION)
    with _LOCK:
        if key in _CACHE:
            result=_CACHE[key];_CACHE.move_to_end(key);return result
    if not _SLOTS.acquire(timeout=5): raise ValueError('Map preview busy; try again later.')
    try:
        with path.open('rb') as handle:
            import os
            if _stamp(os.fstat(handle.fileno()))!=stamp: raise ValueError('Replay changed while opening map header.')
            sha=hashlib.file_digest(handle,'sha256').hexdigest()
            if sha!=expected_sha: raise ValueError('Replay content changed; refresh the library.')
            handle.seek(0);data=_header(handle)
            if _stamp(os.fstat(handle.fileno()))!=stamp or _stamp(path.stat())!=stamp: raise ValueError('Replay changed while reading map header.')
        result=_render(data,sha)
        with _LOCK:
            _CACHE[key]=result;_CACHE.move_to_end(key)
            while len(_CACHE)>128:_CACHE.popitem(last=False)
        return result
    finally:_SLOTS.release()
