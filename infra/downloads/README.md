# `infra/downloads/` —— 安装包缓存

> **本目录只提交这个 README，下载的安装包不入库。**

## 里面放什么

首次部署时从网上下载的安装包缓存，避免重复下载：

- `python-3.x.x-embed-amd64.zip`
- `mysql-8.x.x-winx64.zip`
- 其他一次性下载物

`infra/scripts/setup_and_start.ps1` 若发现本目录已有对应压缩包，会跳过下载直接解压。

## 为什么不入库

- 单包 200MB~500MB，超 GitHub 单文件限制。
- 属于可再下载的中间产物，不是源码。

`.gitignore` 已排除本目录内容与 `infra/*.zip`、`infra/*.7z`。
