# `infra/runtime/` —— 内置 Python 运行时

> **本目录只提交这个 README，运行时本体不入库。**

## 里面放什么

发布包自带的绿色版 Python（约 892MB），让终用户无需自己装 Python：

```
infra/runtime/python/python.exe
infra/runtime/python/Lib/site-packages/…   # 预装的依赖
```

启动脚本 `infra/scripts/setup_and_start.ps1` 会优先用这个解释器；找不到时才回落到系统 Python。

## 为什么不入库

- 892MB，超出 GitHub 单文件 100MB 上限，且会让仓库体积不可逆。
- 二进制可执行文件不宜进代码仓库（无法 review、无法 diff、可能触发安全扫描误报）。

## 怎么获取

从内网网盘或 Release 附件取 `runtime.zip`，解压到本目录，最终路径必须是 `infra/runtime/python/python.exe`。

开发机可以不放，直接用系统 Python + `pip install -r backend/requirements.txt` 即可。
