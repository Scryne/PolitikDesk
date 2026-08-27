"""Faz 23: 100+ Gerçekçi Türkçe Haber Başlığı ile Editoryal Taksonomi ve False-Positive Benchmark'ı."""

from __future__ import annotations

import pytest

from politikdesk.analysis.taxonomy import (
    CATEGORIES,
    REGIONS,
    classify_category,
    classify_region,
)

# 100+ Gerçekçi Türkçe Haber Başlığı Veri Seti
HEADLINES_BENCHMARK = [
    # ── EKONOMİ & FİNANS (15 Örnek) ──
    (
        "TCMB Para Politikası Kurulu faiz kararını yüzde 50 seviyesinde sabit tuttu",
        "Enflasyon ve kur baskısı değerlendirildi",
        "ekonomi",
        "turkiye",
    ),
    (
        "TÜİK yıllık TÜFE enflasyonunu yüzde 42.8 olarak açıkladı",
        "Gıda ve ulaştırma fiyatlarında artış",
        "ekonomi",
        "turkiye",
    ),
    (
        "Hazine ve Maliye Bakanlığı 2 yıllık tahvil ihalesinde borçlanma hedefini aştı",
        "Eurobond ve iç borçlanma dengesi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Borsa İstanbul BIST 100 endeksi bankacılık hisseleri öncülüğünde rekor kırdı",
        "Yabancı yatırımcı girişi arttı",
        "ekonomi",
        "turkiye",
    ),
    (
        "BDDK kredi kartı limitleri ve taksit sınırlandırmalarına ilişkin yeni karar aldı",
        "Tüketici kredileri ve risk ağırlıkları",
        "ekonomi",
        "turkiye",
    ),
    (
        "Merkez Bankası brüt rezervleri swap hariç net pozisyonda toparlanma kaydetti",
        "Döviz ve altın rezervi arttı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Asgari Ücret Tespit Komisyonu ara zam ve refah payı gündemiyle toplandı",
        "İşçi ve işveren sendikaları masada",
        "ekonomi",
        "turkiye",
    ),
    (
        "İhracat temmuz ayında 22 milyar doları aşarak rekor seviyeye ulaştı",
        "Cari açık daralmaya devam ediyor",
        "ekonomi",
        "turkiye",
    ),
    (
        "Uluslararası kredi derecelendirme kuruluşu Fitch Türkiye'nin kredi notunu yükseltti",
        "Görünüm pozitif olarak korundu",
        "ekonomi",
        "turkiye",
    ),
    (
        "Resmi Gazete'de yayımlanan kararla ÖTV ve KDV oranlarında matrah düzenlemesi yapıldı",
        "Vergi ve harç tarifeleri güncellendi",
        "ekonomi",
        "turkiye",
    ),
    (
        "İşsizlik oranı yüzde 8.4 seviyesine gerileyerek son 10 yılın en düşük düzeyini gördü",
        "İstihdam artışı sanayi sektöründe",
        "ekonomi",
        "turkiye",
    ),
    (
        "Merkezi yönetim bütçe açığı ilk altı ayda hedeflerin altında gerçekleşti",
        "Kamu harcamalarında tasarruf tedbirleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "SPK'dan borsa spekülasyonlarına karşı yeni tedbir ve idari para cezası kararları",
        "Halka arz ve sermaye piyasası denetimleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye Cumhuriyet Merkez Bankası döviz satış ve efektif alış kurlarını güncelledi",
        "Dolar ve euro kurunda son durum",
        "ekonomi",
        "turkiye",
    ),
    (
        "Moody's Türkiye bankacılık sektörünün kredi notu görünümünü durağandan pozitife çevirdi",
        "Finansal istikrar göstergeleri",
        "ekonomi",
        "turkiye",
    ),
    # ── İÇ POLİTİKA (12 Örnek) ──
    (
        "TBMM Genel Kurulu yeni anayasa hazırlıkları kapsamında olağanüstü toplandı",
        "Meclis Başkanı siyasi parti liderleriyle görüştü",
        "politika",
        "turkiye",
    ),
    (
        "Yüksek Seçim Kurulu (YSK) ara seçim takvimini ve oy kullanma kurallarını duyurdu",
        "Sandık kurulları ve seçmen listeleri",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanlığı Kabinesi Beştepe'de toplandı: Gündem iç ve dış gelişmeler",
        "Bakanlar kurulu sonrası açıklama yapıldı",
        "politika",
        "turkiye",
    ),
    (
        "CHP Grup Toplantısı'nda Genel Başkan muhalefetin yol haritasını paylaştı",
        "Milletvekilleri ve parti meclisi katıldı",
        "politika",
        "turkiye",
    ),
    (
        "AK Parti MKYK toplantısı sona erdi: Kongre takvimi ve teşkilat çalışmaları",
        "Siyasi değerlendirmeler yapıldı",
        "politika",
        "turkiye",
    ),
    (
        "MHP lideri Devlet Bahçeli Meclis açılışında önemli mesajlar verdi",
        "İttifak ortaklığı ve milli birlik vurgusu",
        "politika",
        "turkiye",
    ),
    (
        "İYİ Parti Genel İdare Kurulu yeni dönem siyaset stratejisini belirledi",
        "Parti sözcüsü basın toplantısı düzenledi",
        "politika",
        "turkiye",
    ),
    (
        "DEM Parti Meclis Grubu yeni yasama yılı öncesi deklarasyon yayınladı",
        "Siyasi müzakereler ve milletvekili heyeti",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanı Erdoğan ile muhalefet lideri arasında ikili görüşme gerçekleşti",
        "Siyasette normalleşme ve diyalog mesajları",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Adalet Komisyonu'nda yargı reformu kanun teklifi maddeleri kabul edildi",
        "Milletvekilleri teklif üzerinde uzlaştı",
        "politika",
        "turkiye",
    ),
    (
        "Siyasi partilerin Hazine yardımı ve seçim bütçesi payları açıklandı",
        "Partilere aktarılacak ödenekler belirlendi",
        "politika",
        "turkiye",
    ),
    (
        "Referandum tartışmaları Meclis kulislerinde yeniden gündeme geldi",
        "Hükümet ve muhalefet kanadından açıklamalar",
        "politika",
        "turkiye",
    ),
    # ── DIŞ POLİTİKA & DİPLOMASİ (12 Örnek) ──
    (
        "Dışişleri Bakanı Hakan Fidan Brüksel'de AB Dış İlişkiler Konseyi'ne katıldı",
        "Avrupa Birliği ile vize serbestisi ve müzakere başlıkları",
        "dis_politika",
        "avrupa",
    ),
    (
        "BM Genel Kurulu 79. Dönem Zirvesi New York'ta dünya liderlerini bir araya getirdi",
        "Küresel krizler ve uluslararası barış",
        "dis_politika",
        "kuresel",
    ),
    (
        "NATO Dışişleri Bakanları Zirvesi'nde ittifakın savunma bütçesi ve genişleme kararları alındı",
        "Washington'da ikili görüşmeler",
        "dis_politika",
        "abd",
    ),
    (
        "Türkiye ve Yunanistan arasında Ege ve Doğu Akdeniz'de Güven Artırıcı Önlemler Zirvesi",
        "Atina ve Ankara diplomasi heyetleri",
        "dis_politika",
        "turkiye",
    ),
    (
        "Azerbaycan ve Ermenistan arasında barış antlaşması protokolü taslağı hazırlandı",
        "Büyükelçilikler düzeyinde müzakereler",
        "dis_politika",
        "turkiye",
    ),
    (
        "Dışişleri Bakanlığı'ndan Gazze'deki ateşkes müzakerelerine ilişkin resmi diplomatik bildiri",
        "Katar ve Mısır ile koordinasyon",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Türkiye ve Çin arasında ikili ticaret ve Kuşak Yol diplomasi heyeti görüşmesi",
        "Pekin'de dışişleri yetkilileri bir araya geldi",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Avrupa Birliği ve üye ülkeler arasında Gümrük Birliği modernizasyonu müzakereleri başladı",
        "Brüksel ve Berlin'de AB heyetleri toplandı",
        "dis_politika",
        "avrupa",
    ),
    (
        "Türkiye ve ABD Stratejik Mekanizma toplantısı Washington'da düzenlendi",
        "Beyaz Saray ve Dışişleri ortak açıklaması",
        "dis_politika",
        "abd",
    ),
    (
        "İran ve Suudi Arabistan büyükelçileri bölgesel normalleşme zirvesinde buluştu",
        "Riyad ve Tahran arasında diplomatik adımlar",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Birleşmiş Milletler Güvenlik Konseyi ateşkes tasarısını oy çokluğuyla kabul etti",
        "Uluslararası barış gücü görevlendirildi",
        "dis_politika",
        "kuresel",
    ),
    (
        "Türk Devletleri Teşkilatı Liderler Zirvesi'nde ortak alfabe ve ticaret anlaşması imzalandı",
        "Bölgesel diplomasi protokolü",
        "dis_politika",
        "turkiye",
    ),
    # ── GÜVENLİK & SAVUNMA (12 Örnek) ──
    (
        "Milli Savunma Bakanlığı ve TSK Irak ve Suriye'nin kuzeyinde hava harekatı icra etti",
        "Terör hedefleri imha edildi ve güvenlik sağlandı",
        "guvenlik",
        "orta_dogu",
    ),
    (
        "MİT sınır ötesi nokta operasyonla kırmızı bültenle aranan terör örgütü yöneticisini etkisiz hale getirdi",
        "İstihbarat destekli operasyon",
        "guvenlik",
        "turkiye",
    ),
    (
        "ASELSAN ve ROKETSAN yerli hava savunma füze sistemi SİPER'in test atışını başarıyla tamamladı",
        "Savunma sanayii ve askeri teknoloji",
        "guvenlik",
        "turkiye",
    ),
    (
        "Bayraktar TB3 SİHA TCG Anadolu amfibi hücum gemisinden ilk iniş ve kalkışını gerçekleştirdi",
        "İHA ve SİHA teknolojisinde tarihi adım",
        "guvenlik",
        "turkiye",
    ),
    (
        "TUSAŞ tarafından geliştirilen milli muharip uçak KAAN ikinci test uçuşunu başarıyla tamamladı",
        "Hava Kuvvetleri ve Türk Silahlı Kuvvetleri",
        "guvenlik",
        "turkiye",
    ),
    (
        "Emniyet Genel Müdürlüğü ve Jandarma 81 ilde eş zamanlı organize suç örgütü operasyonu yaptı",
        "Polis ve güvenlik güçleri operasyonu",
        "guvenlik",
        "turkiye",
    ),
    (
        "Sahil Güvenlik Komutanlığı Ege ve Akdeniz'de düzensiz göçmen kaçakçılarına darbe vurdu",
        "Sınır güvenliği ve deniz devriyesi",
        "guvenlik",
        "turkiye",
    ),
    (
        "Rusya ve Ukrayna sınırında çatışmalar Donbas ve Zaporijya cephesinde yoğunlaştı",
        "Askeri harekat ve ordu mevzileri",
        "guvenlik",
        "rusya_ukrayna",
    ),
    (
        "İsrail ordusu Gazze ve Lübnan sınırında askeri operasyonlarını genişletti",
        "Çatışma ve güvenlik alarmı",
        "guvenlik",
        "orta_dogu",
    ),
    (
        "TSK komuta kademesi ve Milli Savunma Bakanı sınır birliklerinde denetlemelerde bulundu",
        "Askeri teyakkuz ve güvenlik önlemleri",
        "guvenlik",
        "turkiye",
    ),
    (
        "Türk Silahlı Kuvvetleri'ne yeni nesil Fırtına obüsleri ve Altay tankları teslim edildi",
        "Kara Kuvvetleri envanteri güçlendirildi",
        "guvenlik",
        "turkiye",
    ),
    (
        "Milli İstihbarat Teşkilatı siber casusluk şebekesine yönelik kapsamlı operasyon düzenledi",
        "Güvenlik ve istihbarat koordinasyonu",
        "guvenlik",
        "turkiye",
    ),
    # ── HUKUK & YARGI (12 Örnek) ──
    (
        "Anayasa Mahkemesi (AYM) internet düzenlemesine ilişkin iptal kararının gerekçesini yayımladı",
        "Yüksek mahkeme hak ihlali kararı verdi",
        "hukuk",
        "turkiye",
    ),
    (
        "Yargıtay Ceza Genel Kurulu milyonları ilgilendiren emsal dolandırıcılık kararını onadı",
        "Mahkeme kararı ve içtihat",
        "hukuk",
        "turkiye",
    ),
    (
        "Danıştay yürütmeyi durdurma talebini reddederek idari işlemin hukuka uygun olduğuna hükmetti",
        "İdare mahkemesi kararı kesinleşti",
        "hukuk",
        "turkiye",
    ),
    (
        "Hakimler ve Savcılar Kurulu (HSK) adli ve idari yargı ana kararnamesini yayımladı",
        "Savcı ve hakim atamaları tamamlandı",
        "hukuk",
        "turkiye",
    ),
    (
        "İstanbul Cumhuriyet Başsavcılığı kamu zararına yol açan şüpheliler hakkında iddianame hazırladı",
        "Ağır ceza mahkemesinde dava açıldı",
        "hukuk",
        "turkiye",
    ),
    (
        "Türkiye Barolar Birliği ve avukatlar yeni avukatlık asgari ücret tarifesini açıkladı",
        "Adliye ve savunma mesleği",
        "hukuk",
        "turkiye",
    ),
    (
        "Sayıştay denetim raporlarında kamu ihalelerindeki mevzuata aykırılıklar tespit edildi",
        "Yargılama ve denetim bulguları",
        "hukuk",
        "turkiye",
    ),
    (
        "Resmi Gazete'de yayımlanan kanun hükmünde kararname ve yeni mevzuat yürürlüğe girdi",
        "Hukuki düzenlemeler ve yasa maddeleri",
        "hukuk",
        "turkiye",
    ),
    (
        "Ankara Adliyesi'nde görülen tarihi davada sanıklar hakkında tutuklama ve tahliye kararları",
        "Ceza mahkemesi duruşması",
        "hukuk",
        "turkiye",
    ),
    (
        "Ceza Muhakemesi Kanunu ve Türk Ceza Kanunu değişiklik teklifi Adalet Bakanlığı tarafından sunuldu",
        "Yargı reformu paketi",
        "hukuk",
        "turkiye",
    ),
    (
        "Avrupa İnsan Hakları Mahkemesi (AİHM) adil yargılanma hakkına ilişkin kararını açıkladı",
        "Uluslararası hukuk ve mahkeme kararı",
        "hukuk",
        "avrupa",
    ),
    (
        "Sulh Ceza Hakimliği yasa dışı bahis sitelerine erişim engeli kararı verdi",
        "Mahkeme kararı ve adli işlemler",
        "hukuk",
        "turkiye",
    ),
    # ── ENERJİ & İKLİM (10 Örnek) ──
    (
        "BOTAŞ ve TPAO Karadeniz Sakarya gaz sahasında yeni doğalgaz üretim kuyusu açtı",
        "Milli enerji ve sondaj gemisi faaliyetleri",
        "enerji",
        "turkiye",
    ),
    (
        "Akkuyu Nükleer Güç Santrali 1. ünitesinde türbin testleri başarıyla gerçekleştirildi",
        "Nükleer enerji üretimi ve elektrik şebekesi",
        "enerji",
        "turkiye",
    ),
    (
        "EPDK elektrik ve doğalgaz toptan satış tarifelerinde güncelleme yaptı",
        "Enerji Piyasası Düzenleme Kurumu kararı",
        "enerji",
        "turkiye",
    ),
    (
        "OPEC+ petrol üretim kotalarını ve günlük varil kısıtlamalarını uzattı",
        "Küresel petrol ve brent petrol fiyatları",
        "enerji",
        "kuresel",
    ),
    (
        "Türkiye rüzgar ve güneş enerjisinde kurulu güç rekoru kırarak Avrupa'da üst sıralara yükseldi",
        "Yenilenebilir enerji yatırımları",
        "enerji",
        "turkiye",
    ),
    (
        "EPİAŞ elektrik piyasasında spot piyasa takas fiyatları belirlendi",
        "Enerji borsası günlük işlem hacmi",
        "enerji",
        "turkiye",
    ),
    (
        "Karadeniz gazı Filyos işleme tesisinden ulusal iletim boru hattına basılmaya devam ediyor",
        "Doğalgaz altyapısı ve BOTAŞ iletimi",
        "enerji",
        "turkiye",
    ),
    (
        "Çevre, Şehircilik ve İklim Değişikliği Bakanlığı Karbon Emisyon Ticareti taslağını açıkladı",
        "İklim kanunu ve yeşil dönüşüm",
        "enerji",
        "turkiye",
    ),
    (
        "Kömür madenlerinde iş sağlığı ve güvenliği denetim raporları yayımlandı",
        "Maden işletmeleri ve enerji üretimi",
        "enerji",
        "turkiye",
    ),
    (
        "Uluslararası Enerji Ajansı küresel yenilenebilir enerji kapasite artış raporunu sundu",
        "Güneş paneli ve rüzgar türbini yatırımları",
        "enerji",
        "kuresel",
    ),
    # ── TEKNOLOJİ & SANAYİ (10 Örnek) ──
    (
        "TÜBİTAK ve Sanayi ve Teknoloji Bakanlığı yerli yapay zeka büyük dil modelini tanıttı",
        "Milli teknoloji hamlesi ve yazılım ekosistemi",
        "teknoloji",
        "turkiye",
    ),
    (
        "TÜRKSAT 6A yerli haberleşme uydusu yörünge testlerini tamamlayarak hizmete girdi",
        "Uzay teknolojileri ve telekomünikasyon",
        "teknoloji",
        "turkiye",
    ),
    (
        "Sanayi üretim endeksi yüksek teknoloji ve otomasyon sektörleri öncülüğünde arttı",
        "Fabrika üretimi ve imalat sanayii",
        "teknoloji",
        "turkiye",
    ),
    (
        "Savunma ve otomotiv sanayii için yerli çip ve yarı iletken tasarım merkezi kuruldu",
        "Çip üretimi ve ar-ge merkezi",
        "teknoloji",
        "turkiye",
    ),
    (
        "Ulaştırma Bakanlığı 5G telekomünikasyon altyapı ihalesi ve frekans tahsis takvimini açıkladı",
        "Mobil iletişim ve dijital altyapı",
        "teknoloji",
        "turkiye",
    ),
    (
        "Türkiye Siber Güvenlik Kümelenmesi ulusal siber tatbikatı başarıyla tamamladı",
        "Siber savunma ve kritik altyapı yazılımları",
        "teknoloji",
        "turkiye",
    ),
    (
        "Yapay zeka ve robotik otomasyon sistemleri Türk sanayisinde verimliliği artırdı",
        "Endüstriyel ar-ge ve teknoloji teşvikleri",
        "teknoloji",
        "turkiye",
    ),
    (
        "Teknoparklar ve Ar-Ge merkezlerinde istihdam edilen araştırmacı sayısı 300 bini aştı",
        "Yazılım ve donanım girişimciliği",
        "teknoloji",
        "turkiye",
    ),
    (
        "Dünya genelinde küresel yarı iletken ve çip tedarik zincirinde yeni yatırımlar",
        "Tayvan ve Asya çip fabrikaları",
        "teknoloji",
        "asya_pasifik",
    ),
    (
        "Milli Teknoloji Genel Müdürlüğü dijital dönüşüm destek paketini devreye aldı",
        "Sanayi işletmelerine teknoloji hibesi",
        "teknoloji",
        "turkiye",
    ),
    # ── SAĞLIK & TOPLUM (10 Örnek) ──
    (
        "Sağlık Bakanlığı 81 ilde yeni şehir hastaneleri hekim ve sağlık personeli kadrolarını açtı",
        "Hastane kapasiteleri ve randevu sistemi",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Milli Eğitim Bakanlığı (MEB) yeni müfredat ve öğretmen atama takvimini duyurdu",
        "Okul, öğrenci ve üniversite hazırlıkları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "SGK emekli maaş farkları ve bayram ikramiyesi ödeme takvimini netleştirdi",
        "Sosyal Güvenlik Kurumu ve emekliler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Yükseköğretim Kurulu (YÖK) üniversite kontenjanları ve taban puanlarını yayımladı",
        "Akademik eğitim ve üniversiteler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Türk Tabipleri Birliği (TTB) hekim hakları ve sağlıkta şiddete karşı yasa önerisi sundu",
        "Doktorlar ve sağlık çalışanları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Aile ve Sosyal Hizmetler Bakanlığı ihtiyaç sahibi hanelere yönelik sosyal yardım ödemelerini artırdı",
        "Toplum desteği ve engelli maaşları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "TÜİK Türkiye'nin nüfus projeksiyonları ve yaşlanma verilerini paylaştı",
        "Nüfus artış hızı ve demografik yapı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Göç İdaresi Başkanlığı düzensiz göç ve mülteci geri gönderme istatistiklerini açıkladı",
        "Sınır dışı işlemleri ve entegrasyon",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Sağlık Bakanlığı kış mevsimi öncesi grip aşısı ve ilaç tedarik protokolünü tamamladı",
        "Eczane ve ilaç stokları güvence altında",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Gençlik ve Spor Bakanlığı KYK yurt ve burs başvurularını başlattı",
        "Üniversite öğrencilerine barınma desteği",
        "saglik_toplum",
        "turkiye",
    ),
    # ── YEREL YÖNETİMLER (10 Örnek) ──
    (
        "İstanbul Büyükşehir Belediyesi (İBB) Üsküdar-Kadıköy hafif metro hattı temelini attı",
        "Ulaşım ve raylı sistem yatırımı",
        "yerel",
        "turkiye",
    ),
    (
        "Ankara Büyükşehir Belediyesi (ABB) meclisinde su tarifeleri ve kentsel dönüşüm bütçesi onaylandı",
        "Belediye meclisi toplantısı",
        "yerel",
        "turkiye",
    ),
    (
        "İzmir Büyükşehir Belediyesi Körfez temizliği ve arıtma tesisi projesini başlattı",
        "İzmir yerel yönetimi ve çevre yatırımları",
        "yerel",
        "turkiye",
    ),
    (
        "İSKİ İstanbul'da baraj doluluk oranlarının yüzde 75'e yükseldiğini duyurdu",
        "Su yönetimi ve altyapı çalışmaları",
        "yerel",
        "turkiye",
    ),
    (
        "İstanbul Valiliği ve AFAD olası Marmara depremine karşı kentsel dönüşüm genelgesi yayımladı",
        "Valilik ve kaymakamlık koordinasyonu",
        "yerel",
        "turkiye",
    ),
    (
        "Büyükşehir belediyeleri toplu ulaşımda elektrikli otobüs filosunu genişletiyor",
        "Belediye otobüsleri ve metro entegrasyonu",
        "yerel",
        "turkiye",
    ),
    (
        "ASKİ Ankara'da ana içme suyu iletim hattı yenileme çalışmalarını tamamladı",
        "Başkent su ve kanalizasyon idaresi",
        "yerel",
        "turkiye",
    ),
    (
        "Belediye başkanları birliği yerel yönetim reformu ve gelir paylaşımı raporunu sundu",
        "İlçe ve büyükşehir belediye başkanları",
        "yerel",
        "turkiye",
    ),
    (
        "Kentsel dönüşüm kapsamında riskli binaların tahliye ve yıkım işlemleri hızlandırıldı",
        "İmar planları ve belediye ruhsatları",
        "yerel",
        "turkiye",
    ),
    (
        "Muhtarlıklar ve mahalle konseyleri yerel hizmet taleplerini belediyeye iletti",
        "Yerel yönetim ve muhtarlık işbirliği",
        "yerel",
        "turkiye",
    ),
]


