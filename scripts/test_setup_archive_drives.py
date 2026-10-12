"""Safety checks only. No formatting, mounting, or system-file writes are executed."""
import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('drive_setup', Path(__file__).with_name('setup-archive-drives.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class DriveSetupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'name':'/dev/sda2','type':'part','size':1_000_000_000_000,'uuid':setup.ROOT_UUID,
                      'physical_disk':'/dev/sda','mountpoints':['/'],'partuuid':'system','fstype':'ext4'}]
        self.links = {}
        for n, identifier in enumerate(setup.PARTITIONS):
            name = '/dev/' + ['sdb2','sdc2','sdd2'][n]
            disk = name[:-1]
            self.rows += [{'name':disk,'type':'disk','size':2_000_000_000_000,'physical_disk':disk,'mountpoints':[None]},
                          {'name':name,'type':'part','size':1_999_000_000_000,'uuid':None,'physical_disk':disk,
                           'mountpoints':[None],'partuuid':identifier,'fstype':None,'ro':False}]
            self.links['/dev/disk/by-partuuid/'+identifier] = Path(name)
        for item in [patch.object(setup,'run',return_value=setup.ROOT_UUID),
                     patch.object(Path,'is_dir',return_value=True), patch.object(Path,'iterdir',return_value=iter(())),
                     patch.object(Path,'exists',return_value=True),
                     patch.object(Path,'resolve',autospec=True,side_effect=lambda p:self.links.get(str(p),p))]:
            item.start(); self.addCleanup(item.stop)
    def targets(self):
        return [r for r in self.rows if r.get('partuuid') in setup.PARTITIONS]
    def test_exact_three_approved_large_partitions(self):
        targets = setup.inspect(self.rows)
        self.assertEqual([r['partuuid'] for r in targets],list(setup.PARTITIONS))
        self.assertNotIn('/dev/sda',{r['physical_disk'] for r in targets})
    def test_os_disk_can_never_be_a_target(self):
        self.targets()[0]['physical_disk'] = '/dev/sda'
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_two_partitions_on_one_disk_are_rejected(self):
        self.targets()[1]['physical_disk'] = self.targets()[0]['physical_disk']
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_mounted_target_or_swap_is_rejected(self):
        for value in ['/mnt/data','[SWAP]']:
            with self.subTest(value=value):
                rows = copy.deepcopy(self.rows)
                rows[2]['mountpoints'] = [value]
                with self.assertRaises(RuntimeError): setup.inspect(rows)
    def test_mounted_sibling_is_rejected(self):
        self.rows.append({'name':'/dev/sdb1','physical_disk':'/dev/sdb','type':'part','mountpoints':['/mnt/other']})
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_active_block_holder_is_rejected(self):
        with patch.object(Path,'iterdir',return_value=iter([Path('dm-0')])):
            with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_already_formatted_ext4_is_rejected(self):
        self.targets()[0]['fstype'] = 'ext4'
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_small_reserved_partition_is_rejected(self):
        self.targets()[0]['size'] = 128 * 1024**2
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_missing_or_duplicate_partition_id_is_rejected(self):
        for rows in [self.rows[:-1],self.rows+[copy.deepcopy(self.targets()[0])]]:
            with self.assertRaises(RuntimeError): setup.inspect(rows)
    def test_persistent_symlink_identity_must_match(self):
        self.links['/dev/disk/by-partuuid/'+setup.PARTITIONS[0]] = Path('/dev/sda2')
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_wrong_os_uuid_is_rejected(self):
        with patch.object(setup,'run',return_value='another-server'):
            with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_read_only_target_is_rejected(self):
        self.targets()[0]['ro'] = True
        with self.assertRaises(RuntimeError): setup.inspect(self.rows)
    def test_default_mode_never_calls_apply(self):
        with patch.object(sys,'argv',['setup-archive-drives.py']),patch.object(setup,'preflight',return_value='fstab'),patch.object(setup,'inventory',return_value=self.rows),patch.object(setup,'apply') as apply:
            self.assertEqual(setup.main(),0)
            apply.assert_not_called()
    def test_wrong_confirmation_never_formats_or_creates_backups(self):
        with patch.object(setup.os,'geteuid',return_value=0),patch('builtins.input',return_value='NO'),patch.object(setup.subprocess,'run') as run,patch.object(Path,'mkdir') as mkdir:
            with self.assertRaises(RuntimeError): setup.apply(self.targets(),'fstab')
            run.assert_not_called()
            mkdir.assert_not_called()

    def test_manifest_is_readable_by_container_group_without_world_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'drives.json'
            with patch.object(setup, 'REPO', Path(temporary)), patch.object(setup.os, 'chown') as chown:
                setup.write_new(path, '[]\n', app_readable=True)
                chown.assert_called_once_with(path, Path(temporary).stat().st_uid, 10001)
            self.assertEqual(path.read_text(), '[]\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

if __name__ == '__main__':
    unittest.main()
