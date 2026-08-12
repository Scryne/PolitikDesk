"""Kanıt motoru — DETERMİNİSTİK. LLM ÇAĞRISI YOKTUR.

⛔ MİMARİ KURAL (Spec §11.2, P4):
   Bu paket `politikdesk.llm` paketini import EDEMEZ.

   Gerekçe: `evidence_status` hiçbir koşulda bir LLM çağrısının çıktısı
   olamaz (Spec §8.1 "Yasak"). LLM'in tek görevi, HESAPLANMIŞ etiketi
   kullanıcıya açıklayan metni yazmaktır — etiketi belirlemek değil.

   Kural `scripts/check_architecture.py` ile CI'da zorlanır; ihlal eden
   bir commit CI'ı kırar (tests/test_architecture.py bunu deneyle doğrular).

Faz 2'de bu pakete gelecek modüller:
    rules.py         R0–R7 kural motoru (Spec §8.3)     — F2-12
    independence.py  bağımsız kanıt sayımı (Spec §8.2)  — F2-11
    salience.py      gündem skoru (Spec §8.4)           — F2-15
"""

ENGINE_VERSION = "evidence-engine@0.1.0-scaffold"
