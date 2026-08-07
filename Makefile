py_warn = PYTHONDEVMODE=1


up:
	@uv lock

deps:
	@uv sync

build: deps
	@uv build