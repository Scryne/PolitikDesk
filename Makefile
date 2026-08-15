.PHONY: help setup up workers start stop restart down migrate test lint audit fmt arch verify-arch deploy-check verify-deploy-check cost ci clean sync ingest embed entities cluster claims reclaim evidence context calendar eval health pipeline-health watchdog backup backup-list backup-verify backup-restore feeds briefing metrics genbench

export PD_GIT_SHA ?= $(shell git rev-parse HEAD 2>/dev/null)
export PD_GIT_BRANCH ?= $(shell git branch --show-current 2>/dev/null)

help:
	@echo "PolitikDesk — geliştirme komutları"
	@echo ""
	@echo "  make setup        Bağımlılıkları kur (dev dahil)"
	@echo "  make start        TÜM yığını ayağa kaldır (günlük kullanım)"
	@echo "  make stop         Yığını durdur"
	@echo "  make restart      Yeniden kurup başlat (kod değiştiyse)"
	@echo "  make up           Postgres + Redis + API ayağa kaldır"
	@echo "  make workers      Worker + beat'i YENİDEN KURARAK ayağa kaldır"
	@echo "  make migrate      Migration'ları uygula"
	@echo "  make down         Servisleri durdur"
	@echo "  make deploy-check Çalışan konteynerler depodaki kodu mu taşıyor?"
	@echo ""
	@echo "  -- sağlık ve yedek (Faz 4) --"
	@echo "  make watchdog        Dışarıdan sağlık nöbeti (konteyner+API+aşama)"
	@echo "  make pipeline-health Hangi aşamada birikme var?"
	@echo "  make backup          Veritabanı yedeği al"
	@echo "  make backup-list     Yedekleri listele"
	@echo "  make backup-verify F=<dosya>   Yedek okunabilir mi?"
	@echo "  make backup-restore F=<dosya>  Ayrı bir DB'ye geri yükle + doğrula"
	@echo "  make test         Test paketini koş"
	@echo "  make lint         ruff + mypy"
	@echo "  make audit        Bağımlılık güvenlik taraması (B-83)"
	@echo "  make fmt          ruff format"
	@echo "  make arch         Mimari kuralları denetle (F0-16)"
	@echo "  make verify-arch  Mimari korumayı canlı deneyle doğrula"
	@echo "  make sync         config/sources.yml -> veritabanı"
	@echo "  make ingest       Bir toplama turu çalıştır"
	@echo "  make cluster      Bekleyen makaleleri olaylara ata (F2-01)"
	@echo "  make claims       Olaylardan iddia çıkar (F2-06, LLM)"
	@echo "  make reclaim      İddiaları güncel prompt sürümüyle yeniden çıkar (B-70)"
	@echo "  make evidence     Kanıt durumu + salience (F2-12/15)"
	@echo "  make context      Tarihsel bağlam bağları (F2-17)"
	@echo "  make eval         Golden Set ölçümü (F2-16)"
	@echo "  make briefing     Sabah brifingi üret + gönder (F3-16/17)"
	@echo "  make metrics      8 ürün metriğini topla (F3-19)"
	@echo "  make genbench     Üretim modeli kıyaslaması (B-71)"
	@echo "  make embed        Bekleyen makaleleri embed et"
	@echo "  make entities     Varlık çıkarımı"
	@echo "  make health       Kaynak sağlık raporu"
	@echo "  make feeds        Doğrulanmamış kaynakların akışını ara"
	@echo "  make cost         Maliyet modelini yeniden hesapla (F0-06/F0-07)"
	@echo "  make ci           CI'ın yerelde koştuğu her şey"

setup:
	pip install -e ".[dev]"

up:
	docker compose up -d db redis
	docker compose run --rm migrate
	docker compose up -d --build api

