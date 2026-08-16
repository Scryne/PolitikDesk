"""Olay merkezi (centroid) güncelleme (F2-02).

DoD: Yeni makale eklendiğinde merkez artımlı güncelleniyor; drift testi
geçiyor.

**Pazarlık edilemez kısıt (docs/karar-itirazlari.md, İtiraz-5 mühendislik
notu):** `events.centroid_embedding` her zaman üyelerinden **yeniden
hesaplanabilir** kalmalıdır. Artımlı güncelleme merkezi geri döndürülemez
hale getirmemelidir.

Bu yalnızca teorik bir temizlik değil, iki somut gereksinimin ortak
karşılığıdır:

  1. **Merge/split geri alınabilirliği (F2-05, G2 koşul 8).** Yanlış
     birleştirilmiş bir makale olaydan çıkarılabilmeli ve merkez bozulmadan
     eski haline dönebilmelidir.
  2. **Silme talebi (F4-12).** Bir makale silindiğinde merkezinden payının
     çıkarılabilmesi gerekir.

**Bunu sağlayan tasarım:** merkez, üye vektörlerin **normalize edilmemiş
aritmetik ortalamasıdır**. Her adımda L2 normalizasyonu uygulansaydı,
`centroid = mean(members)` özdeşliği bozulur ve merkez üyelerinden yeniden
üretilemezdi. Normalizasyona gerek de yoktur: karşılaştırma kosinüs
benzerliğiyle yapılır ve kosinüs ölçekten bağımsızdır.
"""

from __future__ import annotations

import math

# Ortalamanın yeniden hesaplanmış hâlinden bu kadar uzaklaşırsa artımlı
# güncelleme kayan nokta birikimi yüzünden güvenilmez sayılır.
DRIFT_TOLERANCE = 1e-6


def _check_dims(a: list[float], b: list[float]) -> None:
    if len(a) != len(b):
        raise ValueError(f"Boyut uyuşmazlığı: {len(a)} != {len(b)}")


def add_member(centroid: list[float] | None, count: int, vector: list[float]) -> list[float]:
    """Merkeze bir üye ekler ve yeni ortalamayı döndürür.

    `count` ekleme ÖNCESİNDEKİ üye sayısıdır. `centroid` None ise ilk üyedir.
    """
    if count < 0:
        raise ValueError("count negatif olamaz")
    if centroid is None or count == 0:
        return list(vector)
    _check_dims(centroid, vector)
    n = float(count)
    return [(c * n + v) / (n + 1.0) for c, v in zip(centroid, vector, strict=True)]


def remove_member(centroid: list[float], count: int, vector: list[float]) -> list[float] | None:
    """Merkezden bir üyeyi çıkarır (F2-05 geri alma, F4-12 silme).

    `count` çıkarma ÖNCESİNDEKİ üye sayısıdır. Son üye çıkarılıyorsa merkez
    tanımsızdır ve None döner — sıfır vektör döndürmek, merkezi "her şeye
    eşit uzaklıkta" yapar ve sessizce yanlış kümeleme üretir.
    """
    if count <= 0:
        raise ValueError("Üyesi olmayan merkezden üye çıkarılamaz")
    _check_dims(centroid, vector)
    if count == 1:
        return None
    n = float(count)
    return [(c * n - v) / (n - 1.0) for c, v in zip(centroid, vector, strict=True)]


def recompute(vectors: list[list[float]]) -> list[float] | None:
    """Merkezi üyelerden sıfırdan hesaplar — doğruluk ölçütü budur.

    Artımlı güncelleme bunun bir hızlandırmasıdır, alternatifi değil.
    """
    if not vectors:
        return None
    dim = len(vectors[0])
    total = [0.0] * dim
    for v in vectors:
        if len(v) != dim:
            raise ValueError("Üye vektörlerinin boyutları eşit değil")
        for i, x in enumerate(v):
            total[i] += x
    n = float(len(vectors))
    return [x / n for x in total]


def cosine(a: list[float], b: list[float]) -> float:
    _check_dims(a, b)
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def drift(incremental: list[float], recomputed: list[float]) -> float:
    """Artımlı merkez ile yeniden hesaplanan merkez arasındaki azami sapma.

    Kosinüs değil **mutlak bileşen farkı** ölçülür: kosinüs ölçeğe duyarsız
    olduğu için, ortalamanın büyüklüğünü kaybeden bir hatayı gizleyebilir.
    Oysa `remove_member` tam ortalamaya dayanır; büyüklük bozulursa geri
    alma da bozulur.
    """
    _check_dims(incremental, recomputed)
    return max((abs(x - y) for x, y in zip(incremental, recomputed, strict=True)), default=0.0)


def is_recomputable(
    incremental: list[float],
    members: list[list[float]],
    tolerance: float = DRIFT_TOLERANCE,
) -> bool:
    """F2-02 DoD'un testi: merkez hâlâ üyelerinden üretilebiliyor mu?"""
    recomputed = recompute(members)
    if recomputed is None:
        return False
    return drift(incremental, recomputed) <= tolerance
