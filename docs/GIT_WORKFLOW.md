# AI Monitor：本地工程与 GitHub 的对应关系

## 名称与仓库边界

工作区名为 `AI-Monitor`；应用显示名为 **AI Monitor**，本地实验版为 **AI Monitor Local**。目录名、GitHub仓库名和应用名不需要逐字相同。

计划中的公开 GitHub 仓库名是 `AI-Monitor`。它对应的是工作区里的 `public/`，不是最外层工作区。GitHub仓库根目录会直接看到 `Package.swift`、`Sources/`、`README.md`，不会额外套一层 public。

```text
AI-Monitor/                    工作区，不是Git仓库
  public/.git                  独立仓库；未来连接公开的 <owner>/AI-Monitor
  local/.git                   独立私人仓库；不连接上述公开仓库
  output/                      安装候选包，不作为源码推送
  backups/                     私有备份，不推送
```

此文件说明映射规则，不声明已经创建或连接远程仓库。以 `git remote -v` 的实际输出为准。本轮改造未创建或推送任何 GitHub 仓库。

## 日常如何对齐

`public/` 的 main 分支用于正式功能和共享代码。`git commit` 只保存本地历史；设置 origin 并执行 push 后，才会把选定提交发送到GitHub。保存文件、编译应用和运行本地实验版都不会自动上传。

`local/` 的 main 分支仅保存私人入口和实验模块。它不是公开仓库的镜像或分支。Local通过 `../public` 使用当前检出的共享库；修改共享库后，下一次构建Local会使用修改，但已安装应用不会热更新。

实验成熟后，只把审查过的功能整理到 public 的正式模块并补测试；不要合并整份私人仓库、凭据或私人历史。需要为Local提供异地备份时，应另选已确认私有的仓库。

公开仓库有更新时，应先检查工作树、fetch、查看差异，再在明确的分支上使用 `git pull --ff-only`。分叉或冲突应人工处理，不覆盖未提交内容。更新公共库后，也应重新构建测试Local。

## 如何知道安装包来自哪版代码

每个 `output/<edition>/BUILD.json` 同时记录源码逐文件哈希与Git来源：

- `publicGit.commit`：公共代码提交；`dirty` 表示构建时是否有未提交变更。
- `localGit.commit`：Local专用代码提交；公开包中此字段为null。
- `publicSourceHashes` / `localSourceHashes`：实际参与构建的文件内容。

正式发行应使用干净提交并打固定版本tag；不要把不同代码打出来的包仅靠同一个文件名当作同一版本。源码ZIP没有.git时仍可构建，但会明确记录Git提交未知，而不是猜测提交号。

安装包应作为GitHub Release附件发布，不放进源码提交。GitHub自动生成的Source code ZIP不是已编译的.app安装包。推送源代码也不会更新本机安装或自动更新别人电脑上的应用。

## 当前发布保护

首次远程连接前先选择源码许可证，并完成相关来源审查。当前已有本地pre-push保护；在发布准备未完成前，常规公开推送会被阻止。Local保护要求先明确核验私有remote。不要绕过这些保护来发布尚未审查的内容。

本地操作检查示例（在工作区运行）：

```bash
git -C public status --short
git -C public remote -v
git -C public log -1 --oneline
git -C local status --short
python3 scripts/git_alignment.py
```

这些检查不执行网络同步。未设置远程时，不存在已经对齐的 `origin/main`；设置远程也不等于已推送完成。

参考：Git官方 `git-remote`、`git-fetch` 与 `git-pull` 文档。源码仓库通过remote与提交历史关联，文件夹改名不会重建或清空其.git历史。
