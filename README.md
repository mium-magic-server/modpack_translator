# Minecraft 整合包翻译脚本

支持翻译原版的 JSON 字符串和 AE2 的手册

## 使用说明

### 准备工作

要求：

+ Python 3.10
+ OpenAI 兼容的接口和密钥

#### 1. 配置 Python 环境

推荐使用虚拟环境：

```shell
python3.10 -m venv venv
source venv/bin/activate
```

```shell
pip install -r requirements.txt
```

#### 2. 修改配置文件

配置位于 `config.py` 脚本中，已包含注释

#### 3. 准备 CFPA 的翻译作为翻译参考 \[可选\]

将 CFPA 的公共翻译仓库克隆至 `work/Minecraft-Mod-Language-Package`

#### 4. 构建已翻译的文本映射和索引

修改 `json_translate.py`，注释掉最后的 `do_translate()`，如下:

```python
if __name__ == '__main__':
    prepare()

    # do_translate()
```

执行脚本:

```shell
python json_translate.py
```

### 翻译所有 json 字符串

修改 `json_translate.py`，注释掉 `prepare()`，如下:

```python
if __name__ == '__main__':
    # prepare()

    do_translate()
```

执行脚本:

```shell
python json_translate.py
```

生成的 json 文件在 `work/translated.json`

### 翻译 AE2 手册

执行脚本:

```shell
python markdown_translate.py
```

生成的中文 md 文件在 `work/ae2/zh/` 目录下

### 翻译 FTB 任务书

将待翻译的 FTB 任务配置目录放入 `work/ftbquests`.
需要配合 ftb quest lang splitter 模组使用.

执行脚本:

```shell
python ftbquest_translate.py
```

生成的中文 snbt 文件在 `work/ftbquests/quests/lang/zh_cn/` 目录下

## 版权声明

用户使用此工具生成的翻译，可以随意使用，产生的歧义或者版权纠纷与本项目无关。

本项目包含使用 CFPA 翻译项目文件作为翻译参考的功能，若生成的翻译启用了参考功能，必须注明来源。

CFPA 项目地址：[Minecraft-Mod-Language-Package](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package)