# Fix: Bootstrap 重复安装依赖

## 问题

1. 每次调用 skill 都重新检查并尝试安装依赖，导致不必要的开销
2. `pip install` 失败（exit code 0 但包未安装）时 `capture_output=True` 隐藏了错误信息

## 方案

Sentinel 文件 + 移除 capture_output。

## 改动

仅改 `skill.py`：

1. 新增 `BOOTSTRAP_SENTINEL = os.path.join(VENV_DIR, ".deps-installed")`
2. `_bootstrap()` 开头检查 sentinel 文件，存在则直接 return
3. `_bootstrap()` 安装成功后写入 sentinel 文件
4. `_install_deps()` 移除 `capture_output=True`，让 pip 输出直接显示在终端
