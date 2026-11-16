import contextlib
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import submarine_designs as subs
import save_cheats as saves
import mod_loader

SAMPLE=(b"\xef\xbb\xbf[General]\r\nYear=1965\r\nMonth=1\r\nDay=1\r\nIDNo=5432\r\n"
        b"[Nation0]\r\nName=Japan\r\nFunds=25000\r\n[Nation0Submarines]\r\nSubCount=2\r\n"
        b"Sub0Name=I-1\r\nSub0Availability=40\r\nSub0Accuracy=-2\r\nSub0SubType=0\r\nSub0Fate=\r\nSub0YearBuilt=1960\r\n"
        b"Sub0RemainingBuildTime=8\r\nSub0Halted=0\r\nSub0Sunk=0\r\nSub0Active=0\r\nSub0InPlay=1\r\nSub0LocationAreaName=Northeast Asia\r\n"
        b"Sub1Name=I-2\r\nSub1Availability=40\r\nSub1Accuracy=-2\r\nSub1SubType=0\r\nSub1YearBuilt=1960\r\n"
        b"Sub1RemainingBuildTime=6666\r\nSub1Sunk=1\r\nSub1InPlay=1\r\n[Unsupported]\r\nUserField=preserve\r\n")


class SubmarineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="submarine-test-",dir=mod_loader.HERE)
        self.root=Path(self.temp.name);self.save_root=self.root/"Save";self.slot=self.save_root/"Game1";self.slot.mkdir(parents=True)
        self.path=self.slot/"Campaign.bcs";self.path.write_bytes(SAMPLE);(self.slot/"Fleet.des").write_bytes(b"preserve design")
        self.context=contextlib.ExitStack()
        for module,name,value in ((subs,"HERE",self.root),(subs,"LIBRARY",self.root/"library.json"),(saves,"SAVE_ROOT",self.save_root),(saves,"BACKUPS",self.root/"backups")):
            self.context.enter_context(patch.object(module,name,value))
        self.context.enter_context(patch.object(mod_loader,"running_games",return_value=[]))

    def tearDown(self): self.context.close();self.temp.cleanup()

    def blueprint(self,**changes):
        return subs.save_blueprint({**subs.DEFAULT,**changes})

    def apply(self,blueprint,index=0,adjust=False,sha=None):
        return subs.apply_blueprint(self.path,"Nation0",index,blueprint["id"],blueprint["revision"],sha or saves.digest(self.path),adjust)

    def test_all_starting_templates_fit_model(self):
        for design in subs.TEMPLATES:
            self.assertTrue(subs.evaluate(design)["valid"],design["name"])

    def test_overloaded_design_cannot_be_saved(self):
        design={**subs.DEFAULT,"displacement":100,"torpedo_tubes":12,"torpedo_load":100}
        self.assertFalse(subs.evaluate(design)["valid"])
        with self.assertRaisesRegex(ValueError,"over its"):
            subs.save_blueprint(design)
        self.assertFalse(subs.LIBRARY.exists())

    def test_invalid_unknown_bool_and_multiline_inputs_refused(self):
        for fields in ({"laser":1},{"sonar":True},{"depth":10000},{"name":"bad\nline"}):
            with self.assertRaises(ValueError): subs.evaluate({**subs.DEFAULT,**fields})

    def test_propulsion_and_missile_gates(self):
        for fields in ({"year":1935,"propulsion":"nuclear"},{"year":1970,"propulsion":"aip"},{"missile_cells":4},
                       {"role":"missile","missile_cells":0},{"torpedo_load":0}):
            with self.assertRaises(ValueError): subs.evaluate({**subs.DEFAULT,**fields})

    def test_component_changes_recalculate_native_outputs(self):
        first=subs.evaluate(subs.DEFAULT)
        improved=subs.evaluate({**subs.DEFAULT,"sonar":3,"reliability":3})
        self.assertGreater(improved["native"]["accuracy"],first["native"]["accuracy"])
        self.assertGreater(improved["native"]["availability"],first["native"]["availability"])
        self.assertFalse(improved["tactical_control_implemented"])

    def test_library_revisions_and_recoverable_previous_copy(self):
        first=self.blueprint();second=subs.save_blueprint({**subs.DEFAULT,"name":"Patrol II"},first["id"],1)
        self.assertEqual(second["revision"],2)
        self.assertEqual(len(list((self.root/"submarine-library-backups").glob("*.json"))),1)
        with self.assertRaisesRegex(ValueError,"changed"):
            subs.save_blueprint(subs.DEFAULT,first["id"],1)

    def test_inspection_does_not_include_sunk_boats_or_write_files(self):
        result=subs.inspect_save(self.path)
        self.assertEqual(len(result["boats"]),1)
        self.assertEqual(result["boats"][0]["name"],"I-1")
        self.assertFalse(subs.LIBRARY.exists())
        self.assertEqual(self.path.read_bytes(),SAMPLE)

    def test_apply_changes_only_supported_fields_and_backs_up_full_slot(self):
        blueprint=self.blueprint();result=self.apply(blueprint,adjust=True)
        native=blueprint["evaluation"]["native"]
        expected=SAMPLE.replace(b"Sub0Availability=40",("Sub0Availability="+str(native["availability"])).encode()).replace(b"Sub0Accuracy=-2",("Sub0Accuracy="+str(native["accuracy"])).encode()).replace(b"Sub0RemainingBuildTime=8",("Sub0RemainingBuildTime="+str(native["suggested_build_turns"])).encode())
        self.assertEqual(self.path.read_bytes(),expected)
        backup=Path(result["backup"])
        self.assertEqual((backup/self.path.name).read_bytes(),SAMPLE)
        self.assertEqual((backup/"Fleet.des").read_bytes(),b"preserve design")
        self.assertFalse(list(backup.glob("*.tmp")))
        binding=json.loads(Path(result["binding_file"]).read_text(encoding="utf-8"))["bindings"]["Nation0/0"]
        self.assertEqual(binding["boat_name"],"I-1")
        self.assertEqual(binding["design"],blueprint["evaluation"]["design"])
        self.assertFalse(list(self.save_root.glob("*.tmp")))

    def test_running_game_stale_save_and_stale_blueprint_refused(self):
        blueprint=self.blueprint()
        with patch.object(mod_loader,"running_games",return_value=[{"pid":9}]):
            with self.assertRaisesRegex(ValueError,"close RTW3"): self.apply(blueprint)
        with self.assertRaisesRegex(ValueError,"save changed"): self.apply(blueprint,sha="wrong")
        subs.save_blueprint({**subs.DEFAULT,"name":"New revision"},blueprint["id"],1)
        with self.assertRaisesRegex(ValueError,"Blueprint changed"): self.apply(blueprint)
        self.assertEqual(self.path.read_bytes(),SAMPLE)

    def test_role_future_and_sunk_boat_protections(self):
        with self.assertRaisesRegex(ValueError,"same native role"): self.apply(self.blueprint(role="coastal"))
        with self.assertRaisesRegex(ValueError,"later than this campaign"): self.apply(self.blueprint(year=2000))
        with self.assertRaisesRegex(ValueError,"unsunk"): self.apply(self.blueprint(),index=1)
        self.assertEqual(self.path.read_bytes(),SAMPLE)

    def test_completed_boat_build_timer_is_protected(self):
        self.path.write_bytes(SAMPLE.replace(b"Sub0RemainingBuildTime=8",b"Sub0RemainingBuildTime=0"))
        with self.assertRaisesRegex(ValueError,"under construction"): self.apply(self.blueprint(),adjust=True)

    def test_sidecar_failure_rolls_back_native_save_and_retains_backup(self):
        blueprint=self.blueprint();original_replace=Path.replace
        def fail_sidecar(path,target):
            if str(target).endswith(".submarine-designs.json"): raise OSError("simulated sidecar failure")
            return original_replace(path,target)
        with patch.object(Path,"replace",fail_sidecar):
            with self.assertRaisesRegex(ValueError,"Native save restored"): self.apply(blueprint)
        self.assertEqual(self.path.read_bytes(),SAMPLE)
        self.assertFalse(self.path.with_name(self.path.stem+".submarine-designs.json").exists())
        self.assertTrue(list((self.root/"backups").glob("*/Game1/Campaign.bcs")))
        self.assertFalse(list(self.save_root.glob("*.tmp")))


if __name__=="__main__": unittest.main(verbosity=2)
