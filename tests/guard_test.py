"""守門入口：跑 tests/ 底下所有 test_*.py。全域 PostToolUse hook 會呼叫這支；
測試紅就擋下編輯。手動跑：python3 tests/guard_test.py"""
import glob
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    failed = []
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        name = os.path.basename(path)
        try:
            mod = runpy.run_path(path)
            for fn_name, fn in sorted(mod.items()):
                if fn_name.startswith("test_") and callable(fn):
                    fn()
            print(f"PASS {name}")
        except Exception as e:  # noqa: BLE001
            failed.append((name, e))
            print(f"FAIL {name}: {e}")
    if failed:
        print(f"\n❌ {len(failed)} 個測試檔失敗")
        return 1
    print("\n✅ 全部測試通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
