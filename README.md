# README

## Introduction

Use Cython to convert Python source code (.py, .pyw, .pyx) into dynamic link libraries

to achieve the purpose of protecting the source code

## File

- [LICENSE](./LICENSE)
- [CHANGELOG](./CHANGELOG.md)

## Install

```bash

# create venv
uv venv --python 3.12

# in a uv env, install requirements
uv sync

# build package dist
uv build

# install
cd dist
pip install ./cy_encrypt-0.3.0-py3-none-any.whl
```

## Usage

config.json example

```json
{
    "source_dir": "/home/user/project/example",
    "skip_dirs": [
        "apps",
        "apps/threads",
        "apps/views"
    ],
    "skip_cp_dirs": [
        ".git",
        ".idea"
    ]
}
```

example project structure tree

```text
.
├── apps
│         ├── const.py
│         ├── log.py
│         ├── setting.py
│         ├── signal.py
│         ├── threads
│         │         ├── main.py
│         │         └── setting.py
│         ├── views
│         │         ├── main.py
│         │         └── setting.py
│         └── work.py
```

command

```bash
cy_encrypt -c ./config.json execute
```

Then Will Auto Process `/home/user/project/example`

cp `source_dir` to `{source_dir}_{now}`

Compile `.py` files to dynamically linked libraries (`.so`/`.pyd`), keeping the relative path unchanged

## Test

not install cy_encrypt

```bash

python -m cy_encrypt.cli --help
```
