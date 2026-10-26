"""Lifecycle helper command construction; never launches processes in tests."""
import tempfile
import unittest
from pathlib import Path

from rings.lifecycle import autostart_command, python_gui_executable, restart_command, ROOT


class LifecycleTests(unittest.TestCase):
    def test_autostart_modes_reuse_existing_script(self):
        for mode in ("Install", "Remove", "Status"):
            with self.subTest(mode=mode):
                command = autostart_command(mode)
                self.assertEqual(command[0], "powershell.exe")
                self.assertEqual(command[-2:], ["-Mode", mode])
                self.assertTrue(command[command.index("-File") + 1].endswith("Autostart.ps1"))
        with self.assertRaises(ValueError):
            autostart_command("DeleteEverything")

    def test_restart_waits_on_own_process_and_same_interpreter(self):
        cmd = restart_command(4521, executable=r"C:\tools\custom-python.exe")
        self.assertEqual(cmd[0], "powershell.exe")
        self.assertEqual(cmd[cmd.index("-WaitPid") + 1], "4521")
        self.assertEqual(cmd[cmd.index("-PythonPath") + 1], r"C:\tools\custom-python.exe")
        self.assertEqual(cmd[cmd.index("-MainPath") + 1], str(ROOT / "main.py"))
        with self.assertRaises(ValueError):
            restart_command(-1)

    def test_prefers_sibling_pythonw_when_present(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "python.exe"
            source.touch()
            target = Path(root) / "pythonw.exe"
            self.assertEqual(python_gui_executable(str(source)), str(source))
            target.touch()
            self.assertEqual(python_gui_executable(str(source)), str(target))


if __name__ == "__main__":
    unittest.main()
