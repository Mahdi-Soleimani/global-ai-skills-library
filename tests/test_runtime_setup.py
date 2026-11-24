"""Local runtime setup/launcher tests without a network or user profile writes."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from runtime_setup import isolated_env, runtime_python, validate_layout, setup, verify_runtime


class RuntimeSetupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix="gasl-runtime-test-")
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()

    def layout(self):
        python=runtime_python(self.root)
        python.parent.mkdir(parents=True)
        python.write_bytes(b"INERT placeholder")
        (self.root/".venv/pyvenv.cfg").write_text("include-system-site-packages = false\n",encoding="utf-8")
        return python

    def test_isolated_environment_does_not_change_parent(self):
        with patch.dict(os.environ,{"PYTHONPATH":"injected","PYTHONHOME":"injected","PYTHONSTARTUP":"injected"}):
            env=isolated_env()
            for key in ("PYTHONPATH","PYTHONHOME","PYTHONSTARTUP"):
                self.assertNotIn(key,env)
                self.assertEqual(os.environ[key],"injected")
            self.assertEqual(env["PYTHONNOUSERSITE"],"1")

    def test_layout_refuses_missing_and_system_site_packages(self):
        with self.assertRaises(ValueError):
            validate_layout(self.root)
        python=self.layout()
        self.assertEqual(validate_layout(self.root),python)
        cfg=self.root/".venv/pyvenv.cfg"
        for content in ("include-system-site-packages = true\n",
                        "include-system-site-packages = false\ninclude-system-site-packages = true\n"):
            cfg.write_text(content,encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_layout(self.root)

    def test_setup_check_never_installs(self):
        python=self.layout()
        with patch("runtime_setup._run") as run:
            self.assertEqual(setup(self.root,check=True),python)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[1],"-c")
        self.assertIn("2.3.0",run.call_args.args)

    def test_failed_layout_never_calls_python_or_deletes(self):
        folder=self.root/".venv"
        folder.mkdir()
        marker=folder/"keep"
        marker.write_bytes(b"preserve")
        with patch("runtime_setup._run") as run,self.assertRaises(ValueError):
            setup(self.root)
        run.assert_not_called()
        self.assertEqual(marker.read_bytes(),b"preserve")

    def test_real_venv_creation_and_prefix_without_network(self):
        subprocess.run([sys.executable,"-I","-m","venv","--without-pip",str(self.root/".venv")],
                       env=isolated_env(),check=True,timeout=60)
        self.assertEqual(verify_runtime(self.root,require_mcp=False),runtime_python(self.root))

if __name__=="__main__":
    unittest.main()
