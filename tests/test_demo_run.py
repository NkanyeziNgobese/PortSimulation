import shutil
import subprocess
import sys
import unittest
from pathlib import Path


class DemoRunTest(unittest.TestCase):
    def test_demo_outputs_exist(self):
        root = Path(__file__).resolve().parents[1]
        out_dir = root / "outputs" / "test_demo_baseline"
        if out_dir.exists():
            shutil.rmtree(out_dir)

        cmd = [
            sys.executable,
            str(root / "scripts" / "run_simulation.py"),
            "--scenario",
            "baseline",
            "--seed",
            "123",
            "--demo",
            "--out",
            str(out_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("STDOUT:\n", result.stdout)
            print("STDERR:\n", result.stderr)
        self.assertEqual(result.returncode, 0)

        self.assertTrue((out_dir / "metadata.json").exists())
        self.assertTrue((out_dir / "kpis.csv").exists())
        self.assertTrue((out_dir / "run.log").exists())
        self.assertTrue((out_dir / "plots").exists())
        plots = list((out_dir / "plots").glob("*.png"))
        self.assertGreaterEqual(len(plots), 2)


if __name__ == "__main__":
    unittest.main()
