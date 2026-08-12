"""Değerlendirme araçları burada DEĞİL, repo kökündeki `eval/` altındadır.

Yol haritası eval eserlerini kök seviyede konumlandırıyor:
    eval/golden_set_v1.jsonl     (F0-14, F1-20, F2-20)
    eval/embedding_benchmark.py  (F0-13)
    eval/run.py                  (F2-16)

Sebep: Golden Set ve benchmark'lar uygulama kodu değil, ölçüm eseridir;
Docker imajına girmezler (.dockerignore) ve sürüm kontrolünde ayrı yaşarlar.

Bu paket yalnızca Spec §11.2'deki modül haritasıyla uyum için durur.
"""
