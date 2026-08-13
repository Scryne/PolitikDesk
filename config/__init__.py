"""Çalışma zamanı yapılandırması — kodun DIŞINDAKİ kararlar.

Bu dizin uygulama kodu değil, **yapılandırma** taşır: hangi kaynaklardan
toplanacağı (`sources.yml`), veri yayım takvimi (`calendar_2026.yml`) ve
Election Mode eşikleri (`election_mode.py`).

Ayrım niyetlidir. `politikdesk/config.py` uygulamanın *ayarlarıdır*
(veritabanı adresi, model adı, bütçe tavanı) ve ortam değişkenlerinden
okunur. Buradakiler ise *ürün kararlarıdır*: 8 kaynak sınırı, seçim
dönemi eşiği. Bunlar bir dağıtım ayrıntısı değildir ve gözden geçirilmek
üzere depoda dururlar.

`__init__.py` bir paket yapmak için gerekli (Spec/Yol Haritası F4-15
çıktıyı `config/election_mode.py` olarak adlandırıyor). Dizin
Dockerfile'da `/app/config`'e kopyalanır ve WORKDIR `/app` olduğu için
konteynerde de import edilebilir.
"""
