# Kurulu design skill'leri

`DESIGN.md` Bölüm 3 ve `docs/DESIGN-BASLANGIC.md` Adım 3'ün karşılığı.
**Kural: aynı anda 10'dan fazla design skill aktif olmasın** — fazlası
context'i böler ve ölçülebilir şekilde kaliteyi düşürür.

## Çekirdek set (7)

| Skill | Nereden | Not |
|---|---|---|
| `frontend-design` | `claude-plugins-official` marketplace | Değiştirilmedi, olduğu gibi |
| `design-system` | bu depoda yazıldı | Token'ları `ui/tokens.py`'ye bağlar |
| `enterprise-dashboard-design` | bu depoda yazıldı | Bölüm 7-8 uygulama notları |
| `dashboard-ux` | bu depoda yazıldı | Bilgi hiyerarşisi, eşik/uyarı |
| `dataviz` | **Claude Code yerleşiği** | Ayrıca kurulmadı — zaten yüklü |
| `micro-interactions` | bu depoda yazıldı | Süre/easing, layout zıplaması |
| `accessibility-wcag` | bu depoda yazıldı | WCAG 2.2 AA, Lighthouse ≥95 |

## Proje tipine göre eklenenler (2)

Proje "mevcut arayüzü yeniden tasarlama" + "Türkçe metin kalitesi kritik"
kategorilerine giriyor (`DESIGN.md` Bölüm 3.2):

| Skill | Neden |
|---|---|
| `redesign-existing-projects` | Çalışan bir arayüz yeniden dizildi; davranış korunmak zorundaydı |
| `ux-writing` | Arayüzün tamamı Türkçe, i18n katmanı yok, metin doğrudan kodda |

**Toplam 9** — tavan 10.

## Neden bazıları burada yok

`docs/DESIGN-BASLANGIC.md` Adım 3'ün "KURMA" listesi (`impeccable`,
`ui-ux-pro-max`, `design-inspiration`, `gpt-taste`, `emil-design-eng`,
`ui-styling`, `color-system`, `typography`, `ux-laws`, `magicui-patterns`,
`aceternity-ui-patterns`, `reactbits-patterns`, `minimalist-ui`,
`industrial-brutalist-ui`) bilerek kurulmadı: çekirdek setle veya
`DESIGN.md` Bölüm 5–13 ile çakışıyorlar.

Ayrıca `magicui`/`aceternity`/`reactbits` React bileşen kütüphaneleridir;
bu depoda React yok (bkz. `CLAUDE.md`).
