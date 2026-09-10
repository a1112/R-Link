# 滚动条样式使用指南

R-Link 项目统一的滚动条样式系统。

## 全局默认样式

所有滚动条默认使用以下样式：
- 宽度: 8px (垂直), 8px (水平)
- 轨道: 透明
- 滑块: 半透明白色
- 圆角: 4px
- 悬停效果: 滑块透明度增加

## 可用工具类

### `.scrollbar-hide`
隐藏滚动条但保持滚动功能。
```tsx
<div className="scrollbar-hide overflow-y-auto">...</div>
```

### `.scrollbar-thin`
极细滚动条 (4px)，适用于紧凑空间。
```tsx
<div className="scrollbar-thin overflow-y-auto">...</div>
```

### `.scrollbar-standard`
标准滚动条 (8px)，默认样式。
```tsx
<div className="scrollbar-standard overflow-y-auto">...</div>
```

### `.scrollbar-card`
卡片内滚动条 (6px)，带轨道背景。
```tsx
<div className="scrollbar-card overflow-y-auto">...</div>
```

### `.scrollbar-hover`
悬停时显示滚动条，平时隐藏。
```tsx
<div className="scrollbar-hover overflow-y-auto">...</div>
```

### `.scrollbar-auto-hide`
自动隐藏滚动条，悬停时展开。
```tsx
<div className="scrollbar-auto-hide overflow-y-auto">...</div>
```

### `.scrollbar-rounded`
更圆润的滚动条滑块。
```tsx
<div className="scrollbar-rounded overflow-y-auto">...</div>
```

## 滚动行为

### `.smooth-scroll`
平滑滚动效果。
```tsx
<div className="smooth-scroll overflow-y-auto">...</div>
```

## 滚动捕捉

用于创建轮播、滑动等效果。

```tsx
{/* 水平捕捉 */}
<div className="scroll-snap-x flex overflow-x-auto">
  <div className="scroll-snap-start">...</div>
  <div className="scroll-snap-center">...</div>
  <div className="scroll-snap-end">...</div>
</div>

{/* 垂直捕捉 */}
<div className="scroll-snap-y overflow-y-auto">
  <div className="scroll-snap-start">...</div>
  <div className="scroll-snap-center">...</div>
</div>
```

## 使用示例

### 弹窗内容区
```tsx
<div className="flex-1 overflow-y-auto p-6 scrollbar-card">
  {content}
</div>
```

### 侧边栏菜单
```tsx
<div className="h-full overflow-y-auto scrollbar-thin">
  {menuItems}
</div>
```

### 列表容器
```tsx
<div className="overflow-y-auto scrollbar-standard max-h-96">
  {listItems}
</div>
```

### 隐藏滚动条
```tsx
<div className="overflow-x-auto scrollbar-hide">
  {horizontalContent}
</div>
```

## 浏览器兼容性

| 特性 | Chrome | Firefox | Safari | Edge |
|------|--------|---------|--------|------|
| Webkit 样式 | ✅ | ❌ | ✅ | ✅ |
| Firefox 样式 | ❌ | ✅ | ❌ | ❌ |
| CSS Scroll Snap | ✅ | ✅ | ✅ | ✅ |
| smooth-scroll | ✅ | ✅ | ✅ | ✅ |
