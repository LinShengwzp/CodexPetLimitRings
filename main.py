"""Entry point for the native Codex Mini/Pet quota rings."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys


def enable_dpi_awareness() -> None:
    """Use physical pixels to match Win32 pet coordinates across monitors."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def cli() -> int:
    parser = argparse.ArgumentParser(description="Attach two quota rings to Codex's native Mini/Pet.")
    parser.add_argument("--demo", action="store_true", help="preview 41/91 rings beside the pet or pointer without querying Codex")
    parser.add_argument("--once", action="store_true", help="print subscription quota JSON and exit")
    parser.add_argument("--probe", action="store_true", help="inspect live mascot position and native host window")
    parser.add_argument("--diagnose", action="store_true", help="show sanitized Codex window candidates and saved pet geometry")
    options = parser.parse_args()

    if os.name != "nt" and not options.once:
        print("这个桌宠只支持 Windows 10/11。", file=sys.stderr)
        return 2

    enable_dpi_awareness()

    if options.once:
        from rings.bridge import read_quotas, QuotaReadError
        from rings.core import explain
        try:
            result = explain(read_quotas())
        except QuotaReadError as exc:
            print("额度查询失败：" + str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if options.probe or options.diagnose:
        from rings.pet import PetLocator
        pet, details = PetLocator().inspect(diagnostic=options.diagnose)
        output = {
            "found": pet is not None,
            "mascot_rect": pet.rect.__dict__ if pet else None,
            "host_rect": pet.host_rect.__dict__ if pet else None,
            "position_source": pet.source if pet else None,
            "precise_mascot_geometry": pet.precise if pet else None,
            "hwnd": pet.handle if pet else None,
            "dpi": pet.dpi if pet else None,
            "monitor_work_area": pet.work_area.__dict__ if pet else None,
            "saved_codex_state": details,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if pet is None:
            print("未检测到可验证的 Pet 宿主窗口。可分享上面的诊断结果（不含凭据或窗口标题）。", file=sys.stderr)
        return 0 if pet else 1

    # Do not allow accidental double launch of the overlay.
    mutex = None
    if not options.demo:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        mutex = kernel32.CreateMutexW(None, False, "Local\\CodexPetLimitRings-v1")
        if not mutex:
            print("无法创建单实例锁。", file=sys.stderr)
            return 1
        if kernel32.GetLastError() == 183:
            kernel32.CloseHandle(mutex)
            print("额度圆环已经运行，不重复启动。")
            return 0
    try:
        from rings.ui import RingWidget
        RingWidget(demo=options.demo).run()
        return 0
    finally:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    raise SystemExit(cli())
