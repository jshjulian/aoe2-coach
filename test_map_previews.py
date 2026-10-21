import hashlib
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
import map_previews as maps


def data(dim=2):
    return {'map':{'dimension':dim,'tiles':[(12,0)]*(dim*dim),'restore_time':0},'players':[], 'de':{}}


class MapPreviewTests(unittest.TestCase):
    def setUp(self):
        maps._CACHE.clear()

    def test_sampled_grid_is_bounded_and_retains_unknown_terrain(self):
        d=data(120);d['map']['tiles'][0]=(-1,0)
        p=maps._render(d,'a'*64)
        self.assertEqual((p['grid_size'],p['sample_step']),(60,2))
        self.assertEqual(p['terrain_ids'][0],-1)
        self.assertEqual(len(p['terrain_ids']),3600)
        self.assertEqual(p['source']['kind'],'recorded_header_snapshot')

    def test_bad_dimensions_and_partial_grids_withhold_preview(self):
        for d in [data(0),data(481),{'map':{'dimension':2,'tiles':[]}}]:
            with self.assertRaises(ValueError): maps._render(d,'a'*64)

    def test_start_markers_bind_de_slot_number_not_broken_legacy_color(self):
        d=data();d['de']={'players':[{'number':1,'color_id':0}]};d['players']=[{'number':1,'color_id':70,'position':{'x':1,'y':1}},{'number':2,'color_id':0,'position':{'x':0,'y':1}}]
        p=maps._render(d,'a'*64)
        self.assertEqual([s['color_id'] for s in p['starts']],[0,None])
        self.assertEqual([s['player_id'] for s in p['starts']],[1,2])

    def test_compressed_header_and_expansion_limits(self):
        with self.assertRaises(ValueError): maps._header(io.BytesIO(struct.pack('<II',maps.MAX_COMPRESSED+1,0)))
        obj=zlib.compressobj(wbits=-15);compressed=obj.compress(b'0'*1024)+obj.flush()
        raw=struct.pack('<II',8+len(compressed),0)+compressed+struct.pack('<I',5)
        with patch.object(maps,'MAX_EXPANDED',32):
            with self.assertRaises(ValueError): maps._header(io.BytesIO(raw))

    def test_map_dimensions_checked_before_parser_tile_allocation(self):
        from mgz.fast import header
        from mgz.util import Version
        body=b'\0'*8+struct.pack('<III',481,481,1)
        obj=zlib.compressobj(wbits=-15);compressed=obj.compress(body)+obj.flush();raw=struct.pack('<II',8+len(compressed),0)+compressed+struct.pack('<I',5)
        with patch.object(header,'parse_version',return_value=(Version.DE,'VER 9.4',68.9,5)),patch.object(header,'parse_de',return_value={}),patch.object(header,'parse_hd'),patch.object(header,'parse_metadata',return_value=({},3)),patch.object(header,'parse_map') as parser:
            with self.assertRaises(ValueError): maps._header(io.BytesIO(raw))
            parser.assert_not_called()

    def test_cache_is_memory_only_and_source_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.aoe2record';p.write_bytes(b'example');s=p.stat();sha=hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.object(maps,'_header',return_value=data()) as header:
                a=maps.preview(p,sha,(s.st_size,s.st_mtime_ns));b=maps.preview(p,sha,(s.st_size,s.st_mtime_ns));self.assertEqual(a,b);self.assertEqual(header.call_count,1)
            self.assertEqual([x.name for x in Path(tmp).iterdir()],['test.aoe2record'])

    def test_wrong_hash_or_changed_index_stamp_is_rejected_before_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.aoe2record';p.write_bytes(b'example');s=p.stat()
            with patch.object(maps,'_header') as header:
                with self.assertRaises(ValueError): maps.preview(p,'a'*64,(s.st_size,s.st_mtime_ns))
                with self.assertRaises(ValueError): maps.preview(p,hashlib.sha256(b'example').hexdigest(),(1,s.st_mtime_ns))
                header.assert_not_called()

    def test_library_withholds_previews_for_unconfirmed_recordings(self):
        from app import ReplayLibrary
        library=ReplayLibrary()
        library._rows['test']={'game_id':'test','file':'test.aoe2record','modified_timestamp':0,'status':'ready','match_id':'a'*64,'players':[{'id':1,'won':False},{'id':2,'won':False}],'_path':Path('not-read'),'_size_bytes':0,'_mtime_ns':0}
        self.assertIsNone(library.preview_entry('test'))
        self.assertIs(library.games()[0]['map_preview_available'],False)
        self.assertTrue(maps.eligible_players([{'id':1,'team_id':[1],'won':True},{'id':2,'team_id':[2],'won':False}]))
        self.assertFalse(maps.eligible_players([{'id':1,'team_id':[1,2],'won':True},{'id':2,'team_id':[1,2],'won':True},{'id':3,'team_id':[3,4],'won':False},{'id':4,'team_id':[3,4],'won':False}]))

    def test_file_change_during_header_read_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.aoe2record';p.write_bytes(b'example');s=p.stat();sha=hashlib.sha256(b'example').hexdigest()
            def changed(_): p.write_bytes(b'changed size');return data()
            with patch.object(maps,'_header',side_effect=changed):
                with self.assertRaises(ValueError): maps.preview(p,sha,(s.st_size,s.st_mtime_ns))
            self.assertFalse(maps._CACHE)

if __name__=='__main__': unittest.main()
