PORT ?= 8321
OUT ?= ./site

.PHONY: run build deploy

run:
	uv run server.py $(PORT)

build:
	uv run server.py build $(OUT)

deploy:
	uv run server.py deploy
