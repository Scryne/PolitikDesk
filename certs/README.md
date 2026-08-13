# certs/ — eksik ara sertifikalar (F5-20)

Buradaki dosyalar **kök sertifika değildir** ve güven sınırını genişletmez.
Hepsi zaten güvenilen bir kökün (DigiCert vb.) imzaladığı **ara**
sertifikalardır; yalnızca sunucunun göndermeyi unuttuğu halkayı
tamamlarlar.

## Neden gerekiyor

Bir TLS sunucusu, kendi sertifikasıyla birlikte **ara sertifikaları da
göndermek zorundadır**. Bazı sunucular bunu yapmaz. Tarayıcılar bu hatayı
gizler: eksik halkayı sertifikadaki AIA adresinden kendileri indirir
(*AIA chasing*). Python'un `ssl` modülü bunu YAPMAZ ve doğrulama düşer.

Sonuç, teşhisi zor bir asimetridir: **site tarayıcıda açılır, koddan
açılmaz.**

## Buradaki dosyalar

| Dosya | Kimin için | Kanıt |
|---|---|---|
| `geotrust-tls-rsa-ca-g1.pem` | `resmigazete.gov.tr` | Sunucu yalnızca yaprak sertifikayı gönderiyor; ara sertifika AIA'da ilan edilmiş: `http://cacerts.geotrust.com/GeoTrustTLSRSACAG1.crt` |

## Neden `verify=False` DEĞİL

Doğrulamayı kapatmak sorunu "çözer" ama ürünün kanıt zincirini çürütür:
Tier 1 birincil kaynaktan okuduğumuzu iddia ederken karşı tarafın gerçekten
o kurum olduğunu doğrulamamış oluruz. Ortadaki adam saldırısına açık bir
kanıt, kanıt değildir.

Eksik halkayı eklemek doğrulamayı **açık** tutar.

## Yeni sertifika eklerken

1. Hatanın gerçekten eksik zincir olduğunu doğrulayın — `verify=False` ile
   istek geçiyorsa ama varsayılan demetle `CERTIFICATE_VERIFY_FAILED`
   alıyorsanız muhtemelen budur.
2. Yaprak sertifikanın AIA alanındaki `CA Issuers` adresinden ara
   sertifikayı indirin.
3. **Kök sertifika eklemeyin.** Buraya yalnızca zaten güvenilen bir kökün
   altındaki ara sertifikalar girer.
4. `tests/test_http_client.py` demetin yüklendiğini denetler.
