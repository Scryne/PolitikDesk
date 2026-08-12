"""LLM adaptörü — sağlayıcı-agnostik arayüz + maliyet takibi (F0-17).

Spec §11.5 disiplini:
  * Tüm çağrılar `llm.client.LLMClient` üzerinden geçer.
  * Her çağrının token/maliyeti `llm_calls` tablosuna yazılır.
  * Günlük/aylık tavan aşılınca `BudgetExceeded` fırlatılır.
  * Yapılandırılmış çıktı (JSON şema) zorunludur.
  * Her prompt sürümlenir ve çıktıya işlenir.

⛔ `evidence/` modülü bu paketi import EDEMEZ (Spec §11.2). Kural
   scripts/check_architecture.py ile CI'da zorlanır.
"""

from politikdesk.llm.errors import BudgetExceeded, LLMError, LLMRefusal
from politikdesk.llm.pricing import estimate_cost_usd

__all__ = ["BudgetExceeded", "LLMError", "LLMRefusal", "estimate_cost_usd"]
