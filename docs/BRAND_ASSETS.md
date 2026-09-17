# Monitor 品牌标志来源

这些标志仅用于识别对应服务。Monitor 是个人本机工具，与这些品牌无隶属或背书关系。所有商标属于各自权利人。标志采用官方站点、官方仓库或本机已安装官方应用中的原始图形；未改形状或为标志套用自定义色彩。SVG/ICNS 用系统 sips 转成 PNG，运行时不访问任何图标服务。

卡片、菜单栏横杠和进度条的颜色为 Monitor 的区分色，不声称是各品牌的完整官方配色规范。

- **claude**：`https://cdn.sanity.io/images/4zrzovbb/claude-com/369b14e80ac643cc09dccd581ccb91f82b559190-32x32.png (linked by https://claude.com/)`
- **kimi**：`https://www.kimi.com/pwa-192.png`
- **codex**：`https://developers.openai.com/favicon.png`
- **glm**：`https://z-cdn.chatglm.cn/z-ai/static/logo.svg (linked by https://chat.z.ai/)`
- **copilot**：`https://raw.githubusercontent.com/primer/octicons/main/icons/copilot-24.svg`
- **antigravity**：`/Applications/Antigravity.app/Contents/Resources/icon.icns (installed official app)`
- **gemini**：`https://www.gstatic.com/lamda/images/gemini_sparkle_4g_512_lt_f94943af3be039176192d.png (linked by https://gemini.google.com/)`

GitHub 的 Copilot 小图形来自 Primer Octicons，用作产品导航图标。OpenAI 标志保持其开发者官网提供的原始图形，绿色只用于外侧卡片和额度条。

资源文件摘要见 `Resources/BrandAssets/sources.json`。

## Monitor 应用图标

`Resources/AppIcon.icns` 是 Monitor 自己的图标（访达、启动台）：白色圆角方块上的四条额度横杠，呼应菜单栏图标，颜色取自 `BrandStyle` 的区分色，不含任何服务商标志。由 `swift scripts/make_app_icon.swift Resources/AppIcon.icns` 生成，`build.sh` 打包时复制进应用并写入 `CFBundleIconFile`。
