// ============ 共享设计助手（拼接在每个生成脚本前） ============
const PAGE = figma.currentPage;

const hex2rgb = (h) => {
  const n = h.replace("#", "");
  return {
    r: parseInt(n.slice(0, 2), 16) / 255,
    g: parseInt(n.slice(2, 4), 16) / 255,
    b: parseInt(n.slice(4, 6), 16) / 255,
  };
};
const paint = (h, opacity) => [{ type: "SOLID", color: hex2rgb(h), opacity: opacity ?? 1 }];

const C = {
  bg: "#f5f7fb", sidebar: "#111b31", active: "#82aaff",
  primary: "#668ff6", ink: "#25334b", sub: "#8997aa", faint: "#9aa6b8",
  card: "#ffffff", line: "#e3e7ef", lineSoft: "#f0f2f7", inputBg: "#f3f5f9",
  chipBlue: "#edf3ff", chipGreen: "#eaf8f1", chipRed: "#fdeef1", chipAmber: "#fff4df", chipPurple: "#f2ecff",
  green: "#2aa77c", red: "#e5607a", amber: "#d68a2d", purple: "#8c6bce",
  sidebarText: "#9faac1", dark: "#0b1730",
};
const F_REG = { family: "Noto Sans SC", style: "Regular" };
const F_MED = { family: "Noto Sans SC", style: "Medium" };
const F_BOLD = { family: "Noto Sans SC", style: "Bold" };
await figma.loadFontAsync(F_REG);
await figma.loadFontAsync(F_MED);
await figma.loadFontAsync(F_BOLD);

function frame(parent, name, x, y, w, h, o = {}) {
  const f = figma.createFrame();
  f.name = name;
  f.parent = parent;
  f.x = x; f.y = y;
  f.resize(w, h);
  f.fills = o.fill ? paint(o.fill, o.opacity) : [];
  f.clipsContent = o.clips === undefined ? false : o.clips;
  if (o.radius != null) f.cornerRadius = o.radius;
  if (o.stroke) { f.strokes = paint(o.stroke); f.strokeWeight = o.sw ?? 1; }
  if (o.dash) f.strokeDashes = o.dash;
  if (o.shadow) {
    f.effects = [{ type: "DROP_SHADOW", color: { r: 0.04, g: 0.09, b: 0.19, a: 0.16 }, offset: { x: 0, y: 12 }, radius: 32, spread: 0, visible: true }];
  }
  return f;
}
function txt(parent, name, x, y, w, h, chars, o = {}) {
  const t = figma.createText();
  t.name = name;
  t.parent = parent;
  t.x = x; t.y = y;
  t.fontName = o.bold ? F_BOLD : o.med ? F_MED : F_REG;
  t.fontSize = o.size ?? 13;
  t.characters = chars;
  t.fills = paint(o.color ?? C.ink, o.opacity);
  t.textAlignHorizontal = o.align ?? "LEFT";
  t.textAlignVertical = o.valign ?? "CENTER";
  t.lineHeight = o.lh ? { unit: "PIXELS", value: o.lh } : { unit: "AUTO" };
  t.resize(w, h);
  return t;
}
function hline(parent, x, y, w, color) {
  return frame(parent, "Hairline", x, y, w, 1, { fill: color ?? C.line });
}
function vline(parent, x, y, h, color) {
  return frame(parent, "V Line", x, y, 1, h, { fill: color ?? C.line });
}
function dot(parent, x, y, d, color, name) {
  const e = figma.createEllipse();
  e.name = name ?? "Dot";
  e.parent = parent;
  e.x = x; e.y = y;
  e.resize(d, d);
  e.fills = paint(color);
  return e;
}
// 估算文本宽度：CJK≈1.0，其它≈0.58
function textW(s, size) {
  let u = 0;
  for (const ch of s) u += /[\u2e80-\ufeff]/.test(ch) ? 1.0 : 0.58;
  return Math.ceil(u * size);
}
function chip(parent, x, y, label, o = {}) {
  const size = o.size ?? 11;
  const w = o.w ?? textW(label, size) + 20;
  const h = o.h ?? 22;
  const c = frame(parent, "Chip · " + label, x, y, w, h, { fill: o.bg ?? C.chipBlue, radius: o.radius ?? h / 2 });
  txt(c, "Label", 10, (h - size - 2) / 2, w - 20, size + 2, label, { size, color: o.color ?? C.primary, med: true });
  return c;
}

