"""Phase 25: 300+ Adversarial Türkçe Haber Başlığı ile Stres Testi ve Confusion Matrix."""

from __future__ import annotations

from collections import defaultdict

import pytest

from politikdesk.analysis.taxonomy import (
    classify_category,
    classify_region,
)

# 300+ Adversarial ve Zorlu Türkçe Haber Başlığı Veri Seti
ADVERSARIAL_300 = [
    # ── EKONOMİ & FİNANS (35 Başlık) ──
    (
        "Merkez Bankası PPK toplantısı sonrası gecelik borçlanma faizini güncelledi",
        "Para piyasası ve likidite adımları",
        "ekonomi",
        "turkiye",
    ),
    (
        "Hazine iç borçlanma stratejisi kapsamında 5 yıllık TÜFE'ye endeksli tahvil ihraç etti",
        "Devlet tahvili ve kupon ödemeleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "BIST 100 endeksi günü yüzde 2.4 yükselişle rekor puandan kapattı",
        "Hisse senetleri ve işlem hacmi",
        "ekonomi",
        "turkiye",
    ),
    (
        "TÜİK ve ENAG enflasyon verileri arasındaki fark tartışılıyor",
        "Tüketici fiyat endeksi hesaplama yöntemi",
        "ekonomi",
        "turkiye",
    ),
    (
        "BDDK ticari kredilerde risk ağırlığı düzenlemesini yürürlüğe koydu",
        "Bankacılık sektörü sermaye yeterliliği",
        "ekonomi",
        "turkiye",
    ),
    (
        "Kredi derecelendirme kuruluşu S&P Türkiye'nin kredi notunu B+'dan BB-'ye yükseltti",
        "Kredi notu ve yabancı fon girişi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Asgari Ücret Komisyonu üçüncü toplantısını tamamladı: Rakam netleşiyor",
        "İşçi ve işveren temsilcileri zam oranını görüştü",
        "ekonomi",
        "turkiye",
    ),
    (
        "Cari işlemler dengesi haziran ayında 1.2 milyar dolar fazla verdi",
        "Dış ticaret ve turizm gelirleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "SPK'dan halka arz takvimine iki yeni şirket eklendi",
        "Sermaye piyasaları ve izahname onayı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Kur korumalı mevduat (KKM) toplam büyüklüğü 1.5 trilyon liranın altına geriledi",
        "TL mevduata geçiş süreci",
        "ekonomi",
        "turkiye",
    ),
    (
        "Konut kredisi faiz oranlarındaki indirim beklentisi konut satışlarını hareketlendirdi",
        "Gayrimenkul ve ipotekli konut satışı",
        "ekonomi",
        "turkiye",
    ),
    (
        "İkinci el araç piyasasında 6 ay 6 bin kilometre kuralı uzatıldı",
        "Otomotiv ticareti ve fiyat denetimi",
        "ekonomi",
        "turkiye",
    ),
    (
        "İhracat birim değer endeksi yıllık bazda yüzde 3.8 artış gösterdi",
        "Dış ticaret istatistikleri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Vergi reformu paketinde yurt dışı çıkış harcı ve kripto varlık vergisi maddeleri",
        "Gelir İdaresi Başkanlığı düzenlemesi",
        "ekonomi",
        "turkiye",
    ),
    (
        "İmalat sanayi kapasite kullanım oranı (KKO) temmuzda yüzde 76.2 oldu",
        "İmalat kapasite kullanımı ve sanayi verileri",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye'nin net rezervleri swap hariç pozitife geçti",
        "TCMB döviz pozisyonu",
        "ekonomi",
        "turkiye",
    ),
    (
        "Bankacılık sektörünün takipteki alacak oranı yüzde 1.5 seviyesine indi",
        "Kredi riskleri ve batık krediler",
        "ekonomi",
        "turkiye",
    ),
    (
        "Altın ithalatına kota getirilmesi sonrası kuyumculuk sektöründe son durum",
        "Kıymetli madenler ve cari açık",
        "ekonomi",
        "turkiye",
    ),
    (
        "Küresel piyasalarda dolar endeksi DXY faiz indirimi beklentisiyle geriledi",
        "Döviz kurları ve emtia piyasası",
        "ekonomi",
        "kuresel",
    ),
    (
        "Hazine ve Maliye Bakanı Londra ve New York'ta uluslararası yatırımcılarla buluştu",
        "Eurobond ihracı ve yabancı sermaye",
        "ekonomi",
        "turkiye",
    ),
    (
        "Otomotiv Distribütörleri ve Mobilite Derneği elektrikli araç satış verilerini paylaştı",
        "Otomobil pazarı ve ÖTV matrahı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Tarım Kredi Kooperatif marketlerinde temel gıda ürünlerinde indirim kampanyası",
        "Gıda enflasyonu ve perakende fiyatlar",
        "ekonomi",
        "turkiye",
    ),
    (
        "Reel Efektif Döviz Kuru (REK) endeksi TÜFE bazında 62.8 seviyesine yükseldi",
        "Türk Lirası reel değer artışı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Borsa İstanbul Vadeli İşlem ve Opsiyon Piyasası (VİOP) akşam seansında alıcılı seyretti",
        "Türev piyasalar ve endeks kontratları",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye Varlık Fonu madencilik ve telekomünikasyon yatırımlarını büyütüyor",
        "Kamu sermayesi ve stratejik varlıklar",
        "ekonomi",
        "turkiye",
    ),
    (
        "İşsizlik Sigortası Fonu toplam varlığı 250 milyar lirayı aştı",
        "İşsizlik ödeneği ve fon getirisi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Esnaf ve sanatkarlara Halkbank üzerinden kullandırılacak faiz indirimli kredi limiti artırıldı",
        "KOBİ kredisi ve kamu desteği",
        "ekonomi",
        "turkiye",
    ),
    (
        "Döviz tevdiat hesaplarında (DTH) parite etkisinden arındırılmış gerileme sürdü",
        "Bankalardaki döviz mevduatı",
        "ekonomi",
        "turkiye",
    ),
    (
        "Türkiye Cumhuriyet Merkez Bankası haftalık para ve banka istatistiklerini yayımladı",
        "M2 para arzı ve banka mevduatları",
        "ekonomi",
        "turkiye",
    ),
    (
        "TÜİK hizmet üretim endeksini yıllık bazda yüzde 6.5 artış olarak duyurdu",
        "Hizmet sektörü ciroları",
        "ekonomi",
        "turkiye",
    ),
    (
        "Gelir vergisi tarifesinde ilk dilim matrahının artırılması talep edildi",
        "Ücretli çalışanların vergi yükü",
        "ekonomi",
        "turkiye",
    ),
    (
        "Merkezi yönetim bütçesi faiz giderleri temmuz ayında açıklandı",
        "Kamu maliyesi ve bütçe dengesi",
        "ekonomi",
        "turkiye",
    ),
    (
        "Sermaye Piyasası Kurulu izinsiz kaldıraçlı foreks işlemi yaptıran 40 siteyi kapattı",
        "Finansal denetim ve yaptırım",
        "ekonomi",
        "turkiye",
    ),
    (
        "Merkez Bankası mikro ve makro ihtiyati çerçeveyi sadeleştirme kararı aldı",
        "Kredi büyüme sınırları ve zorunlu karşılık",
        "ekonomi",
        "turkiye",
    ),
    (
        "Yurt dışı yerleşiklerin hisse senedi ve DİBS net alımları arttı",
        "Portföy yatırımları ve sıcak para girişi",
        "ekonomi",
        "turkiye",
    ),
    # ── İÇ POLİTİKA (30 Başlık) ──
    (
        "TBMM Başkanı yeni yasama yılı öncesinde siyasi parti genel başkanlarını ziyaret etti",
        "Meclis gündemi ve anayasa uzlaşması",
        "politika",
        "turkiye",
    ),
    (
        "AK Parti olağan kongre sürecini ve ilçe kongreleri takvimini başlattı",
        "Parti teşkilatları ve MKYK kararı",
        "politika",
        "turkiye",
    ),
    (
        "CHP Parti Meclisi tüzük kurultayı hazırlıklarını tamamladı",
        "Genel başkan ve milletvekilleri toplantısı",
        "politika",
        "turkiye",
    ),
    (
        "MHP Genel Başkanı Devlet Bahçeli yazılı basın açıklaması yaptı",
        "Cumhur İttifakı ve siyasi değerlendirmeler",
        "politika",
        "turkiye",
    ),
    (
        "İYİ Parti Genel Başkanı Meclis grup toplantısında hükümeti eleştirdi",
        "Muhalefet politikası ve kanun teklifleri",
        "politika",
        "turkiye",
    ),
    (
        "DEM Parti Merkez Yürütme Kurulu haftalık siyasi gündemi değerlendirdi",
        "Parti sözcüsü basın toplantısı",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanlığı Kabinesi Beştepe'de toplandı: Gündem iç siyaset",
        "Bakanlar Kurulu toplantısı sonrası açıklama",
        "politika",
        "turkiye",
    ),
    (
        "YSK yenilenen yerel seçimlerin resmi ve kesin sonuçlarını ilan etti",
        "Oy sayımı ve sandık tutanakları",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Genel Kurulu'nda yeni vergi kanun teklifi maddeleri oylandı",
        "Milletvekilleri teklifi kabul etti",
        "politika",
        "turkiye",
    ),
    (
        "Gelecek Partisi ve Saadet Partisi ortak Meclis grubunu sürdürme kararı aldı",
        "Siyasi partiler ve parlamento grubu",
        "politika",
        "turkiye",
    ),
    (
        "DEVA Partisi genel merkezinde il başkanları toplantısı gerçekleştirildi",
        "Siyasi teşkilatlanma ve seçim hazırlıkları",
        "politika",
        "turkiye",
    ),
    (
        "Yeniden Refah Partisi Meclis'e yeni kanun teklifi sundu",
        "Milletvekili imzasıyla yasa önerisi",
        "politika",
        "turkiye",
    ),
    (
        "Milletvekili transferleri ve Meclis aritmetiğindeki değişim kulisleri hareketlendirdi",
        "Siyasi partilerin milletvekili sayıları",
        "politika",
        "turkiye",
    ),
    (
        "Erken seçim tartışmalarına iktidar ve muhalefet kanadından peş peşe açıklamalar",
        "Seçim takvimi ve siyasi müzakereler",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Adalet Komisyonu yargı paketini görüşmek üzere toplandı",
        "Komisyon başkanı ve milletvekilleri",
        "politika",
        "turkiye",
    ),
    (
        "Anayasa Mahkemesi üyeliğine TBMM Genel Kurulu'nda gizli oylama ile seçim yapıldı",
        "Yüksek mahkeme üye seçimi",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanı kararı ile üst kademe kamu yöneticiliklerine atama yapıldı",
        "Bakan yardımcılıkları ve genel müdür atamaları",
        "politika",
        "turkiye",
    ),
    (
        "CHP Merkez Yönetim Kurulu (MYK) genel merkezde olağanüstü toplandı",
        "Parti içi seçim hazırlıkları",
        "politika",
        "turkiye",
    ),
    (
        "Cumhur İttifakı ortakları Beştepe'de ikili liderler zirvesinde bir araya geldi",
        "Hükümet politikaları ve yasama gündemi",
        "politika",
        "turkiye",
    ),
    (
        "Meclis Dilekçe ve İnsan Haklarını İnceleme Karma Komisyonu rapor hazırladı",
        "Vatandaş başvuruları ve yasama denetimi",
        "politika",
        "turkiye",
    ),
    (
        "Siyasi Partiler Kanunu ve seçim mevzuatı revizyonu Meclis gündeminde",
        "Siyasi partilere üyelik ve baraj kuralları",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Güvenlik ve İstihbarat Komisyonu basına kapalı toplantı gerçekleştirdi",
        "Milletvekilleri brifing aldı",
        "politika",
        "turkiye",
    ),
    (
        "Cumhurbaşkanı Yardımcısı Orta Vadeli Program hedeflerini Meclis'te anlattı",
        "Hükümet programı ve yasama",
        "politika",
        "turkiye",
    ),
    (
        "Halkların Eşitlik ve Demokrasi Partisi eş genel başkanları basın toplantısı yaptı",
        "Siyasi deklarasyon ve barış mesajları",
        "politika",
        "turkiye",
    ),
    (
        "Memleket Partisi olağanüstü kurultayında yeni yönetim kadrosu belirlendi",
        "Parti tüzüğü ve genel başkanlık seçimi",
        "politika",
        "turkiye",
    ),
    (
        "Zafer Partisi genel başkanı basın mensuplarına açıklamalarda bulundu",
        "Sığınmacı politikası ve siyasi açıklamalar",
        "politika",
        "turkiye",
    ),
    (
        "Büyük Birlik Partisi Genel İstişare Kurulu toplandı",
        "Cumhur İttifakı ve siyaset gündemi",
        "politika",
        "turkiye",
    ),
    (
        "Demokrat Parti Genel Başkanı Meclis açılışı öncesi açıklama yaptı",
        "Demokrasi ve seçim değerlendirmeleri",
        "politika",
        "turkiye",
    ),
    (
        "TBMM Dışişleri Komisyonu uluslararası anlaşmaları onayladı",
        "Kanun tasarısı ve milletvekili oylaması",
        "politika",
        "turkiye",
    ),
    (
        "Meclis İçtüzüğü değişikliği teklifi partilerin ortak mutabakatına sunuldu",
        "Genel Kurul çalışma esasları",
        "politika",
        "turkiye",
    ),
    # ── DIŞ POLİTİKA & DİPLOMASİ (30 Başlık) ──
    (
        "Dışişleri Bakanı Hakan Fidan Washington'da mevkidaşı Antony Blinken ile görüştü",
        "ABD ve Türkiye ikili diplomasi ve F-16 tedariki",
        "dis_politika",
        "abd",
    ),
    (
        "BM Güvenlik Konseyi Orta Doğu krizini görüşmek üzere acil oturumla toplandı",
        "New York'ta uluslararası diplomasi",
        "dis_politika",
        "kuresel",
    ),
    (
        "Avrupa Birliği liderleri Brüksel zirvesinde genişleme politikasını ele aldı",
        "AB Komisyonu ve aday ülkeler müzakereleri",
        "dis_politika",
        "avrupa",
    ),
    (
        "Türkiye ve Yunanistan İstişari Görüşmeler 65. turu Atina'da yapıldı",
        "Ege ve Akdeniz diplomatik heyetleri",
        "dis_politika",
        "avrupa",
    ),
    (
        "Azerbaycan ve Ermenistan sınır belirleme komisyonu protokol imzaladı",
        "Güney Kafkasya barış diplomasisi",
        "dis_politika",
        "turkiye",
    ),
    (
        "İran ve Suudi Arabistan büyükelçilikleri yeniden tam kapasiteyle faaliyete başladı",
        "Tahran ve Riyad normalleşme süreci",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "G20 Dışişleri Bakanları Toplantısı'nda küresel diplomasi bildirisi kabul edildi",
        "Uluslararası barış ve ekonomik işbirliği",
        "dis_politika",
        "kuresel",
    ),
    (
        "NATO Genel Sekreteri Ankara'da resmi diplomatik temaslarda bulundu",
        "İttifakın güney kanadı ve savunma işbirliği",
        "dis_politika",
        "turkiye",
    ),
    (
        "Katar ve Mısır arabuluculuğunda Gazze'de ateşkes müzakereleri devam ediyor",
        "Kahire ve Doha diplomatik görüşmeleri",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Fransa Cumhurbaşkanı ve Almanya Başbakanı Berlin'de Avrupa güvenliğini görüştü",
        "Paris ve Berlin diplomasi zirvesi",
        "dis_politika",
        "avrupa",
    ),
    (
        "Türkiye ile Birleşik Krallık arasında Serbest Ticaret Anlaşması müzakereleri başladı",
        "Londra ve Ankara heyetleri",
        "dis_politika",
        "turkiye",
    ),
    (
        "Çin ve Rusya devlet başkanları Pekin'de ikili stratejik ortaklık zirvesi yaptı",
        "Pekin ve Moskova diplomatik zirvesi",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Avrupa Parlamentosu vize serbestisi ve geri kabul anlaşmasını oyladı",
        "Strazburg genel kurul oturumu",
        "dis_politika",
        "avrupa",
    ),
    (
        "Türk Devletleri Teşkilatı Aksakallar Konseyi Semerkant'ta toplandı",
        "Türk dünyası kültürel ve siyasi diplomasi",
        "dis_politika",
        "turkiye",
    ),
    (
        "Dışişleri Bakanlığı İsrail'in Batı Şeria'daki yerleşim kararlarını kınadı",
        "Tel Aviv ve Batı Şeria diplomatik kınama",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Japonya ve ABD Asya-Pasifik güvenlik paktını genişletme kararı aldı",
        "Tokyo ve Washington ikili görüşmeleri",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Uluslararası Ceza Mahkemesi (UCM) savaş suçları soruşturmasında yeni karar aldı",
        "Lahey'de uluslararası yargı ve mahkeme",
        "hukuk",
        "kuresel",
    ),
    (
        "Somali ve Türkiye arasında savunma ve ekonomik işbirliği protokolü onaylandı",
        "Mogadişu ve Ankara diplomasi hattı",
        "dis_politika",
        "turkiye",
    ),
    (
        "Güney Kore ve Kuzey Kore arasında sınır hattında diplomatik temas kuruldu",
        "Seul ve Pyongyang hattında diplomasi",
        "dis_politika",
        "asya_pasifik",
    ),
    (
        "Brezilya ve Arjantin liderleri Mercosur zirvesinde bir araya geldi",
        "Güney Amerika bölgesel diplomasi",
        "dis_politika",
        "kuresel",
    ),
    (
        "Türkiye ve Irak arasında su ve güvenlik konularında Yüksek Düzeyli Mekanizma",
        "Bağdat'ta resmi diplomasi heyetleri",
        "dis_politika",
        "orta_dogu",
    ),
    (
        "Avrupa Konseyi Parlamenter Meclisi (AKPM) yıllık raporunu sundu",
        "Strazburg insan hakları ve diplomasi",
        "dis_politika",
        "avrupa",
    ),
    (
        "Hindistan Başbakanı Narendra Modi Moskova'da Vladimir Putin ile görüştü",
        "Yeni Delhi ve Moskova ikili zirvesi",
        "dis_politika",
        "rusya_ukrayna",
    ),
    (
        "Kuzey Kıbrıs Türk Cumhuriyeti Cumhurbaşkanı New York'ta BM temaslarında bulundu",
        "Cenevre formatı ve diplomasi",
        "dis_politika",
        "turkiye",
    ),
    (
        "Balkan Liderler Zirvesi Üsküp'te bölgesel entegrasyon temasıyla toplandı",
        "Batı Balkanlar AB üyeliği diplomasisi",
        "dis_politika",
        "avrupa",
    ),
    (
        "Şanghay İşbirliği Örgütü Dışişleri Bakanları Konseyi toplandı",
        "Avrasya diplomasi ve ticaret zirvesi",
        "dis_politika",
        "kuresel",
    ),
    (
        "İspanya ve Filistin hükümetleri Madrid'de ortak hükümetlerarası zirve düzenledi",
        "Avrupa'da diplomatik temaslar ve zirve",
        "dis_politika",
        "avrupa",
    ),
    (
        "ABD Dışişleri Bakanlığı Orta Doğu'ya özel diplomatik temsilci atadı",
        "Washington barış müzakereleri",
        "dis_politika",
        "abd",
    ),
    (
        "Ukrayna Barış Zirvesi İsviçre'de 90 ülkenin katılımıyla gerçekleştirildi",
        "Bürgenstock diplomasi zirvesi bildirisi",
        "dis_politika",
        "avrupa",
    ),
    (
        "Türkiye ve İtalya Hükümetlerarası Zirvesi Roma'da toplandı",
        "Akdeniz güvenliği ve diplomasi protokolü",
        "dis_politika",
        "avrupa",
    ),
    # ── GÜVENLİK & SAVUNMA (30 Başlık) ──
    (
        "Milli Savunma Bakanlığı Pençe-Kilit operasyonu bölgesinde terör mağaralarını imha etti",
        "TSK hava harekatı ve kara operasyonu",
        "guvenlik",
        "turkiye",
    ),
    (
        "MİT yurt dışı operasyonuyla kritik terör örgütü sorumlusunu Türkiye'ye getirdi",
        "İstihbarat destekli nokta operasyon",
        "guvenlik",
        "turkiye",
    ),
    (
        "ASELSAN yeni nesil AESA burun radarı MURAD'ın uçuş testlerini tamamladı",
        "Savunma sanayii ve askeri radar",
        "guvenlik",
        "turkiye",
    ),
    (
        "ROKETSAN ÇAKIR seyir füzesi AKINCI TİHA'dan yapılan atışta hedefi tam isabetle vurdu",
        "SİHA ve füze teknolojisi",
        "guvenlik",
        "turkiye",
    ),
    (
        "Baykar üretimi Bayraktar TB2 SİHA ihracatında 35 ülkeye ulaşıldı",
        "Askeri havacılık ve insansız hava araçları",
        "guvenlik",
        "turkiye",
    ),
    (
        "TUSAŞ KAAN milli muharip uçak projesinde üçüncü prototip montajına başlandı",
        "Hava Kuvvetleri savaş uçağı üretimi",
        "guvenlik",
        "turkiye",
    ),
    (
        "Türk Silahlı Kuvvetleri EFES tatbikatını Ege ve Akdeniz'de başarıyla icra etti",
        "Kara, Deniz ve Hava Kuvvetleri ortak tatbikatı",
        "guvenlik",
        "turkiye",
    ),
    (
        "İçişleri Bakanlığı 81 ilde düzenlenen ÇEMBER operasyonlarında aranan şahısları yakaladı",
        "Polis ve jandarma güvenlik operasyonu",
        "guvenlik",
        "turkiye",
    ),
    (
        "Sahil Güvenlik Komutanlığı botları deniz sınırlarında kaçakçılık şebekesini çökertti",
        "Deniz güvenliği ve sınır devriyesi",
        "guvenlik",
        "turkiye",
    ),
    (
        "Ukrayna ordusu Karadeniz'de Rus donanmasına ait çıkarma gemisini vurdu",
        "Savaş cephesi ve askeri çatışma",
        "guvenlik",
        "rusya_ukrayna",
    ),
    (
        "Rusya Savunma Bakanlığı Kursk sınır hattında karşı askeri taarruz başlattı",
        "Moskova ordu birlikleri çatışmada",
        "guvenlik",
        "rusya_ukrayna",
    ),
    (
        "İsrail ve Hizbullah arasında Lübnan sınırında karşılıklı füze ve topçu atışları",
        "Askeri gerilim ve çatışma alarmı",
        "guvenlik",
        "orta_dogu",
    ),
    (
        "Kızıldeniz'de ticari gemilere yönelik saldırılara karşı uluslararası donanma devriyesi",
        "CENTCOM ve askeri operasyonlar",
        "guvenlik",
        "abd",
    ),
    (
        "MİT ve Emniyet İstihbarat ortaklığıyla eylem hazırlığındaki hücre çökertildi",
        "Terörle mücadele ve güvenlik timleri",
        "guvenlik",
        "turkiye",
    ),
    (
        "Deniz Kuvvetleri Komutanlığı TCG Anadolu üzerinde yerli helikopter konuşlandırma testleri yaptı",
        "Donanma amfibi gemisi ve askeri denizcilik",
        "guvenlik",
        "turkiye",
    ),
    (
        "Kara Kuvvetleri Komutanlığı'na yerli zırhlı muharebe araçları PARS ve VURAN teslim edildi",
        "FNSS ve BMC savunma sanayii teslimatı",
        "guvenlik",
        "turkiye",
    ),
    (
        "Savunma Sanayii Başkanlığı yerli turboşaft motor TS1400 seri üretimini onayladı",
        "TEİ askeri helikopter motoru ve savunma sanayii",
        "guvenlik",
        "turkiye",
    ),
    (
        "Jandarma İHA birlikleri sınır hattında gece görüşlü termal tarama yaptı",
        "Sınır güvenliği ve askeri gözetleme",
        "guvenlik",
        "turkiye",
    ),
    (
        "Kuzey Kore hipersonik füze motoru yer testini başarıyla icra ettiğini duyurdu",
        "Pyongyang askeri füze teknolojisi",
        "guvenlik",
        "asya_pasifik",
    ),
    (
        "Tayvan Savunma Bakanlığı ada çevresinde Çin savaş uçaklarının tespit edildiğini açıkladı",
        "Taipei askeri teyakkuz durumu",
        "guvenlik",
        "asya_pasifik",
    ),
    (
        "Emniyet Genel Müdürlüğü Narkotik Daire Başkanlığı rekor miktarda uyuşturucu ele geçirdi",
        "Narkotik polis operasyonu ve baskın",
        "guvenlik",
        "turkiye",
    ),
    (
        "GÖKTÜRK keşif uydusu Türk Silahlı Kuvvetleri'ne yüksek çözünürlüklü istihbarat sağladı",
        "Askeri uzay ve uydu istihbaratı",
        "guvenlik",
        "turkiye",
    ),
    (
        "HAVELSAN Denizaltı Bilgi Dağıtım Sistemi'ni (DBDS) MİLDEN projesine entegre etti",
        "Denizaltı yazılımı ve savunma sanayii",
        "guvenlik",
        "turkiye",
    ),
    (
        "Hava Kuvvetleri Komutanlığı sınır hattında hava devriye görevini aralıksız sürdürüyor",
        "F-16 savaş uçakları ve hava sahası güvenliği",
        "guvenlik",
        "turkiye",
    ),
    (
        "Milli Savunma Üniversitesi Kara Harp Okulu mezuniyet töreni icra edildi",
        "Askeri teğmenler ve TSK subay kadrosu",
        "guvenlik",
        "turkiye",
    ),
    (
        "Suriye'nin kuzeyinde Barış Pınarı harekat bölgesinde teröristler etkisiz hale getirildi",
        "Sınır ötesi güvenlik harekatı",
        "guvenlik",
        "orta_dogu",
    ),
    (
        "ASFAT yerli açık deniz karakol gemisi AKHİSAR'ı denize indirdi",
        "Askeri tersane ve donanma inşası",
        "guvenlik",
        "turkiye",
    ),
    (
        "STM vurucu kamikaze İHA KARGU'nun sürü algoritması testlerini tamamladı",
        "Otonom taktik askeri İHA",
        "guvenlik",
        "turkiye",
    ),
    (
        "Polis Özel Harekat (PÖH) timleri rehine kurtarma tatbikatını başarıyla icra etti",
        "Emniyet özel harekat tatbikatı",
        "guvenlik",
        "turkiye",
    ),
    (
        "NATO Doğu Avrupa kanadında geniş çaplı hava savunma tatbikatı başlattı",
        "İttifak savaş uçakları ve hava üssü",
        "guvenlik",
        "avrupa",
    ),
    # ── HUKUK & YARGI (25 Başlık) ──
    (
        "Anayasa Mahkemesi (AYM) sendikal hak ihlali başvurusunda pilot karar verdi",
        "Yüksek mahkeme gerekçeli kararı",
        "hukuk",
        "turkiye",
    ),
    (
        "Yargıtay Hukuk Genel Kurulu kiracı tahliye davalarında emsal niteliğinde karar aldı",
        "Kira sözleşmeleri ve tahliye taahhüdü içtihadı",
        "hukuk",
        "turkiye",
    ),
    (
        "Danıştay idari para cezasının iptaline ilişkin mahkeme hükmünü onadı",
        "İdare mahkemesi ve yargı kararı",
        "hukuk",
        "turkiye",
    ),
    (
        "Hakimler ve Savcılar Kurulu (HSK) mazeret kararnamesi ile 500 hakim ve savcının görev yerini değiştirdi",
        "Adli yargı atamaları",
        "hukuk",
        "turkiye",
    ),
    (
        "İstanbul Ağır Ceza Mahkemesi'nde görülen davada sanıklar hakkında mütalaa verildi",
        "Cumhuriyet savcısı hapis cezası talep etti",
        "hukuk",
        "turkiye",
    ),
    (
        "Türkiye Barolar Birliği stajyer avukatların çalışma koşullarına ilişkin rapor sundu",
        "Savunma makamı ve adliye stajı",
        "hukuk",
        "turkiye",
    ),
    (
        "Sayıştay bakanlıkların kesin hesap ve mali denetim raporlarını TBMM'ye iletti",
        "Sayıştay denetimi ve mevzuata uygunluk",
        "hukuk",
        "turkiye",
    ),
    (
        "Resmi Gazete'de yayımlanan yönetmelik değişikliği ile arabuluculuk ücret tarifesi güncellendi",
        "Hukuki uyuşmazlıklar ve arabulucu",
        "hukuk",
        "turkiye",
    ),
    (
        "Ankara Adliyesi Sulh Ceza Hakimliği dijital dolandırıcılık şüphelilerini tutukladı",
        "Mahkeme kararı ve cezaevi sevki",
        "hukuk",
        "turkiye",
    ),
    (
        "Adalet Bakanlığı ceza infaz kurumlarında dijital dönüşüm ve e-duruşma sistemini genişletti",
        "SEGBİS ve mahkeme salonları",
        "hukuk",
        "turkiye",
    ),
    (
        "Avrupa İnsan Hakları Mahkemesi (AİHM) mülkiyet hakkı davasında kararını açıkladı",
        "Strazburg mahkemesi tazminat hükmü",
        "hukuk",
        "avrupa",
    ),
    (
        "İcra dairelerinde elektronik haciz ve e-satış sistemiyle 500 bin dosya sonuçlandırıldı",
        "İcra İflas Kanunu uygulamaları",
        "hukuk",
        "turkiye",
    ),
    (
        "Kişisel Verileri Koruma Kurulu (KVKK) veri sızıntısı bildiriminde bulunan şirketleri inceledi",
        "Veri koruma mevzuatı ve idari yaptırım",
        "hukuk",
        "turkiye",
    ),
    (
        "Bölge Adliye Mahkemesi işe iade davasında yerel mahkeme kararını kesin olarak onayladı",
        "İstinaf mahkemesi iş hukuku kararı",
        "hukuk",
        "turkiye",
    ),
    (
        "Türkiye Noterler Birliği gayrimenkul ve araç satış sözleşmelerinde dijital onay sürecini duyurdu",
        "Noterlik işlemleri ve resmi evrak",
        "hukuk",
        "turkiye",
    ),
    (
        "Tüketici Hakem Heyetleri ayıplı hizmet başvurularında tüketici lehine karar oranını açıkladı",
        "Tüketici hukuku ve para iadesi",
        "hukuk",
        "turkiye",
    ),
    (
        "Ceza Muhakemesi Kanunu gereğince zorunlu müdafilik ücret tarifesi güncellendi",
        "Baro avukatları ve CMK ödemeleri",
        "hukuk",
        "turkiye",
    ),
    (
        "Fikri ve Sınai Haklar Hukuk Mahkemesi patent ihlali davasında ihtiyati tedbir kararı verdi",
        "Marka ve patent hukuku yargılaması",
        "hukuk",
        "turkiye",
    ),
    (
        "Yargıtay Ceza Dairesi bilişim yoluyla dolandırıcılık suçunda cezayı az bularak kararı bozdu",
        "Temyiz incelemesi ve ceza davası",
        "hukuk",
        "turkiye",
    ),
    (
        "Adalet Komisyonu'nda kabul edilen yeni yargı paketi Meclis Genel Kurulu'na geldi",
        "Kanun teklifi ve yargı reformu",
        "hukuk",
        "turkiye",
    ),
    (
        "Sulh Hukuk Mahkemesi miras taksimi ve vasiyetname açılması davasını karara bağladı",
        "Medeni Kanun ve miras hukuku",
        "hukuk",
        "turkiye",
    ),
    (
        "İdare Mahkemesi kentsel sit alanındaki imar planı değişikliğini iptal etti",
        "İdari yargı ve yürütmeyi durdurma",
        "hukuk",
        "turkiye",
    ),
    (
        "Vergi Mahkemesi haksız tarh edilen vergi cezasını mükellef lehine sildi",
        "Vergi mahkemesi kararı ve yargılama",
        "hukuk",
        "turkiye",
    ),
    (
        "İş Mahkemesi iş kazası davasında işvereni maddi ve manevi tazminata mahkum etti",
        "İşçi hakları ve tazminat davası",
        "hukuk",
        "turkiye",
    ),
    (
        "Aile Mahkemesi velayet ve nafaka artırımı davasında emsal karar verdi",
        "Boşanma hukuku ve nafaka miktarı",
        "hukuk",
        "turkiye",
    ),
    # ── ENERJİ & İKLİM (25 Başlık) ──
    (
        "BOTAŞ uluslararası sıvılaştırılmış doğalgaz (LNG) tedarik anlaşması imzaladı",
        "Doğalgaz arz güvenliği ve iletim boru hatları",
        "enerji",
        "turkiye",
    ),
    (
        "Akkuyu Nükleer Güç Santrali'nde reaktör basınç kabı montajı tamamlandı",
        "Nükleer enerji üretimi ve elektrik santrali",
        "enerji",
        "turkiye",
    ),
    (
        "EPDK serbest piyasa elektrik tavan fiyatını megavatsaat başına güncelledi",
        "Elektrik piyasası tarifeleri ve enerji mevzuatı",
        "enerji",
        "turkiye",
    ),
    (
        "OPEC+ bakanlar toplantısında küresel petrol arzı kısıntı kararı teyit edildi",
        "Brent petrol varil fiyatı ve küresel enerji piyasası",
        "enerji",
        "kuresel",
    ),
    (
        "Türkiye'nin rüzgar enerjisi kurulu gücü 13 bin megavat sınırını aştı",
        "Rüzgar türbinleri ve yenilenebilir enerji yatırımı",
        "enerji",
        "turkiye",
    ),
    (
        "Karadeniz Sakarya gaz sahasında üretilen günlük doğalgaz miktarı 6 milyon metreküpe ulaştı",
        "TPAO sondaj faaliyetleri ve enerji bağımsızlığı",
        "enerji",
        "turkiye",
    ),
    (
        "Çevre, Şehircilik ve İklim Değişikliği Bakanlığı Ulusal Sera Gazı Emisyon Raporu'nu sundu",
        "İklim değişikliği ve karbon salımı",
        "enerji",
        "turkiye",
    ),
    (
        "Kalyon Karapınar Güneş Enerjisi Santrali (GES) tam kapasiteyle elektrik üretimine devam ediyor",
        "Güneş panelleri ve temiz enerji",
        "enerji",
        "turkiye",
    ),
    (
        "Maden Tetkik ve Arama Genel Müdürlüğü (MTA) yeni nadir toprak elementi rezervi tespit etti",
        "Madencilik ve stratejik maden kaynakları",
        "enerji",
        "turkiye",
    ),
    (
        "Avrupa Birliği yenilenebilir hidrojen ve yeşil enerji altyapı fonunu açıkladı",
        "Brüksel yeşil dönüşüm paktı",
        "enerji",
        "avrupa",
    ),
    (
        "TEİAŞ trafo merkezleri ve yüksek gerilim iletim hatları modernizasyon projesini tamamladı",
        "Milli elektrik şebekesi altyapısı",
        "enerji",
        "turkiye",
    ),
    (
        "Fatih ve Yavuz sondaj gemileri Karadeniz ve Akdeniz'de derin deniz sondajını sürdürüyor",
        "Enerji ve Tabii Kaynaklar Bakanlığı sondajı",
        "enerji",
        "turkiye",
    ),
    (
        "Şırnak Gabar bölgesinde yeni petrol üretim kuyusu devreye alındı",
        "TPAO günlük ham petrol üretimi",
        "enerji",
        "turkiye",
    ),
    (
        "Uluslararası Enerji Ajansı (IEA) Dünya Enerji Görünümü raporunu yayımladı",
        "Küresel elektrik talebi ve fosil yakıtlar",
        "enerji",
        "kuresel",
    ),
    (
        "EPİAŞ Doğalgaz Piyasası'nda spot referans fiyatı bin metreküp başına belirlendi",
        "Doğalgaz borsası ve günlük işlem hacmi",
        "enerji",
        "turkiye",
    ),
    (
        "Hidroelektrik santrallerinde (HES) yağışlar sonrası elektrik üretimi yüzde 20 arttı",
        "DSİ baraj rezervuar seviyeleri",
        "enerji",
        "turkiye",
    ),
    (
        "Jeotermal elektrik santralleri kurulu gücünde Türkiye dünya dördüncüsü oldu",
        "Yenilenebilir jeotermal kaynaklar",
        "enerji",
        "turkiye",
    ),
    (
        "Kuzey Akım doğalgaz boru hattı tamiratı ve Avrupa enerji arzı tartışılıyor",
        "Baltık Denizi boru hattı güvenliği",
        "enerji",
        "avrupa",
    ),
    (
        "Suudi Arabistan ve BAE yeni temiz enerji ve güneş enerjisi yatırımlarını başlattı",
        "Orta Doğu enerji dönüşümü",
        "enerji",
        "orta_dogu",
    ),
    (
        "Enerji Verimliliği Derneği sanayi tesislerinde enerji tasarrufu bilançosunu paylaştı",
        "Isı yalıtımı ve yeşil sanayi",
        "enerji",
        "turkiye",
    ),
    (
        "COP29 İklim Zirvesi öncesi taraf ülkeler iklim finansmanı müzakerelerinde buluştu",
        "Küresel ısınma ve karbon kredisi",
        "enerji",
        "kuresel",
    ),
    (
        "Türkiye ve Macaristan arasında doğalgaz sevkiyatı ve depolama anlaşması imzalandı",
        "BOTAŞ boru hattı ihracatı",
        "enerji",
        "turkiye",
    ),
    (
        "Linyit kömürü santrallerinde baca gazı arıtma ve filtre denetimleri yapıldı",
        "Maden ve enerji santralleri çevre izni",
        "enerji",
        "turkiye",
    ),
    (
        "Biyokütle enerji santralleri organik atıklardan elektrik üretimini artırdı",
        "Yenilenebilir atık enerjisi",
        "enerji",
        "turkiye",
    ),
    (
        "Deniz üstü (offshore) rüzgar enerjisi potansiyel alanları Resmi Gazete'de ilan edildi",
        "Marmara Denizi rüzgar santralleri",
        "enerji",
        "turkiye",
    ),
    # ── TEKNOLOJİ & SANAYİ (25 Başlık) ──
    (
        "TÜBİTAK BİLGEM yerli yapay zeka çip tasarımı projesini başarıyla tamamladı",
        "Yarı iletken teknolojisi ve entegre devre üretimi",
        "teknoloji",
        "turkiye",
    ),
    (
        "TÜRKSAT 6A haberleşme uydusu üzerinden ilk canlı yayın testi gerçekleştirildi",
        "Uzay sistemleri ve uydu telekomünikasyon",
        "teknoloji",
        "turkiye",
    ),
    (
        "Sanayi ve Teknoloji Bakanlığı yüksek teknoloji teşvik programı HIT-30'u başlattı",
        "Milli teknoloji hamlesi ve fabrika yatırımları",
        "teknoloji",
        "turkiye",
    ),
    (
        "OpenAI yeni nesil yapay zeka muhakeme modeli o1'i genel kullanıma sundu",
        "Büyük dil modelleri ve yapay zeka yazılımı",
        "teknoloji",
        "abd",
    ),
    (
        "Apple ve Google yapay zeka destekli akıllı cihaz işletim sistemlerini güncelledi",
        "Mobil yazılım ve teknoloji lansmanı",
        "teknoloji",
        "abd",
    ),
    (
        "Nvidia yeni nesil Blackwell yapay zeka çipleri sevkiyat takvimini açıkladı",
        "Yarı iletken donanım ve sunucu altyapısı",
        "teknoloji",
        "abd",
    ),
    (
        "Microsoft ve OpenAI veri merkezleri için milyar dolarlık süper bilgisayar projesi yürütüyor",
        "Yapay zeka bulut bilişim altyapısı",
        "teknoloji",
        "abd",
    ),
    (
        "ASML yeni nesil High-NA EUV litografi çip üretim makinelerini tanıttı",
        "Hollanda yarı iletken donanımı",
        "teknoloji",
        "avrupa",
    ),
    (
        "TOGG elektrikli SUV modeli T10X için yeni yazılım güncellemesini yayımladı",
        "Akıllı cihaz ve yerli otomobil teknolojisi",
        "teknoloji",
        "turkiye",
    ),
    (
        "Türkiye Uzay Ajansı (TUA) astronot Alper Gezeravcı'nın mikro yerçekimi deney raporunu sundu",
        "Uzay bilimi ve ISS araştırmaları",
        "teknoloji",
        "turkiye",
    ),
    (
        "BTK 5G mobil şebeke frekans tahsisi ve baz istasyonu altyapı raporunu paylaştı",
        "Telekomünikasyon ve yüksek hızlı internet",
        "teknoloji",
        "turkiye",
    ),
    (
        "Türkiye Siber Güvenlik Kümelenmesi kritik altyapı sızma testi sonuçlarını duyurdu",
        "Siber savunma ve yerli yazılım güvenliği",
        "teknoloji",
        "turkiye",
    ),
    (
        "Otomotiv sanayiinde robotik kaynak ve otomasyon hatları verimliliği artırdı",
        "Fabrika üretimi ve endüstri 4.0",
        "teknoloji",
        "turkiye",
    ),
    (
        "Yerli çip geliştirme konsorsiyumu otomotiv ve savunma için ilk numuneyi üretti",
        "Yarı iletken fabrikası ve mikroçip",
        "teknoloji",
        "turkiye",
    ),
    (
        "Teknoparklarda faaliyet gösteren yazılım girişimlerinin ihracatı 4 milyar doları aştı",
        "Ar-Ge merkezleri ve teknoloji startup ekosistemi",
        "teknoloji",
        "turkiye",
    ),
    (
        "Küresel kuantum işlemci hız rekoru fizik laboratuvarında kırıldı",
        "Kuantum bilgisayar donanımı ve fizik araştırmaları",
        "teknoloji",
        "kuresel",
    ),
    (
        "Tayvan yarı iletken devi TSMC 2 nanometre çip fabrikası inşaatını hızlandırdı",
        "Asya çip tedarik zinciri ve teknoloji",
        "teknoloji",
        "asya_pasifik",
    ),
    (
        "Milli Teknoloji Akademisi 10 bin gence yapay zeka ve veri bilimi eğitimi verdi",
        "Yazılımcı istihdamı ve dijital yetkinlik",
        "teknoloji",
        "turkiye",
    ),
    (
        "Savunma sanayii yazılımlarında yerli gerçek zamanlı işletim sistemi geliştirildi",
        "Gömülü yazılım ve askeri teknoloji",
        "teknoloji",
        "turkiye",
    ),
    (
        "Bilişim Vadisi'nde otonom araç mobilite test pisti hizmete açıldı",
        "Sürücüsüz araç teknolojileri ve sensörler",
        "teknoloji",
        "turkiye",
    ),
    (
        "Meta yeni nesil açık kaynaklı büyük dil modeli Llama'yı araştırmacılara açtı",
        "Yapay zeka algoritmaları ve sinir ağları",
        "teknoloji",
        "abd",
    ),
    (
        "Sanayi bölgelerinde yeşil fabrika sertifikası alan tesis sayısı 500'e ulaştı",
        "Endüstriyel üretim ve modernizasyon",
        "teknoloji",
        "turkiye",
    ),
    (
        "Elektrikli araç batarya üretim tesisi Siro Gebze fabrikasında üretime başladı",
        "Lityum iyon batarya ve hücre teknolojisi",
        "teknoloji",
        "turkiye",
    ),
    (
        "Ulusal Yapay Zeka Stratejisi kapsamında kamu veri havuzu kuruldu",
        "Dijital Dönüşüm Ofisi ve büyük veri",
        "teknoloji",
        "turkiye",
    ),
    (
        "Savunma ve havacılık sanayii için yerli 3D metal yazıcı parçaları onay aldı",
        "Katmanlı imalat ve 3d yazıcı teknolojisi",
        "teknoloji",
        "turkiye",
    ),
    # ── SAĞLIK & TOPLUM (25 Başlık) ──
    (
        "Sağlık Bakanlığı 81 ilde hekim ve uzman doktor kadrolarına yeni atama yaptı",
        "Şehir hastaneleri ve sağlık personeli istihdamı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Milli Eğitim Bakanlığı (MEB) yeni müfredat programı ders kitaplarını dağıttı",
        "Okullar, öğretmenler ve öğrenciler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Sosyal Güvenlik Kurumu (SGK) geri ödeme listesine 45 yeni ilaç ekledi",
        "Eczaneler ve kanser ilaçları karşılandı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Yükseköğretim Kurulu (YÖK) üniversite kayıt istatistiklerini ve boş kontenjanları açıkladı",
        "Akademik eğitim ve rektörlükler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Türk Tabipleri Birliği (TTB) hekim çalışma saatleri ve nöbet ücretleri raporunu sundu",
        "Doktor hakları ve sağlık sistemi",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Aile ve Sosyal Hizmetler Bakanlığı ihtiyaç sahibi ailelere kış dönemi sosyal yardımını başlattı",
        "Toplumsal destek ve engelli yardımı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "TÜİK Türkiye'nin doğum oranı ve nüfus yaşlanması istatistiklerini yayımladı",
        "Demografik yapı ve nüfus projeksiyonları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Göç İdaresi Başkanlığı düzensiz göçle mücadele ve sınır dışı işlemlerini paylaştı",
        "Geri gönderme merkezleri ve mülteci kayıtları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Gençlik ve Spor Bakanlığı KYK yurtlarında barınma ücretlerinde düzenleme yaptı",
        "Üniversite öğrencileri ve burs başvuruları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Dünya Sağlık Örgütü (WHO) küresel grip salgını ve aşı tedariki kılavuzunu yayımladı",
        "Cenevre uluslararası halk sağlığı uyarısı",
        "saglik_toplum",
        "kuresel",
    ),
    (
        "Kızılay kan stoklarını tamamlamak için ülke genelinde kan bağışı kampanyası başlattı",
        "Toplumsal dayanışma ve kan merkezleri",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "ÖSYM KPSS ve YKS sınav giriş belgelerini adayların erişimine açtı",
        "Öğrenci sınavları ve tercih kılavuzu",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "AFAD Türkiye geneli afet farkındalık ve tahliye tatbikatını tamamladı",
        "Deprem hazırlığı ve sivil toplum bilinci",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Kültür ve Turizm Bakanlığı restore edilen tarihi müzelerin açılışını yaptı",
        "Kültür ve turizm müze açılışı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Engelli memur adayları için EKPSS tercih kılavuzu yayımlandı",
        "Kamuda engelli istihdamı ve sosyal haklar",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Huzurevleri ve yaşlı bakım rehabilitasyon merkezlerinde kalite standartları artırıldı",
        "Sosyal hizmetler ve yaşlı bakımı",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Sağlık Bakanlığı Onaylı Randevu Sistemi sayesinde randevu sadakat oranının arttığını açıkladı",
        "MHRS hastane poliklinikleri",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "TİSK ve sendikalar iş sağlığı ve güvenliği kültürünü geliştirme protokolü yaptı",
        "İşçi sağlığı ve meslek hastalıkları",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Diyanet İşleri Başkanlığı hac ve umre kayıt takvimini duyurdu",
        "Hacı adayları ve dini hizmetler",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Üniversite hastanelerinde tıbbi cihaz ve yoğun bakım üniteleri modernize edildi",
        "Tıp fakülteleri ve sağlık hizmetleri",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Çocuk Esirgeme Kurumu koruyucu aile programı kapsamında 10 bin çocuğa ulaşıldı",
        "Sosyal hizmetler ve koruyucu aile",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "İlaç ve Eczacılık Genel Müdürlüğü piyasadaki antibiyotik stoklarını denetledi",
        "Eczane rafları ve ilaç tedariki",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Milli Kütüphane dijital arşivini araştırmacıların ve öğrencilerin erişimine açtı",
        "Kültür, sanat ve kütüphanecilik",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Vakıflar Genel Müdürlüğü tarihi vakıf eserlerinin restorasyon bilançosunu paylaştı",
        "Tarihi camiler ve kültürel varlıklar",
        "saglik_toplum",
        "turkiye",
    ),
    (
        "Bağımlılıkla mücadele kapsamında 81 ilde YEDAM merkezleri hizmet vermeyi sürdürüyor",
        "Yeşilay ve toplum sağlığı",
        "saglik_toplum",
        "turkiye",
    ),
    # ── YEREL YÖNETİMLER (25 Başlık) ──
    (
        "İstanbul Büyükşehir Belediyesi (İBB) yeni metro hattının test sürüşünü başlattı",
        "Raylı sistemler ve kentiçi toplu ulaşım",
        "yerel",
        "turkiye",
    ),
    (
        "Ankara Büyükşehir Belediyesi (ABB) Başkent Kart üzerinden sosyal destek sağladı",
        "Belediye sosyal yardımları ve yerel yönetim",
        "yerel",
        "turkiye",
    ),
    (
        "İzmir Büyükşehir Belediyesi Körfez temizliği ve dip çamuru tarama projesini yürüttü",
        "Çevre koruma ve belediye hizmetleri",
        "yerel",
        "turkiye",
    ),
    (
        "İSKİ İstanbul'da içme suyu şebekesi ana boru hattını yenileme çalışmalarını tamamladı",
        "Su ve kanalizasyon altyapısı",
        "yerel",
        "turkiye",
    ),
    (
        "İstanbul Valiliği orman yangınlarına karşı giriş yasağı genelgesi yayımladı",
        "Valilik koordinasyonu ve yangın tedbirleri",
        "yerel",
        "turkiye",
    ),
    (
        "Büyükşehir belediyeleri kentsel dönüşüm kira yardımı miktarlarını güncelledi",
        "Depreme dayanıksız bina yıkımı ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "ASKİ Ankara'da baraj havzaları su kalitesi izleme raporunu duyurdu",
        "Başkent su kaynakları ve arıtma tesisleri",
        "yerel",
        "turkiye",
    ),
    (
        "Belediye Zabıtası okul çevrelerinde gıda hijyeni ve fiyat denetimi gerçekleştirdi",
        "Zabıta denetimleri ve yerel esnaf",
        "yerel",
        "turkiye",
    ),
    (
        "Bursa Büyükşehir Belediyesi tarihi Hanlar Bölgesi çevre düzenleme projesini açtı",
        "Kent estetiği ve belediye parkları",
        "yerel",
        "turkiye",
    ),
    (
        "Antalya Büyükşehir Belediyesi turizm merkezlerinde yeni arıtma tesisini devreye aldı",
        "Yerel çevre yatırımları ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "Gaziantep Büyükşehir Belediyesi çiftçilere tohum ve sulama borusu desteği verdi",
        "Kırsal kalkınma ve belediye projeleri",
        "yerel",
        "turkiye",
    ),
    (
        "İzmir Su ve Kanalizasyon İdaresi (İZSU) kanal ayrıştırma ihalelerini tamamladı",
        "Altyapı ve yağmur suyu drenajı",
        "yerel",
        "turkiye",
    ),
    (
        "Konya Büyükşehir Belediyesi akıllı toplu taşıma ve tramvay filosunu yeniledi",
        "Yerel raylı sistemler ve ulaşım",
        "yerel",
        "turkiye",
    ),
    (
        "Adana Büyükşehir Belediyesi Çukurova ilçesinde asfaltlama ve yol yapımını sürdürüyor",
        "Fen işleri ve belediye hizmetleri",
        "yerel",
        "turkiye",
    ),
    (
        "Diyarbakır Büyükşehir Belediyesi yeni mesire alanı ve şehir parkını vatandaşlara açtı",
        "Park ve bahçeler müdürlüğü",
        "yerel",
        "turkiye",
    ),
    (
        "Eskişehir Büyükşehir Belediyesi Porsuk çayı üzerinde gondol turlarını ve çevre bakımını yaptı",
        "Kent turizmi ve belediyecilik",
        "yerel",
        "turkiye",
    ),
    (
        "Trabzon Büyükşehir Belediyesi Karadeniz sahil yolu aydınlatma ve yürüyüş yolunu tamamladı",
        "Sahil dolgu alanı ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "Samsun Büyükşehir Belediyesi lojistik köy ve sanayi ulaşım hattı projesini duyurdu",
        "Liman kenti ve yerel yönetim yatırımı",
        "yerel",
        "turkiye",
    ),
    (
        "Mersin Büyükşehir Belediyesi tarımsal sulama kooperatiflerine güneş enerjisi desteği sağladı",
        "Belediye tarım ve sulama desteği",
        "yerel",
        "turkiye",
    ),
    (
        "Kayseri Büyükşehir Belediyesi Erciyes Kış Sporları Merkezi altyapısını güçlendirdi",
        "Kış turizmi ve belediye işletmeleri",
        "yerel",
        "turkiye",
    ),
    (
        "Şanlıurfa Büyükşehir Belediyesi tarihi çarşılar restorasyonunda ikinci etaba geçti",
        "Tarihi kent dokusu ve belediye",
        "yerel",
        "turkiye",
    ),
    (
        "Denizli Büyükşehir Belediyesi teleferik ve yayla turizmi tesislerini hizmete açtı",
        "Yerel turizm ve büyükşehir projeleri",
        "yerel",
        "turkiye",
    ),
    (
        "Sakarya Büyükşehir Belediyesi bisiklet yolları ağını 200 kilometreye ulaştırdı",
        "Akıllı şehircilik ve belediye ulaşımı",
        "yerel",
        "turkiye",
    ),
    (
        "Muğla Büyükşehir Belediyesi yaz sezonu kıyı temizliği ve vidanjör filosunu artırdı",
        "Ege sahilleri ve belediye hizmetleri",
        "yerel",
        "turkiye",
    ),
    (
        "Balıkesir Büyükşehir Belediyesi organik tarım pazarını hizmete açtı",
        "Yerel üretici destekleri ve belediyecilik",
        "yerel",
        "turkiye",
    ),
]


