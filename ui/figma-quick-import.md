# 🚀 Figma插件快速导入 - 详细步骤

## 最简单的方法 (推荐!)

### 方法1: 文件拖拽法 ⭐
1. 打开 **Figma Desktop** 应用
2. 打开任意设计文件
3. 从文件管理器中拖拽这个文件到Figma窗口：
   ```
   D:\workspace\go-agent-system\figma-mcp-bridge\plugin\manifest.json
   ```
4. 松开鼠标，Figma会自动导入插件 ✅

### 方法2: 右键菜单法
1. 在Figma画布空白处 **右键点击**
2. 在弹出菜单中找到 **"Plugins"** (插件)
3. 点击 **"Plugins"** 后会看到子菜单
4. 选择 **"Development"** (开发)
5. 点击 **"Import plugin from manifest..."**
6. 在文件选择器中导航到：
   ```
   D:\workspace\go-agent-system\figma-mcp-bridge\plugin\manifest.json
   ```

### 方法3: 快捷键法
1. 在Figma中按 **`Ctrl + Shift + P`** (Windows)
2. 点击插件窗口右上角的 **三个点 "..."** 菜单
3. 选择 **"Import plugin from manifest..."**
4. 选择 `manifest.json` 文件

## 🔍 验证导入成功

导入成功后，按 `Ctrl+Shift+P` 应该能看到：
- **Figma MCP Bridge** 插件出现在列表中
- 点击运行后显示 **"WebSocket Connected"** 🎉

## ⚡ 如果还是找不到入口

### 可能的原因：
1. **使用的是网页版Figma** → 需要下载 Desktop 版本
2. **Figma版本过旧** → 更新到最新版本
3. **权限不足** → 确保有开发者插件权限

### 下载Figma Desktop:
访问: https://www.figma.com/downloads/

---

**📝 重要**: 确保使用 **Figma Desktop** 而不是网页版，因为插件开发功能只在桌面应用中完全支持！
