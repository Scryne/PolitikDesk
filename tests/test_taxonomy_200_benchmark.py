"""Faz 24: 200+ Gerçekçi Türkçe Haber Başlığı ile Kapsamlı Editoryal Taksonomi Benchmark'ı."""

from __future__ import annotations

import pytest

from politikdesk.analysis.taxonomy import (
    CATEGORIES,
    REGIONS,
    classify_category,
    classify_region,
)

# 200+ Gerçekçi Türkçe Haber Başlığı Veri Seti (Tüm kategoriler, bölgeler ve çoklu sinyal kesişimleri)
BENCHMARK_200 = [
    # ── 1. EKONOMİ & FİNANS (30 Başlık) ──
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
    (
        "Türkiye'nin 5 yıllık kredi iflas takası (CDS) primi 260 baz puanın altına indi",
        "Risk primi ve yabancı sermaye girişi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Konut satışları temmuzda faiz oranlarındaki seyre rağmen yıllık yüzde 16 arttı",
        "İpotekli ve kredili satış istatistikleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Otomotiv Distribütörleri Derneği sıfır araç satışlarında pazar büyümesini açıkladı",
        "Ticari araç ve binek otomobil satışları",
        "ekonomi",
        "turkiye",
    ),
    (
        "Tarım Ürünleri Üretici Fiyat Endeksi (Tarım-ÜFE) yıllık bazda yüzde 52 arttı",
        "Gıda enflasyonu ve hasat dönemi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Gelir İdaresi Başkanlığı kayıt dışı ekonomiyle mücadele denetimlerini sıkılaştırdı",
        "Vergi müfettişleri sahada",
        "ekonomi",
        "turkiye",
    ),
    (
        "Merkez Bankası TL mevduat payını artırmaya yönelik zorunlu karşılık düzenlemesi yaptı",
        "Kredi büyümesi ve TL mevduat faizleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye İhracatçılar Meclisi (TİM) en çok ihracat yapan sektörleri duyurdu",
        "Otomotiv ve kimya ihracatı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye Varlık Fonu uluslararası piyasalarda 500 milyon dolarlık sukuk ihracı gerçekleştirdi",
        "Kira sertifikası ve finansman",
        "ekonomi",
        "turkiye",
    ),
    (
        "KOBİ'lere yönelik KGF teminatlı yeni finansman destek paketi açıklandı",
        "İşletme kredileri ve yatırım teşviki",
        "ekonomi",
        "turkiye",
    ),
    (
        "Kısa vadeli dış borç stoku haziran ayı sonunda 230 milyar dolar oldu",
        "Bankalar ve reel sektör borçlanması",
        "ekonomi",
        "turkiye",
    ),
    (
        "Hazine nakit dengesi temmuz ayında fazla verdi",
        "Kamu gelirleri ve faiz dışı fazla",
        "ekonomi",
        "turkiye",
    ),
    (
        "İstanbul Sanayi Odası (İSO) İmalat PMI verisini 48.5 olarak açıkladı",
        "Ekonomik büyüme ve sipariş göstergeleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Altın ve para piyasaları uzmanları gram altın ve ons fiyatındaki yükselişi yorumladı",
        "Emtia ve döviz piyasası",
        "ekonomi",
        "turkiye",
    ),
    (
        "Bankaların net karı ilk yarıda yıllık bazda yüzde 25 artış gösterdi",
        "Bankacılık sektörü özkaynak karlılığı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Vergi Konseyi dolaylı vergilerin payını azaltacak yeni vergi reformu taslağını sundu",
        "Gelir vergisi dilimleri ve kurumlar vergisi",
        "ekonomi",
        "turkiye",
    ),
    # ── 2. İÇ POLİTİKA (25 Başlık) ──
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
        "TBMM Adalet Komisyonu'nda kanun teklifi maddeleri kabul edildi",
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
    (
        "Saadet Partisi ve Gelecek Partisi ortak grup toplantısı düzenledi",
        "Meclis muhalefet çalışmaları",
        "politika",
        "turkiye",
    ),
    (
        "DEVA Partisi milletvekilleri TBMM'de soru önergesi verdi",
        "Yasama denetimi ve hükümet politikaları",
        "politika",
        "turkiye",
    ),
    (
        "Yeniden Refah Partisi seçim ittifakı tartışmalarına son noktayı koydu",
        "Genel başkan siyasi hedefleri anlattı",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Plan ve Bütçe Komisyonu 2027 yılı merkezi yönetim bütçe takvimini başlattı",
        "Bakanlık bütçeleri Meclis'te görüşülecek",
        "politika",
        "turkiye",
    ),
    (
        "Parti tüzüğü değişikliği için CHP Olağanüstü Kurultayı toplandı",
        "Tüzük maddeleri oylandı",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanı kararnamesi ile üst kademe kamu yöneticiliklerine atamalar yapıldı",
        "Bakan yardımcılıkları ve genel müdürler",
        "politika",
        "turkiye",
    ),
    (
        "Milletvekili dokunulmazlığı fezlekeleri TBMM Karma Komisyonu'na sevk edildi",
        "Fezleke dosyaları ve yargı süreci",
        "politika",
        "turkiye",
    ),
    (
        "Siyasi partilerin üye sayıları Yargıtay Cumhuriyet Başsavcılığı tarafından güncellendi",
        "Parti üyelik istatistikleri",
        "politika",
        "turkiye",
    ),
    (
        "Meclis Araştırma Komisyonu çocuk hakları raporunu tamamladı",
        "Milletvekilleri ortak rapor sundu",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanlığı İletişim Başkanlığı dezenformasyon bültenini yayımladı",
        "Hükümet basın açıklaması",
        "politika",
        "turkiye",
    ),
    (
        "Seçim barajı ve siyasi partiler kanunu değişikliği kulislerde tartışılıyor",
        "İttifak içi müzakereler",
        "politika",
        "turkiye",
    ),
    (
        "CHP Merkez Yönetim Kurulu (MYK) haftalık olağan toplantısını yaptı",
        "Parti sözcüsü gündemi değerlendirdi",
        "politika",
        "turkiye",
    ),
    (
        "Hükümet sözcüsü Meclis açılışı öncesi öncelikli kanun tekliflerini açıkladı",
        "Yasama gündemi ve reformlar",
        "politika",
        "turkiye",
    ),
    # ── 3. DIŞ POLİTİKA & DİPLOMASİ (25 Başlık) ──
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
    (
        "Almanya ve Fransa liderleri Paris'te Avrupa savunma paktı için bir araya geldi",
        "Berlin ve Paris diplomasi zirvesi",
        "dis_politika",
        "avrupa",
    ),
    (
        "İngiltere Dışişleri Bakanı Orta Doğu turu kapsamında Kahire ve Amman'ı ziyaret etti",
        "Diplomatik temaslar ve ateşkes çağrısı",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "G20 Liderler Zirvesi Rio de Janeiro'da küresel yoksulluk bildirisiyle sona erdi",
        "Uluslararası zirve ve ekonomik işbirliği",
        "dis_politika",
        "kuresel",
    ),
    (
        "Türkiye ve Mısır Yüksek Düzeyli Stratejik İşbirliği Konseyi toplantısı yapıldı",
        "Kahire ve Ankara arasında anlaşmalar imzalandı",
        "dis_politika",
        "turkiye",
    ),
    (
        "Avrupa Parlamentosu Türkiye yıllık ilerleme raporunu oylayarak kabul etti",
        "Strazburg'da genel kurul oturumu",
        "dis_politika",
        "avrupa",
    ),
    (
        "Dışişleri Bakanlığı'ndan Sudan'daki iç çatışmalara ilişkin itidal ve diplomasi çağrısı",
        "Büyükelçilik tahliye operasyonları",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Japonya ve Güney Kore liderleri Tokyo'da güvenlik zirvesinde buluştu",
        "Asya-Pasifik'te ikili diplomasi",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Uluslararası Atom Enerjisi Ajansı (UAEA) İran nükleer tesisleri denetim raporunu yayımladı",
        "Viyana'da diplomatik müzakereler",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Kuzey Kıbrıs Türk Cumhuriyeti'nin uluslararası tanınması için yeni diplomasi atağı",
        "Dışişleri heyeti temaslarda bulundu",
        "dis_politika",
        "turkiye",
    ),
    (
        "Hindistan ve Çin sınır hattında askeri devriyelerin yeniden başlaması için diplomatik uzlaşı",
        "Yeni Delhi ve Pekin mutabakatı",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Balkan Barış Forumu Saraybosna'da bölge dışişleri bakanlarını buluşturdu",
        "Bölgesel istikrar ve işbirliği",
        "dis_politika",
        "avrupa",
    ),
    (
        "İspanya, İrlanda ve Norveç'ten Filistin'i resmi olarak tanıma ortak diplomatik kararı",
        "Madrid ve Dublin ortak bildirisi",
        "dis_politika",
        "avrupa",
    ),
    (
        "Şanghay İşbirliği Örgütü Liderler Zirvesi Astana'da genişleme gündemiyle toplandı",
        "Avrasya diplomasi zirvesi",
        "dis_politika",
        "kuresel",
    ),
    # ── 4. GÜVENLİK & SAVUNMA (25 Başlık) ──
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
    (
        "Hava Kuvvetleri Komutanlığı F-16 modernizasyon projesi ve filo tatbikatını tamamladı",
        "Askeri havacılık ve savunma",
        "guvenlik",
        "turkiye",
    ),
    (
        "Deniz Kuvvetleri Komutanlığı MAVİ VATAN tatbikatını Doğu Akdeniz'de icra etti",
        "Donanma fırkateynleri ve denizaltılar",
        "guvenlik",
        "turkiye",
    ),
    (
        "Jandarma Özel Asayiş Komutanlığı (JÖAK) kış dönemi terörle mücadele operasyonlarını başlattı",
        "Özel harekat timleri dağlık arazide",
        "guvenlik",
        "turkiye",
    ),
    (
        "Savunma Sanayii Başkanlığı yerli denizaltı STM500 inşa sürecini paylaştı",
        "Denizaltı ve askeri tersane",
        "guvenlik",
        "turkiye",
    ),
    (
        "Ukrayna ordusu Kursk bölgesinde sınır ötesi askeri harekat başlattı",
        "Savaş alanında son gelişmeler",
        "guvenlik",
        "rusya_ukrayna",
    ),
    (
        "Kremlin Sözcüsü Rus ordusunun stratejik nükleer tatbikat icra ettiğini duyurdu",
        "Moskova askeri alarmı",
        "guvenlik",
        "rusya_ukrayna",
    ),
    (
        "Pentagon Kızıldeniz'de Husilere yönelik hava harekatı düzenlendiğini açıkladı",
        "ABD Merkez Kuvvetler Komutanlığı CENTCOM",
        "guvenlik",
        "abd",
    ),
    (
        "Kore Yarımadası'nda askeri gerilim: Kuzey Kore balistik füze denemesi yaptı",
        "Seul ve Tokyo güvenlik alarmında",
        "guvenlik",
        "asya_pasifik",
    ),
    (
        "İçişleri Bakanlığı uyuşturucu çetelerine yönelik NARKOGÜÇ operasyonunun bilançosunu açıkladı",
        "Emniyet ve narkotik polisleri",
        "guvenlik",
        "turkiye",
    ),
    (
        "GÖKBEY genel maksat helikopteri Jandarma Genel Komutanlığı envanterine girdi",
        "TUSAŞ üretimi askeri helikopter",
        "guvenlik",
        "turkiye",
    ),
    (
        "HAVELSAN yerli otonom kara ve hava araçları sürü harekat yazılımını tanıttı",
        "Askeri simülasyon ve savunma yazılımı",
        "guvenlik",
        "turkiye",
    ),
    (
        "Tayvan Boğazı'nda Çin donanması geniş çaplı askeri tatbikat icra etti",
        "Pekin ve Taipei hattında ordu teyakkuzda",
        "guvenlik",
        "asya_pasifik",
    ),
    (
        "MİT ve Emniyet ortaklığıyla yabancı istihbarat servislerine çalışan hücre çökertildi",
        "Casusluk soruşturması ve operasyon",
        "guvenlik",
        "turkiye",
    ),
    # ── 5. HUKUK & YARGI (20 Başlık) ──
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
    (
        "İcra ve İflas Kanunu'nda borçlu haklarını koruyan yeni yargı paketi yürürlüğe girdi",
        "İcra daireleri ve haciz işlemleri",
        "hukuk",
        "turkiye",
    ),
    (
        "Bilişim suçları mahkemesi siber dolandırıcılık şebekesi sanıklarına rekor hapis cezası verdi",
        "Ağır ceza mahkemesi kararı",
        "hukuk",
        "turkiye",
    ),
    (
        "Kişisel Verileri Koruma Kurumu (KVKK) veri ihlali yapan şirketlere idari para cezası kesti",
        "Veri koruma mevzuatı ve hukuk",
        "hukuk",
        "turkiye",
    ),
    (
        "Bölge Adliye Mahkemesi (İstinaf) iş mahkemesi kıdem tazminatı kararını bozdu",
        "İstinaf dairesi emsal içtihat",
        "hukuk",
        "turkiye",
    ),
    (
        "Adalet Bakanlığı arabuluculuk sistemiyle 1 yılda 1 milyon uyuşmazlığın çözüldüğünü duyurdu",
        "Hukuk uyuşmazlıkları ve arabuluculuk",
        "hukuk",
        "turkiye",
    ),
    (
        "Noterler Birliği nöbetçi noterlik ve dijital sözleşme onay istatistiklerini paylaştı",
        "Hukuki işlemler ve noterlik",
        "hukuk",
        "turkiye",
    ),
    (
        "Miras hukuku ve paylı mülkiyet uyuşmazlıklarında zorunlu arabuluculuk kararı",
        "Sulh hukuk mahkemesi davaları",
        "hukuk",
        "turkiye",
    ),
    (
        "Tüketici Mahkemesi ayıplı mal davasında tüketici lehine bedel iadesi kararı verdi",
        "Tüketici hakları ve yargı",
        "hukuk",
        "turkiye",
    ),
    # ── 6. ENERJİ & İKLİM (20 Başlık) ──
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
    (
        "TEİAŞ elektrik iletim şebekesi trafo kapasite artırımı ihalesini tamamladı",
        "Yüksek gerilim hatları ve enerji nakli",
        "enerji",
        "turkiye",
    ),
    (
        "Doğu Akdeniz'de Abdülhamid Han sondaj gemisi yeni kuyu açtı",
        "Mavi Vatan enerji aramaları",
        "enerji",
        "turkiye",
    ),
    (
        "Avrupa Birliği Rus doğalgazı ithalatını tamamen durdurma yol haritasını açıkladı",
        "Brüksel enerji güvenliği paktı",
        "enerji",
        "avrupa",
    ),
    (
        "Suudi Arabistan dev petrol sahasında yeni hidrokarbon rezervleri keşfetti",
        "Aramco günlük üretim kapasitesi",
        "enerji",
        "orta_dogu",
    ),
    (
        "Gabar dağında petrol üretimi günlük 50 bin varil sınırını aştı",
        "TPAO Şırnak petrol sahası",
        "enerji",
        "turkiye",
    ),
    (
        "Jeotermal Enerji Derneği Ege bölgesinde yeni jeotermal santral projelerini tanıttı",
        "Yenilenebilir enerji ve elektrik",
        "enerji",
        "turkiye",
    ),
    (
        "Enerji ve Tabii Kaynaklar Bakanlığı Ulusal Enerji Verimliliği Eylem Planı'nı başlattı",
        "Enerji tasarrufu ve yeşil enerji",
        "enerji",
        "turkiye",
    ),
    (
        "Paris İklim Anlaşması hedefleri doğrultusunda küresel karbon vergisi müzakereleri",
        "BM İklim Zirvesi COP29",
        "enerji",
        "kuresel",
    ),
    (
        "Hidroelektrik santrallerinde (HES) baraj doluluk oranları elektrik üretimini artırdı",
        "DSİ ve hidroelektrik enerji",
        "enerji",
        "turkiye",
    ),
    (
        "Kuzey Akım boru hattı sabotajı soruşturmasında yeni teknik raporlar açıklandı",
        "Baltık Denizi doğalgaz hattı",
        "enerji",
        "avrupa",
    ),
    # ── 7. TEKNOLOJİ & SANAYİ (20 Başlık) ──
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
    (
        "TOGG elektrikli sedan modeli T10F'in seri üretim takvimini duyurdu",
        "Yerli otomobil ve batarya fabrikası",
        "teknoloji",
        "turkiye",
    ),
    (
        "OpenAI ve Microsoft yeni nesil yapay zeka süper bilgisayar projesini başlattı",
        "Büyük dil modelleri ve sunucu altyapısı",
        "teknoloji",
        "abd",
    ),
    (
        "Apple ve Google yapay zeka entegrasyonlu akıllı telefon işletim sistemlerini tanıttı",
        "Mobil yazılım ve teknoloji lansmanı",
        "teknoloji",
        "abd",
    ),
    (
        "Nvidia yapay zeka çipleri pazarında gelir rekoru kırdı",
        "Yarı iletken ve donanım teknolojileri",
        "teknoloji",
        "abd",
    ),
    (
        "Türkiye Uzay Ajansı (TUA) Ay Araştırma Programı motor testlerini tamamladı",
        "Uzay aracı ve roket teknolojisi",
        "teknoloji",
        "turkiye",
    ),
    (
        "Organize sanayi bölgelerinde (OSB) fabrika yatırımları ve istihdam arttı",
        "İmalat sanayii ve üretim kapasitesi",
        "teknoloji",
        "turkiye",
    ),
    (
        "BTK internet servis sağlayıcılarına yönelik altyapı ve hız kalite raporunu sundu",
        "Genişbant fiber internet ve telekomünikasyon",
        "teknoloji",
        "turkiye",
    ),
    (
        "Küresel kuantum bilgisayar teknolojilerinde yeni fiziksel kubit rekoru kırıldı",
        "Kuantum donanım ve yazılım laboratuvarı",
        "teknoloji",
        "kuresel",
    ),
    (
        "Sanayi Bakanlığı Model Fabrika projesiyle KOBİ'lere yalın üretim eğitimi verdi",
        "Sanayi verimliliği ve dijitalleşme",
        "teknoloji",
        "turkiye",
    ),
    (
        "ASML yeni nesil EUV litografi çip üretim makinelerini tanıttı",
        "Hollanda yarı iletken teknolojisi",
        "teknoloji",
        "avrupa",
    ),
    # ── 8. SAĞLIK & TOPLUM (20 Başlık) ──
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
    (
        "Dünya Sağlık Örgütü (WHO) küresel maymun çiçeği virüsü için acil durum ilan etti",
        "Cenevre'de uluslararası sağlık uyarısı",
        "saglik_toplum",
        "kuresel",
    ),
    (
        "Kızılay kan bağışı ve kış dönemi acil kan stoku çağrısında bulundu",
        "Toplumsal dayanışma ve kan merkezleri",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "ÖSYM YKS ve KPSS sınav sonuçları ile yerleştirme takvimini açıkladı",
        "Öğrenci sınavları ve tercih kılavuzu",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "TİSK ve Hak-İş iş sağlığı ve mesleki eğitim protokolü imzaladı",
        "İşçi sağlığı ve çalışma hayatı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Kültür ve Turizm Bakanlığı müze ve ören yerleri ziyaretçi rekorunu duyurdu",
        "Tarihi miras ve kültürel etkinlikler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Afet ve Acil Durum Yönetimi Başkanlığı (AFAD) Türkiye geneli deprem tatbikatı düzenledi",
        "Afet bilinci ve sivil toplum",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Engelli vatandaşlar için kamuda EKPSS memur yerleştirme kadroları açıldı",
        "Sosyal entegrasyon ve kamu istihdamı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Sağlık Bakanlığı Merkezi Hekim Randevu Sistemi'nde (MHRS) onaylı randevu dönemini başlattı",
        "Hastane randevuları ve poliklinikler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Huzurevleri ve yaşlı bakım merkezleri kapasite artırım projesi onaylandı",
        "Sosyal hizmetler ve yaşlı bakımı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Üniversitelerde yeni akademik yıl açılışı ve rektörler toplantısı yapıldı",
        "Yükseköğretim ve bilimsel araştırmalar",
        "saglik_toplum",
        "turkiye",
    ),
    # ── 9. YEREL YÖNETİMLER (20 Başlık) ──
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
    (
        "Bursa Büyükşehir Belediyesi tarihi çarşı ve hanlar bölgesi restorasyonunu tamamladı",
        "Kent estetiği ve belediye projesi",
        "yerel",
        "turkiye",
    ),
    (
        "Antalya Büyükşehir Belediyesi turizm sezonu altyapı ve arıtma yatırımlarını açıkladı",
        "Akdeniz kıyı yönetimi ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "Gaziantep Büyükşehir Belediyesi gastronomi vadisi ve kentsel gelişim projesini tanıttı",
        "Yerel kalkınma ve belediyecilik",
        "yerel",
        "turkiye",
    ),
    (
        "İzmir Su ve Kanalizasyon İdaresi (İZSU) yağmur suyu ayrıştırma kanallarını yeniledi",
        "Altyapı ve su baskınlarına karşı önlem",
        "yerel",
        "turkiye",
    ),
    (
        "Belediyeler zabıta teşkilatı fahiş fiyat ve hijyen denetimlerini artırdı",
        "Yerel zabıta denetimleri ve pazar yerleri",
        "yerel",
        "turkiye",
    ),
    (
        "Konya Büyükşehir Belediyesi akıllı şehir otomasyonu ve bisiklet yolları ağını genişletti",
        "Akıllı şehircilik ve yerel yönetim",
        "yerel",
        "turkiye",
    ),
    (
        "Diyarbakır Büyükşehir Belediyesi kırsal kalkınma ve sulama kanalı desteği sağladı",
        "Tarımsal sulama ve belediye desteği",
        "yerel",
        "turkiye",
    ),
    (
        "Adana Büyükşehir Belediyesi Çukurova hafif raylı sistem uzatma projesini meclise sundu",
        "Ulaşım master planı ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "Eskişehir Büyükşehir Belediyesi Porsuk çayı rekreasyon ve yeşil alan projesini açtı",
        "Kent parkları ve belediye hizmetleri",
        "yerel",
        "turkiye",
    ),
    (
        "Trabzon Büyükşehir Belediyesi sahil dolgu alanı ve rekreasyon projesini tamamladı",
        "Karadeniz kıyı düzenlemesi ve belediye",
        "yerel",
        "turkiye",
    ),
]


@pytest.mark.parametrize(("title", "summary", "expected_cat", "expected_reg"), BENCHMARK_200)
def test_200_headlines_taxonomy_accuracy(
    title: str, summary: str, expected_cat: str, expected_reg: str
) -> None:
    """200+ Türkçe gerçek haber başlığı üzerinde kategori ve bölge sınıflandırma doğruluğu."""
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


def test_taxonomy_200_coverage_statistics() -> None:
    """Benchmark'ın 200+ başlık içerdiğini ve tüm 10 kategori ve 7 bölgeyi kapsadığını doğrular."""
    assert len(BENCHMARK_200) >= 200, (
        f"Benchmark başlık sayısı 200'ün altında: {len(BENCHMARK_200)}"
    )

    covered_cats = {item[2] for item in BENCHMARK_200}
    covered_regs = {item[3] for item in BENCHMARK_200}

    canonical_cats = {k for k, _ in CATEGORIES if k not in ("all", "diger")}
    canonical_regs = {k for k, _ in REGIONS if k != "all"}

    for cat in canonical_cats:
        assert cat in covered_cats, f"Kategori benchmarkta eksik: {cat}"

    for reg in canonical_regs:
        assert reg in covered_regs, f"Bölge benchmarkta eksik: {reg}"
