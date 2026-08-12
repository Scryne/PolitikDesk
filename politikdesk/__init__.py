"""PolitikDesk — AI Political Intelligence & Editorial Workspace.

Modüler monolit (Spec §11.2). Modül sınırları:

    ingestion/  kaynak adaptörleri, normalizasyon, dedup
    nlp/        embedding, NER, iddia çıkarımı
    clustering/ olay kümeleme + merge/split
    evidence/   DETERMİNİSTİK kanıt motoru — llm/ import edemez
    context/    olay-olay ilişkileri, tarihsel bağlam
    editorial/  taslak üretimi, pre-publish check
    briefing/   sabah/akşam brifingi
    llm/        sağlayıcı-agnostik adapter + maliyet takibi
    api/        FastAPI router'ları
    admin/      kaynak yönetimi, olay denetimi
    eval/       test seti, ölçüm koşucusu
"""

__version__ = "0.1.0"