# `--build` ZORUNLU. 13 Ağustos 2026'da beat Faz 1 imajıyla, worker Faz 2
# imajıyla koşuyordu: `up -d` mevcut imaj varsa yeniden kurmaz, bu yüzden
# yeni görevler (kümeleme, iddia, brifing, metrik) hiç zamanlanmadı ve
# boru hattı sessizce koptu. `make deploy-check` bu durumu yakalar.
workers:
	docker compose --profile workers up -d --build
	@$(MAKE) --no-print-directory deploy-check

# Günlük kullanım girişi (F4-10). `up` + `workers` sırasını doğru
# uygular: migration önce, worker/beat sonra.
start: up workers
	@echo ""
	@echo "PolitikDesk hazır:"
	@echo "  Feed        http://localhost:8000/feed"
	@echo "  Sağlık      http://localhost:8000/admin/"
	@echo "  Metrikler   http://localhost:8000/admin/metrics"

stop:
	docker compose --profile workers down

# Kod değiştiyse bu. `restart` yerine `stop + start`: Docker'ın
# `restart` komutu imajı YENİDEN KURMAZ ve B-77'nin tam olarak
# tekrarına yol açar.
restart: stop start

migrate:
	docker compose run --rm migrate

down:
	docker compose --profile workers down

test:
	pytest -v

lint:
	ruff check .
	mypy

# B-83: bagimlilik guvenlik taramasi. CI'da zorunlu adim.
audit:
	pip-audit --skip-editable

fmt:
	ruff format .
	ruff check --fix .

arch:
	python -m scripts.check_architecture

verify-arch:
	python -m scripts.verify_arch_guard

# Testler kodu denetler, çalışan konteyneri değil. Bu ikisi arasındaki
# kaymayı yalnızca aşağıdaki denetleyici görür.
deploy-check:
	python -m scripts.check_deployment

sync:
	python -m scripts.ingest sync

ingest:
	python -m scripts.ingest run

embed:
	python -m scripts.ingest embed

entities:
	python -m scripts.ingest entities

cluster:
	python -m scripts.ingest cluster

claims:
	python -m scripts.ingest claims

reclaim:
	python -m scripts.ingest reclaim

evidence:
	python -m scripts.ingest evidence

context:
	python -m scripts.ingest context

calendar:
	python -m scripts.calendar list

eval:
	python -m eval.run

briefing:
	python -m scripts.ingest briefing --slot morning --send

metrics:
	python -m scripts.ingest metrics

genbench:
	python -m scripts.generation_benchmark --events 3

health:
	python -m scripts.ingest health

# Boru hattının İÇİ: bir aşamada birikme var mı? (B-78)
pipeline-health:
	python -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:22} bekleyen={r.backlog:4} en_eski={r.oldest_hours} esik={r.threshold_hours}') for r in p.stage_report()]"

# Dışarıdan nöbet: Docker kapalıysa içerideki alarm ötemez (F4-10)
watchdog:
	python -m scripts.watchdog

# --- Yedekleme (F4-06) ---------------------------------------------------
backup:
	python -m scripts.backup create

backup-list:
	python -m scripts.backup list

backup-verify:
	@test -n "$(F)" || (echo "Kullanim: make backup-verify F=backups/<dosya>.dump"; exit 1)
	python -m scripts.backup verify "$(F)"

# Geri yükleme ÜRETİME DEĞİL, ayrı bir doğrulama veritabanına yapılır.
backup-restore:
	@test -n "$(F)" || (echo "Kullanim: make backup-restore F=backups/<dosya>.dump"; exit 1)
	python -m scripts.backup restore "$(F)" --into politikdesk_restore_test

feeds:
	python -m scripts.discover_feeds

cost:
	python -m scripts.cost_model

# DESIGN.md Bolum 14 denetimi: 7 ekran x 4 viewport'ta yatay tasma,
# konsol hatasi ve h1/lang/aria kontrolu. `ci`ye DAHIL DEGIL cunku ayakta
# bir sunucu ister ve CI isinde Docker yok. Arayuz degistiginde elle
# kosulur; sonrasinda design/decisions.md guncellenir.
ui-check:
	python -m playwright install chromium
	python scripts/ui_check.py --shots

ci: lint audit arch verify-arch test

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
