# AetherFlow 设计系统 - 色彩与排版规范

## 色彩系统

### 主色调
```
品牌主色: #4a6cf7 (蓝色)
- 用途: 主要操作按钮、链接、强调元素
- 渐变: linear-gradient(135deg, #76a9ff, #b59bff)
```

### 功能色彩
```
成功/在线: #2aa77c (绿色)
警告: #f59e0b (橙黄色)  
错误/失败: #ef4444 (红色)
信息: #3b82f6 (蓝色)
```

### 中性色彩体系
```
深色背景层级:
- #111b31 (侧边栏顶部)
- #0c1529 (侧边栏底部)

浅色背景层级:
- #f5f7fb (主内容区背景)
- #ffffff (卡片背景)
- #f3f5f9 (输入框背景)

文本色彩:
- #1e293b (主要文本)
- #435069 (次要文本)
- #64748b (辅助文本)
- #76839e (占位符文本)
- #94a0b4 (禁用状态文本)

边框色彩:
- #e2e8f0 (主要边框)
- #e8ebf1 (卡片边框)
- #edf0f5 (输入框边框)
```

### 语义色彩
```css
/* 在线状态点 */
.online-dot: background-color: #2aa77c;

/* 选中状态 */
.selected: background-color: #82aaff;
.selected-text: color: #061b42;

/* 悬停状态 */
.hover: background: rgba(255,255,255,.06);
.hover-text: color: #f3f6ff;
```

## 排版系统

### 字体家族
```
主字体: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
等宽字体: "SF Mono", "Monaco", "Cascadia Code", monospace
```

### 字号层级
```
特大标题: 18px (品牌名称)
大标题: 24px (页面标题)
中标题: 16px (卡片标题)
正文: 14px (内容文本)
小文本: 13px (辅助信息)
微文本: 12px (标签和提示)
极小文本: 10px (分类标签)
```

### 字重规范
```
超粗体: 800 (品牌名称)
粗体: 750 (选中菜单)
半粗体: 700 (强调文本)
中等: 600 (用户名)
常规: 400 (正文)
轻量: 300 (描述)
```

### 行高与字间距
```
大行高: 1.6 (正文内容)
中行高: 1.4 (标题)
紧缩行高: 1.2 (标签文本)

标准字间距: -0.4px (品牌名称)
宽字间距: 1.7px (小型大写标签)
```

## 间距系统

### 基础间距单位
```
4px: 微小间距 (图标内边距)
8px: 标准间距 (相关元素之间) 
12px: 中等间距 (组件内部)
16px: 大间距 (组件之间)
24px: 超大间距 (区块之间)
38px: 特大间距 (页面边距)
```

### 组件内边距
```css
/* 按钮内边距 */
.button-small: padding: 6px 12px;
.button-medium: padding: 8px 16px;
.button-large: padding: 12px 24px;

/* 输入框内边距 */
.input: padding: 8px 12px;

/* 卡片内边距 */
.card: padding: 20px 24px;
```

## 圆角系统

```
微小圆角: 2px (分隔条)
小圆角: 8px (按钮)
标准圆角: 9px (菜单项)
大圆角: 11px (品牌Logo、卡片)
完全圆角: 50% (头像、圆形元素)
```

## 阴影与效果

### 卡片阴影
```css
/* 品牌Logo阴影 */
.brand-shadow: 
  box-shadow: 0 10px 25px rgba(104,148,255,.27);

/* 选中菜单阴影 */
.selected-shadow:
  box-shadow: 0 7px 18px rgba(80,134,255,.18);
```

### 边框效果
```css
/* 侧边栏右边框 */
.sider-border-right: 
  border-right: 1px solid rgba(255,255,255,.07);

/* 顶部Header底边框 */
.header-border-bottom:
  border-bottom: 1px solid #e8ebf1;

/* 用户信息顶边框 */
.profile-border-top:
  border-top: 1px solid rgba(255,255,255,.08);
```

## 尺寸规范

### 固定尺寸组件
```
侧边栏: 252px 宽度
顶部Header: 72px 高度
品牌Logo区域: 93px 高度
导航菜单项: 42px 高度
用户头像: 28-31px 直径
全局搜索框: 230-270px 宽度
```

### 响应式断点
```
大屏: > 1280px (标准布局)
中屏: 1024px - 1280px (压缩布局)
小屏: < 1024px (移动适配)
```

## 动画与过渡

### 过渡时长
```
快速: 150ms (悬停状态)
标准: 300ms (页面切换)
慢速: 500ms (复杂动画)
```

### 缓动函数
```
标准: cubic-bezier(0.4, 0, 0.2, 1)
进入: cubic-bezier(0, 0, 0.2, 1)  
离开: cubic-bezier(0.4, 0, 1, 1)
```

## 状态系统

### 组件状态矩阵
```
状态类型    背景色          文字色        边框色        阴影
默认       #ffffff        #1e293b      #e2e8f0      无
悬停       #f8fafc        #1e293b      #cbd5e1      轻微
激活       #eff6ff        #1d4ed8      #3b82f6      中等
禁用       #f1f5f9        #94a3b8      #e2e8f0      无
加载       #eff6ff        #1d4ed8      #3b82f6      脉冲
错误       #fef2f2        #dc2626      #fca5a5      红色
成功       #f0fdf4        #16a34a      #86efac      绿色
```

---

**文档版本**: 1.0  
**相关文件**: frontend/src/layouts/AgentWorkspaceLayout.module.css  
**更新日期**: 2025-01-14