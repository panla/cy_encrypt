py_warn = PYTHONDEVMODE=1


up:
	@poetry update

deps:
	@poetry install

build: deps
	@poetry build
