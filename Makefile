.PHONY: help setup up down migrate test lint fmt arch verify-arch cost ci clean sync ingest embed entities cluster claims reclaim evidence context calendar eval health feeds briefing metrics genbench

help:
	@echo "PolitikDesk — geliştirme komutları"
	@echo ""
	@echo "  make setup        Bağımlılıkları kur (dev dahil)"
	@echo "  make up           Postgres + Redis + API ayağa kaldır"
	@echo "  make migrate      Migration'ları uygula"
	@echo "  make down         Servisleri durdur"
	@echo "  make test         Test paketini koş"
	@echo "  make lint         ruff + mypy"
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
	docker compose up -d api

migrate:
	docker compose run --rm migrate

down:
	docker compose down

test:
	pytest -v

lint:
	ruff check .
	mypy || true

fmt:
	ruff format .
	ruff check --fix .

arch:
	python -m scripts.check_architecture

verify-arch:
	python -m scripts.verify_arch_guard

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

feeds:
	python -m scripts.discover_feeds

cost:
	python -m scripts.cost_model

ci: lint arch verify-arch test

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
