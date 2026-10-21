import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from replay_settings import select_directories


class ReplaySettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.saves=self.root/'Save games with spaces';self.saves.mkdir()
        self.other=self.root/'Other';self.other.mkdir();self.config=self.root/'agewise.local.json'

    def select(self,cli=None,config=None,environment=None):
        return select_directories(cli,config,environment={} if environment is None else environment,default_config=self.config,cwd=self.root)

    def write(self,dirs):self.config.write_text(json.dumps({'version':1,'replay_directories':dirs}))

    def test_absent_config_keeps_discovery(self):self.assertEqual(self.select(),(None,'auto-discovery'))
    def test_empty_existing_folder_is_supported(self):
        self.write([str(self.saves)]);self.assertEqual(self.select()[0],[self.saves])
    def test_relative_config_paths_resolve_next_to_config(self):
        self.write(['Save games with spaces']);self.assertEqual(self.select()[0],[self.saves])
    def test_empty_selection_does_not_fall_back_to_discovery(self):
        self.write([]);self.assertEqual(self.select()[0],[])
        from app import ReplayLibrary
        library=ReplayLibrary();library.configure([])
        with patch('app.discover_replay_directories',side_effect=AssertionError('No fallback')):self.assertEqual(library.folders(),[])
    def test_cli_overrides_environment_and_config(self):
        self.write(['/missing'])
        self.assertEqual(self.select([self.saves],environment={'AOE2_REPLAY_DIR':'/missing'})[0],[self.saves])
    def test_environment_overrides_config_and_keeps_multiple_paths(self):
        self.write(['/missing']);env={'AOE2_REPLAY_DIR':os.pathsep.join([str(self.other),str(self.saves)])}
        self.assertEqual(self.select(environment=env)[0],[self.other,self.saves])
    def test_repeated_cli_paths_deduplicate_and_keep_order(self):
        self.assertEqual(self.select([self.other,self.saves,self.other])[0],[self.other,self.saves])
    def test_missing_folder_is_an_error_not_discovery_or_mkdir(self):
        self.write(['missing'])
        with self.assertRaises(ValueError):self.select()
        self.assertFalse((self.root/'missing').exists())
    def test_blank_cli_path_is_not_the_current_directory(self):
        with self.assertRaises(ValueError):self.select([''])
    def test_missing_explicit_config_is_an_error(self):
        with self.assertRaises(ValueError):self.select(config=self.root/'missing.json')
    def test_corrupt_or_unsupported_config_is_not_repaired(self):
        for raw in ['broken','null','{}','{"version":true,"replay_directories":[]}','{"version":2,"replay_directories":[]}','{"version":1,"replay_directories":[null]}','{"version":1,"replay_directories":[],"extra":1}']:
            self.config.write_text(raw)
            with self.assertRaises(ValueError):self.select()
            self.assertEqual(self.config.read_text(),raw)
    def test_oversize_config_rejected(self):
        self.config.write_text(' '*65537)
        with self.assertRaises(ValueError):self.select()
    def test_explicit_discovery_accepts_empty_folder(self):
        from app import discover_replay_directories
        self.assertEqual(discover_replay_directories(self.saves),[self.saves])

if __name__=='__main__':unittest.main()
