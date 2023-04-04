# README

## Introduction

利用 Cython Python 源代码 转换为动态链接库

## Install

```bash
# in a poetry env, install requirements
poetry install

# build package
poetry build

# install
cd dist
pip install ./cy_encrypt-0.1.0-py3-none-any.whl
```

## usage

config.json example

```json
{
    "source_dir": "/home/user/project/example",
    "need_compile_dirs": [
        "apps",
        "apps/threads",
        "apps/views"
    ]
}
```

example project structure tree

```text
.
├── apps
│   ├── const.py
│   ├── log.py
│   ├── setting.py
│   ├── signal.py
│   ├── threads
│   │   ├── main.py
│   │   └── setting.py
│   ├── views
│   │   ├── main.py
│   │   └── setting.py
│   └── work.py
```

command

```bash
cy_encrypt -c ./config.json execute
```

Then Will Auto Process `/home/user/project/example`

cp `source_dir` to `source_dir_target_{now}`

Generate C language source code file to `source_dir_c_source_{now}`

## File

- [LICENSE](./LICENSE)
- [CHANGELOG](./CHANGELOG.md)
