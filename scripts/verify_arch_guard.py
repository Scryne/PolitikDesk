"""F0-16 DoD kanıtı: kuralı ihlal eden bir dosya CI'ı gerçekten kırıyor mu?

Gerçek repo üzerinde canlı deney yapar:
  1. politikdesk/evidence/ içine kuralı ihlal eden geçici bir dosya yazar
  2. denetleyiciyi çalıştırır ve ihlali yakalamasını BEKLER
  3. dosyayı siler ve denetleyicinin yeniden temiz döndüğünü doğrular

Kullanım:
    python -m scripts.verify_arch_guard

Çıkış kodu 0 = koruma çalışıyor, 1 = koruma çalışmıyor.
"""

from __future__ import annotations

from scripts.check_architecture import REPO_ROOT, check

PROBE = REPO_ROOT / "politikdesk" / "evidence" / "_arch_guard_probe.py"
PROBE_SOURCE = '''"""GEÇİCİ deney dosyası — scripts/verify_arch_guard.py tarafından yaratıldı."""
from politikdesk.llm.client import LLMClient  # kural ihlali

__all__ = ["LLMClient"]
'''


def main() -> int:
    if PROBE.exists():
        PROBE.unlink()

    baseline = check()
    if baseline:
        print("[HATA] Deneyden ONCE repo zaten kirli - once mevcut ihlalleri duzeltin.")
        for v in baseline:
            print("   ", v.render(REPO_ROOT))
        return 1

    PROBE.write_text(PROBE_SOURCE, encoding="utf-8")
    try:
        with_probe = check()
    finally:
        PROBE.unlink(missing_ok=True)

    after = check()

    ok = bool(with_probe) and not after
    if ok:
        print(
            "[OK] Koruma dogrulandi: ihlal eden dosya eklendiginde denetleyici "
            f"{len(with_probe)} ihlal bildirdi, dosya silinince yeniden temiz dondu."
        )
        return 0

    if not with_probe:
        print("[HATA] KORUMA CALISMIYOR: ihlal eden dosya eklendi ama yakalanmadi.")
    if after:
        print("[HATA] Temizlik basarisiz: deney dosyasi silindikten sonra hala ihlal var.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
