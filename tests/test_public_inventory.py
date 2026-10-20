"""Archive allowlist rejects extra, missing and modified runtime source."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_inventory',ROOT/'tools/check_public.py')
inventory=importlib.util.module_from_spec(spec);spec.loader.exec_module(inventory)

class PublicInventory(unittest.TestCase):
    def test_historical_snapshot_unchanged(self):
        if not (ROOT/'legacy').exists():self.skipTest('historical snapshot is repository-only')
        self.assertEqual(inventory.snapshot(),57)
    def test_wheel_cannot_add_or_modify_runtime_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('smb_voice_bench/injected.py','smb_voice_bench/__init__.py'):
                with zipfile.ZipFile(Path(tmp)/'test.whl','w') as z:z.writestr(name,b'changed')
                with self.assertRaises(ValueError):inventory.archives(tmp,{'src/smb_voice_bench/__init__.py'})
    def test_source_archive_cannot_include_history_or_omit_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('legacy/fixture-pack-v1/package.json','PKG-INFO'):
                with tarfile.open(Path(tmp)/'test.tar.gz','w:gz') as tar:
                    item=tarfile.TarInfo('smb_voice_bench-0.1.0/'+name);item.size=2;tar.addfile(item,io.BytesIO(b'{}'))
                with self.assertRaises(ValueError):inventory.archives(tmp,{'README.md'})
