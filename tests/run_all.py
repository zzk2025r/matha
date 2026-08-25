"""全量测试套件 — 执行所有 tests/ 下的测试模块。"""
import subprocess, sys, os, glob

os.chdir(r"D:\trae")
sys.path.insert(0, r"D:\trae")

test_files = sorted(glob.glob("tests/test_*.py"))
print(f"发现 {len(test_files)} 个测试文件")
print("=" * 70)

results = []
for tf in test_files:
    # Convert path to module name: tests/test_foo.py -> tests.test_foo
    mod = "tests." + os.path.splitext(os.path.basename(tf))[0]
    try:
        r = subprocess.run(
            [sys.executable, "-m", mod],
            capture_output=True, text=True, timeout=30,
            cwd=r"D:\trae"
        )
        lines = r.stdout.strip().split("\n")
        last = lines[-1] if lines else ""
        if "总计" in last or "通过" in last:
            status = last
        elif r.returncode == 0:
            status = "✓ 通过"
        else:
            # Show first error line
            err_lines = [l for l in r.stderr.split("\n") if l.strip()][:2]
            status = f"✗ {err_lines[0] if err_lines else 'exit=' + str(r.returncode)}"
        print(f"  {mod.replace('tests.', 'test_'):40s} {status}")
        results.append((mod, r.returncode == 0))
    except subprocess.TimeoutExpired:
        print(f"  {mod:40s} ✗ 超时")
        results.append((mod, False))
    except Exception as e:
        print(f"  {mod:40s} ✗ {e}")
        results.append((mod, False))

print("=" * 70)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"总计: {passed}/{total} 通过")
failed = [m for m, ok in results if not ok]
if failed:
    print(f"失败 ({len(failed)} 个):")
    for m in failed:
        print(f"  - {m}")
print("=" * 70)
sys.exit(0 if passed == total else 1)