// ---- 极简图标（几何基元） ----
function rectStroke(parent, x, y, w, h, color, o = {}) {
  return frame(parent, o.name ?? "Rect", x, y, w, h, {
    stroke: color, sw: o.sw ?? 1.5, radius: o.radius ?? 2, dash: o.dash,
  });
}
function tri(parent, x, y, size, color, rotation) {
  const p = figma.createPolygon();
  p.name = "Triangle";
  p.parent = parent;
  p.x = x; p.y = y;
  p.resize(size, size);
  p.pointCount = 3;
  p.fills = paint(color);
  if (rotation) p.rotation = rotation;
  return p;
}
function icon(parent, kind, x, y, color, s) {
  const g = frame(parent, "Icon · " + kind, x, y, 14, 14);
  const col = color ?? C.sub;
  const mk = (dx, dy, w, h, o) => frame(g, "P", dx, dy, w, h, { fill: col, radius: o?.radius ?? 0 });
  const st = (dx, dy, w, h, o) => rectStroke(g, dx, dy, w, h, col, o);
  switch (kind) {
    case "plus":
      mk(2, 6, 10, 2); mk(6, 2, 2, 10); break;
    case "search":
      st(1, 1, 9, 9, { radius: 5 }); frame(g, "P", 9.5, 9.5, 2, 4, { fill: col }).rotation = 45; break;
    case "send":
      tri(g, 1, 1, 12, col, 90); break;
    case "check":
      frame(g, "P", 2, 7, 5, 2, { fill: col }).rotation = 45;
      frame(g, "P", 5, 6, 9, 2, { fill: col }).rotation = -45; break;
    case "close":
      frame(g, "P", 2, 6, 10, 2, { fill: col }).rotation = 45;
      frame(g, "P", 2, 6, 10, 2, { fill: col }).rotation = -45; break;
    case "sparkle":
      frame(g, "P", 3.5, 3.5, 7, 7, { fill: col, radius: 1 }).rotation = 45; break;
    case "doc":
      st(2.5, 1, 9, 12, { radius: 2 }); mk(4.5, 5, 5, 1.4); mk(4.5, 8, 5, 1.4); break;
    case "arrow":
      mk(1, 6.2, 9, 1.6); tri(g, 8, 3.5, 7, col, 90); break;
    case "dots":
      dot(g, 1.5, 6, 2, col); dot(g, 6, 6, 2, col); dot(g, 10.5, 6, 2, col); break;
    case "upload":
      st(1, 10, 12, 3, { radius: 1.5 }); mk(6, 2, 2, 7); tri(g, 3.5, 0, 7, col); break;
    case "copy":
      st(4, 1, 9, 10, { radius: 2 }); st(1, 4, 9, 10, { radius: 2 }); break;
    case "redo":
      st(2, 4, 10, 8, { radius: 4 }); tri(g, 8, 1, 7, col, 0); break;
    case "thumb":
      st(1, 5, 4, 8, { radius: 1 }); st(6, 5, 7, 8, { radius: 2 }); mk(7, 2, 2, 4); break;
    case "bot":
      st(1.5, 4, 11, 8, { radius: 3 }); dot(g, 4.5, 7, 2, col); dot(g, 7.5, 7, 2, col); mk(4, 1, 6, 2, { radius: 1 }); break;
    case "clip":
      frame(g, "P", 5, 2, 4, 10, { fill: col }).rotation = -45;
      frame(g, "P", 2, 4, 4, 8, { stroke: col, sw: 1.5, radius: 2 }).rotation = -45; break;
    case "flow":
      st(0, 0, 5, 5, { radius: 1 }); st(9, 9, 5, 5, { radius: 1 }); mk(2.5, 11.5, 9, 1.4); break;
    case "archive":
      st(1, 3, 12, 9, { radius: 2 }); mk(3.5, 6.5, 7, 1.4); break;
    case "message":
      st(0.5, 1, 13, 10, { radius: 3 }); tri(g, 2, 9, 5, col, 180); break;
    case "chevron":
      tri(g, 3, 4, 8, col, 180); break;
    case "workflow":
      st(1, 1, 5, 5, { radius: 1 }); st(8, 8, 5, 5, { radius: 1 }); mk(3.5, 6, 1.4, 4); mk(3.5, 10.5, 6, 1.4); break;
  }
  return g;
}

