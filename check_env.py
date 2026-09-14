"""Проверка окружения QuickDeck — печатает по-русски, в отличие от .bat."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

print()
print("=" * 58)
print(f"  Python : {sys.version.split()[0]}")
bad = []
for mod in ("PySide6", "pynput"):
    try:
        m = __import__(mod)
        print(f"  {mod:<8}: OK  {getattr(m, '__version__', '')}")
    except Exception as e:
        bad.append(mod)
        print(f"  {mod:<8}: НЕ УСТАНОВЛЕН — {e}")
print("=" * 58)
if bad:
    print(f"\n  Не встало: {', '.join(bad)}")
    print("  Скопируй текст ошибки pip выше и покажи Claude.")
else:
    print("\n  Всё на месте. Запускай start.bat")
print()
