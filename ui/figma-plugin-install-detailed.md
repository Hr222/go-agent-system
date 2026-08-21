# Figma插件导入详细指南

## 🎯 找到插件导入的正确位置

### 在Figma Desktop中寻找插件入口：

**方法A: 通过右键菜单**
1. 在Figma画布任意位置**右键点击**
2. 选择 **"Plugins"** 或 **"插件"**
3. 选择 **"Development"** 或 **"开发"**
4. 点击 **"Import plugin from manifest..."** 或 **"从清单文件导入插件..."**

**方法B: 通过快捷键**
1. 按 `Ctrl+Shift+P` (Windows) 或 `Cmd+Shift+P` (Mac)
2. 在弹出的插件运行窗口中
3. 点击右上角的 **"..."** 菜单
4. 选择 **"Import plugin from manifest..."**

**方法C: 通过顶部菜单**
1. 点击顶部菜单 **"Plugins"** 或 **"插件"**
2. 选择 **"Development"** 或 **"开发"**
3. 点击 **"Import plugin from manifest..."**

## 📂 选择正确的文件

导航到项目文件夹，选择：
```
D:\workspace\go-agent-system\figma-mcp-bridge\plugin\manifest.json
```

## 🔍 如果还是找不到，试试这些：

### 网页版Figma用户：
1. 访问 [Figma Community](https://www.figma.com/community)
2. 搜索 "Figma MCP Bridge"
3. 或者使用桌面版获得更好的插件支持

### 检查Figma版本：
- 确保使用的是 **Figma Desktop** (不是网页版)
- 最新版本的Figma支持完整的插件开发功能

## ⚡ 快速验证是否成功

导入成功后：
1. 按 `Ctrl+Shift+P` 打开插件列表
2. 应该能看到 **"Figma MCP Bridge"** 插件
3. 运行后显示 "WebSocket Connected"

## 🆘 还是有问题？

1. **确认Figma版本**: Help > About Figma (查看版本号)
2. **重启Figma**: 关闭后重新打开
3. **使用绝对路径**: 直接粘贴完整路径到文件选择器

---

**💡 小贴士**: 如果使用的是Figma网页版，建议下载Figma Desktop应用来获得完整的插件开发支持！
