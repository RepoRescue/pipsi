# pipsi — Usability Validation

**Selected rescue**: sonnet (srconly: FAIL — 所有 srconly 都 FAIL，因为修复版需要捆绑 click>=8.3.1 / virtualenv>=21.2.0 的安装)
**Scenario type**: A — CLI tool (entry_points.console_scripts: `pipsi=pipsi:cli`)
**Real-world use**: pipsi 在每个 PyPI 包独立的 venv 里安装它的 console_scripts，再 symlink 到 `~/.local/bin`。pipx 的前身（2017–2019 主流）。

## Step 0: Import sanity

```
/home/zhihao/hdd/RepoRescue_Clean/repos/rescue_sonnet/pipsi/venv-t2/bin/python -c "import pipsi"
→ OK (pipsi/__init__.py 583 行)
```

## Step 1: Best rescue selection

| Model | T2 | srconly |
|---|---|---|
| **sonnet** | PASS | FAIL |
| gpt-codex | PASS | FAIL |
| minimax | PASS | FAIL |
| glm | PASS | FAIL |
| kimi | FAIL | FAIL |

按优先级 sonnet > gpt-codex > kimi > glm > minimax，选 sonnet。所有 srconly 都 FAIL → 修复实质依赖 setup.py / requirements.txt 的依赖版本钉死（click>=8.3.1, virtualenv>=21.2.0）。

## Step 4: Install + core feature (clean venv)

\`\`\`
python3.13 -m venv /tmp/pipsi-clean
/tmp/pipsi-clean/bin/pip install -e repos/rescue_sonnet/pipsi
→ Successfully installed Click-8.3.3 virtualenv-21.2.4 pipsi-0.10.dev0 ...
/tmp/pipsi-clean/bin/pipsi --version
→ pipsi, version 0.10.dev0, python /tmp/pipsi-clean/bin/python3.13
\`\`\`

招牌功能（在隔离 venv 里装 PyPI 包 + 暴露 console_scripts）：**PASS**

测试场景（usability_validate.py）：
1. \`pipsi install httpie\` → 在 \`\$PIPSI_HOME/httpie\` 建独立 venv
2. \`\$PIPSI_BIN_DIR/http\` 真实可执行 → \`http --help\` 返回 0 + 输出含 \`URL\`
3. \`pipsi list\` 列出 httpie 的 3 个 binary（http / httpie / https）
4. \`pipsi uninstall --yes httpie\` 移除 venv + 所有 symlink，\`pipsi list\` 报空
5. 再次 install / uninstall round-trip 干净

## Hard constraint 5: ≥3 distinct sub-paths exercised

虽然 pipsi 是单文件包，但 \`usability_validate.py\` 直接调用了 3 条独立的 in-process 路径：

| Path | API | 触发面 |
|---|---|---|
| 1 | \`pipsi.normalize_package("Click>=8.0") == "click"\` | 修复后改用 regex（替代 \`pkg_resources.Requirement\`） |
| 2 | \`pipsi.Repo(home, bin).list_everything()\` | os/json/glob 路径 |
| 3 | \`pipsi.get_real_python(sys.executable)\` | 修复后用 \`shutil.which\`（替代 \`distutils.spawn.find_executable\`） |

加上 subprocess 路径上 \`pipsi.cli\` → \`Repo.install\` → \`find_scripts\` → \`publish_script\` 的 4 个独立函数被真实调度。

## Hard constraint 6: Py3.13 surface stressed

修复 diff（\`/usr/bin/diff -u repos/original/pipsi/pipsi/__init__.py repos/rescue_sonnet/pipsi/pipsi/__init__.py\`）在源码层移除/替换：

| Surface | Evidence |
|---|---|
| \`pkg_resources.Requirement\` → regex parse | \`__init__.py:35\` 删除 import；\`:69-74\` 新 \`normalize_package\`；\`:289\` 用新函数 |
| \`distutils.spawn.find_executable\` → \`shutil.which\` | \`__init__.py:12\` 删 import；\`:327\` 改用 \`shutil.which(python_exe)\` |
| \`pkg_resources\` based version → \`importlib.metadata.version\` | \`__init__.py:13\` 新增 \`from importlib.metadata import version as package_version\`；\`:479\` \`click.version_option(version=package_version('pipsi'))\` |
| \`virtualenv\` 21.x（py3.13 兼容版本） | \`setup.py:23\` 新增 \`virtualenv>=21.2.0\` 约束 |

四种破坏面都被显式触碰且代码走到 → **不是 TRIVIAL_RESCUE**。

## Beyond unit tests (constraint 3)

\`testing/test_command_line.py\` 只有一个 \`test_list_command\`（断 \`pipsi list\` 在空 home 上不崩）。\`testing/test_repo.py\` 用 in-process \`Repo.install('grin')\` 覆盖 install，但：

- 没有任何测试做 \`subprocess.run([pipsi, 'install', ...])\` 这条 CLI 路径
- 没有任何测试在 install 之后**真去运行被装出来的 binary**（\`http --help\`），只断了 \`bin.listdir(glob)\` 出现文件
- 没有任何测试做 install → uninstall → list 的 round-trip
- 没有任何测试覆盖 \`--bin-dir\` / \`--home\` flag

我们的 \`usability_validate.py\` 全部覆盖以上四条。

## Step 6: Downstream / Scenario

- **Path A**：跳过。pipsi 在 2019+ 被 pipx 完全取代，PyPI 上没有活跃下游声明依赖 pipsi。
- **Path B**：\`scenario_validate.py\`（94 行真实业务逻辑）。模拟"新员工开发机引导脚本"——pipsi install 一组 CLI 工具（httpie + cookiecutter）→ 探测每个 binary \`--version\` 真能跑 → 写 manifest JSON 给下游审计 → 全部 uninstall → list 收敛回空。运行结果：\`SCENARIO_PASS\`（详见 run.log）。

## Step 7: Bug-hunt

\`bug_hunt.py\` 探测了 4 类边界（详见 bug_hunt.log）：

| Probe | 结果 |
|---|---|
| H1 包名带 dash / mixed case / version specifier / 空串 / 非法字符（normalize_package） | **OK**（修复后的 regex 实现把 7/7 用例都处理对了） |
| H2 重复 install 同一包 | **OK**（rc=1 + "httpie is already installed"） |
| H3 PIPSI_HOME 路径含空格 + 中文（\`pipsi spaces 中\`） | **OK**（install 成功 + binary 可执行） |
| H4 同一进程 2 线程并发 \`pipsi install httpie\` | **BUG**（两个 rc 都是 0，第二个 install 会**覆盖**第一个的 venv）——pipsi 在 venv 目录上没有 file lock。这个洞 PyPI 上的 pipsi 0.9 时代就有，rescue 没新增也没修复 |

H4 是实存的并发缺陷，但**不否决 USABLE**（按 SKILL Step 7 约定：bug-hunt 只是兜底证据，不是 gate）。原版 pipsi 也有同样的 race。

## Verdict

STATUS: USABLE

Reason: clean venv \`pip install -e\` 成功；招牌功能（隔离 venv install + console_script 暴露 + list/uninstall round-trip）全部通过 subprocess 真验证；硬约束 6 在源码层显式命中 4 条 3.13 破坏面（pkg_resources / distutils.spawn / importlib.metadata / virtualenv 兼容版本）；Path B scenario 的开发机引导脚本端到端跑通；bug-hunt 找到 1 个并发 race，但属于上游既有缺陷且不在招牌路径上。