@pytest.mark.parametrize(("title", "summary", "expected_cat", "expected_reg"), HEADLINES_BENCHMARK)
def test_100_headlines_taxonomy_accuracy(
    title: str, summary: str, expected_cat: str, expected_reg: str
) -> None:
    """100+ Türkçe gerçek haber başlığı üzerinde kategori ve bölge sınıflandırma doğruluğu."""
    predicted_cat = classify_category(title, summary)
    assert predicted_cat == expected_cat, (
        f"Kategori Hatası!\n"
        f"  Başlık: '{title}'\n"
        f"  Beklenen: '{expected_cat}', Tahmin Edilen: '{predicted_cat}'"
    )

    predicted_reg = classify_region(title, summary)
    assert predicted_reg == expected_reg, (
        f"Bölge Hatası!\n"
        f"  Başlık: '{title}'\n"
        f"  Beklenen: '{expected_reg}', Tahmin Edilen: '{predicted_reg}'"
    )


def test_short_token_boundary_isolation_false_positives() -> None:
    """Kısa kelime köklerinin (kur, oy, gaz, ab, bm, fed) başka sözcükleri YANLIŞ tetiklemediğini doğrular."""
    # "kur" -> "kurum", "kurul", "kurtarma", "kurgu" kelimelerini ekonomi sanmamalı
    cat_kurum = classify_category(
        "Devlet Denetleme Kurumu yıllık raporunu açıkladı", vertical="other"
    )
    assert cat_kurum != "ekonomi" or cat_kurum in ("politika", "hukuk", "diger")

    # "oy" -> "oyun", "oyuncu", "oyuncak" kelimelerini politika sanmamalı
    cat_oyun = classify_category(
        "Milli tiyatro ekibi yeni sezon oyununun provasını yaptı", vertical="other"
    )
    assert cat_oyun != "politika"

    # "gaz" -> "gazete", "gazeteci", "gazoz" kelimelerini enerji sanmamalı
    cat_gazete = classify_category(
        "Uluslararası Gazeteciler Cemiyeti yıllık basın ödüllerini dağıttı", vertical="other"
    )
    assert cat_gazete != "enerji"

    # "ab" -> "abone", "abartı", "abide" kelimelerini Avrupa sanmamalı
    reg_abone = classify_region("Doğalgaz aboneleri için kış tarifesi duyuruldu")
    assert reg_abone != "avrupa"

    # "bm" -> "tbmm", "bomba", "ambargo" kelimelerini BM / Küresel sanmamalı
    reg_tbmm = classify_region("TBMM Genel Kurulu Ankara'da toplandı")
    assert reg_tbmm == "turkiye"


def test_all_canonical_categories_and_regions_covered_in_benchmark() -> None:
    """Benchmark veri setinin tüm 10 kategori ve 7 bölgeyi kapsadığını doğrular."""
    covered_cats = {item[2] for item in HEADLINES_BENCHMARK}
    covered_regs = {item[3] for item in HEADLINES_BENCHMARK}

    canonical_cats = {k for k, _ in CATEGORIES if k not in ("all", "diger")}
    canonical_regs = {k for k, _ in REGIONS if k != "all"}

    for cat in canonical_cats:
        assert cat in covered_cats, f"Kategori benchmarkta eksik: {cat}"

    for reg in canonical_regs:
        assert reg in covered_regs, f"Bölge benchmarkta eksik: {reg}"
