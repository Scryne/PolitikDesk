"""Kanıt motoru — DETERMİNİSTİK. LLM ÇAĞRISI YOKTUR.

⛔ MİMARİ KURAL (Spec §11.2, P4):
   Bu paket `politikdesk.llm` paketini import EDEMEZ.

   Gerekçe: `evidence_status` hiçbir koşulda bir LLM çağrısının çıktısı
   olamaz (Spec §8.1 "Yasak"). LLM'in tek görevi, HESAPLANMIŞ etiketi
   kullanıcıya açıklayan metni yazmaktır — etiketi belirlemek değil.

   Kural `scripts/check_architecture.py` ile CI'da zorlanır; ihlal eden
   bir commit CI'ı kırar (tests/test_architecture.py bunu deneyle doğrular).

Paketin modülleri:
    rules.py         R0–R7 kural motoru (Spec §8.3)     — F2-12
    independence.py  bağımsız kanıt sayımı (Spec §8.2)  — F2-11
    salience.py      gündem skoru (Spec §8.4)           — F2-15

`ENGINE_VERSION` tek yerde tanımlıdır: `rules.py`. Burada yalnızca yeniden
dışa vurulur. Faz 0'da bu paket kendi iskele sürümünü tutuyordu; motor
yazıldıktan sonra değer güncellenmedi ve iki farklı sürüm dolaşıma girdi.
Sürümü ikinci kez yazmak, `score_claims`'in yeniden puanlama yüklemini
sessizce yanlış tarafa çeker.
"""

from politikdesk.evidence.rules import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]