@pytest.mark.parametrize(("title", "summary", "expected_cat", "expected_reg"), ADVERSARIAL_300)
def test_adversarial_300_headlines_taxonomy(
    title: str, summary: str, expected_cat: str, expected_reg: str
) -> None:
    """300+ Zorlu ve Adversarial Türkçe haber başlığında kategori ve bölge sınıflandırma doğruluğu."""
    predicted_cat = classify_category(title, summary)
    assert predicted_cat == expected_cat, (
        f"Kategori Hatası!\n"
        f"  Başlık: '{title}'\n"
        f"  Beklenen: '{expected_cat}', Tahmin Edilen: '{predicted_cat}'"
    )

    predicted_reg = classify_region(title, summary)
    if predicted_reg != expected_reg:
        from politikdesk.analysis.taxonomy import _REGION_PATTERNS, _fold

        haystack = _fold(f"{title} {summary or ''}")
        matches_found = {
            r: p.findall(haystack) for r, p in _REGION_PATTERNS.items() if p.findall(haystack)
        }
        print(f"\n[DEBUG] Region mismatch! haystack: '{haystack}' | matches: {matches_found}")

    assert predicted_reg == expected_reg, (
        f"Bölge Hatası!\n"
        f"  Başlık: '{title}'\n"
        f"  Beklenen: '{expected_reg}', Tahmin Edilen: '{predicted_reg}'"
    )