// ---- 按钮组件 ----
function btnPrimary(parent, x, y, label, o = {}) {
  const size = o.size ?? 12;
  const w = o.w ?? textW(label, size) + (o.icon ? 46 : 36);
  const h = o.h ?? 36;
  const b = frame(parent, "Btn · " + label, x, y, w, h, { fill: o.fill ?? C.primary, radius: o.radius ?? 8 });
  if (o.icon) icon(b, o.icon, 14, (h - 14) / 2, "#ffffff");
  const tx = o.icon ? 34 : 0;
  txt(b, "Label", tx, (h - size - 2) / 2, w - tx, size + 2, label, { size, color: "#ffffff", med: true, align: o.icon ? "LEFT" : "CENTER" });
  return b;
}
function btnGhost(parent, x, y, label, o = {}) {
  const size = o.size ?? 12;
  const w = o.w ?? textW(label, size) + 32;
  const h = o.h ?? 36;
  const b = frame(parent, "Btn · " + label, x, y, w, h, { fill: o.fill ?? "#ffffff", stroke: o.stroke ?? C.line, radius: o.radius ?? 8 });
  txt(b, "Label", 0, (h - size - 2) / 2, w, size + 2, label, { size, color: o.color ?? "#56657d", med: o.med !== false, align: "CENTER" });
  return b;
}

// ---- 从 Workspace 克隆外壳（侧边栏 + 顶栏） ----
const NAV_NAMES = ["控制台", "智能体", "工作流", "知识库", "文档中心"];
async function loadNodeFont(t) {
  const fn = t.fontName === figma.mixed ? F_REG : t.fontName;
  await figma.loadFontAsync(fn);
  return fn;
}
async function shellInto(screen, activeNav, breadcrumbText) {
  // 侧边栏
  const srcSidebar = await figma.getNodeByIdAsync("2:4");
  const sb = srcSidebar.clone();
  sb.name = "Sidebar · Navigation";
  sb.parent = screen; sb.x = 0; sb.y = 0;
  for (const name of NAV_NAMES) {
    const nav = sb.children.find((c) => c.name === name);
    if (!nav) continue;
    const on = name === activeNav;
    nav.fills = on ? paint(C.active) : [];
    const t = nav.children.find((c) => c.type === "TEXT");
    if (t) t.fills = paint(on ? "#071632" : C.sidebarText);
    const v = nav.findOne((c) => c.type === "VECTOR");
    if (v) v.strokes = paint(on ? C.dark : C.sidebarText);
  }
  // 顶栏
  const srcHeader = await figma.getNodeByIdAsync("2:6");
  const hd = srcHeader.clone();
  hd.name = "Top Header";
  hd.parent = screen; hd.x = 0; hd.y = 0;
  if (breadcrumbText) {
    const bc = hd.findOne((c) => c.name === "Breadcrumb");
    const labels = bc.children.filter((c) => c.type === "TEXT");
    const last = labels[labels.length - 1];
    await loadNodeFont(last);
    last.characters = breadcrumbText;
  }
  return { sb, hd };
}
function removeExisting(name) {
  const n = PAGE.children.find((c) => c.name === name);
  if (n) n.remove();
}