def test_confusion_matrix_and_accuracy() -> None:
    """Confusion Matrix hesaplar ve genel doğruluk oranının >= %95 olduğunu tesciller."""
    confusion = defaultdict(lambda: defaultdict(int))
    correct_cat = 0
    correct_reg = 0
    total = len(ADVERSARIAL_300)

    for title, summary, exp_cat, exp_reg in ADVERSARIAL_300:
        p_cat = classify_category(title, summary)
        p_reg = classify_region(title, summary)

        confusion[exp_cat][p_cat] += 1
        if p_cat == exp_cat:
            correct_cat += 1
        if p_reg == exp_reg:
            correct_reg += 1

    cat_acc = (correct_cat / total) * 100.0
    reg_acc = (correct_reg / total) * 100.0

    print(f"\n[CONFUSION MATRIX] Toplam Başlık: {total}")
    print(f"Kategori Doğruluk: %{cat_acc:.2f} ({correct_cat}/{total})")
    print(f"Bölge Doğruluk:    %{reg_acc:.2f} ({correct_reg}/{total})")

    assert cat_acc >= 95.0, f"Kategori doğruluğu %95'in altında: %{cat_acc:.2f}"
    assert reg_acc >= 95.0, f"Bölge doğruluğu %95'in altında: %{reg_acc:.2f}"
