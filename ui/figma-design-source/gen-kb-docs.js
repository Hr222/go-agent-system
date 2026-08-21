// ============ Screen · 知识库 · 文档管理 ============
removeExisting("Screen · Knowledge Base"); // 清理旧草稿
const SCREEN = "Screen · 知识库 · 文档管理";
removeExisting(SCREEN);
const screen = frame(PAGE, SCREEN, 1600, 40, 1440, 980, { fill: C.bg });
await shellInto(screen, "知识库", "知识库");

// ---- 内容区 (252,72) 1188x908，内边距 38 ----
const CT = frame(screen, "Content", 252, 72, 1188, 908);

// 1. 页头
dot(CT, 38, 38, 8, C.green, "Status Dot");
txt(CT, "Eyebrow", 52, 33, 180, 16, "知识库服务正常运行", { size: 11, color: C.green, med: true });
txt(CT, "Title", 38, 54, 200, 36, "知识库", { size: 28, bold: true });
txt(CT, "Desc", 38, 96, 420, 16, "管理企业制度文档，沉淀可检索、可追溯的知识资产。", { size: 13, color: C.sub });
btnPrimary(CT, 1032, 62, "导入文档", { icon: "upload", w: 118 });

// 2. 统计卡片
const stats = [
  { label: "文档总数", value: "128", trend: "本周新增 6 份", icon: "doc", chip: C.chipBlue, color: C.primary },
  { label: "已发布版本", value: "96", trend: "覆盖全部正式制度", icon: "check", chip: C.chipGreen, color: C.green },
  { label: "解析中", value: "5", trend: "OCR 与切块运行中", icon: "workflow", chip: C.chipAmber, color: C.amber },
  { label: "入库失败", value: "2", trend: "2 份文档需要重试", icon: "close", chip: C.chipRed, color: C.red },
];
stats.forEach((s, i) => {
  const x = 38 + i * 282;
  const card = frame(CT, "Stat · " + s.label, x, 142, 266, 112, { fill: C.card, radius: 10 });
  const ic = frame(card, "Icon Chip", 17, 35, 42, 42, { fill: s.chip, radius: 11 });
  icon(ic, s.icon, 13, 13, s.color);
  txt(card, "Label", 73, 30, 120, 14, s.label, { size: 11, color: C.sub });
  txt(card, "Value", 73, 48, 140, 28, s.value, { size: 22, bold: true });
  txt(card, "Trend", 17, 86, 200, 12, s.trend, { size: 10, color: s.color });
});

// 3. 标签页 + 筛选
txt(CT, "Tab · 概览", 38, 288, 40, 18, "概览", { size: 13, color: C.sub });
txt(CT, "Tab · 文档管理", 98, 288, 120, 18, "文档管理 128", { size: 13, color: C.primary, med: true });
frame(CT, "Tab Underline", 98, 314, 88, 2, { fill: C.primary });
txt(CT, "Tab · 知识检索", 236, 288, 70, 18, "知识检索", { size: 13, color: C.sub });
hline(CT, 38, 320, 1112);

const search = frame(CT, "Doc Search", 736, 284, 216, 32, { fill: C.inputBg, radius: 6 });
icon(search, "search", 10, 9, C.faint);
txt(search, "Placeholder", 30, 9, 150, 14, "搜索文档名称…", { size: 11, color: C.faint });
const sel1 = frame(CT, "Select · 分类", 962, 284, 88, 32, { fill: C.card, stroke: C.line, radius: 6 });
txt(sel1, "Value", 12, 9, 56, 14, "全部分类", { size: 11, color: "#56657d" });
icon(sel1, "chevron", 66, 11, C.faint);
const sel2 = frame(CT, "Select · 状态", 1062, 284, 88, 32, { fill: C.card, stroke: C.line, radius: 6 });
txt(sel2, "Value", 12, 9, 56, 14, "全部状态", { size: 11, color: "#56657d" });
icon(sel2, "chevron", 66, 11, C.faint);

// 4. 文档表格
const table = frame(CT, "Document Table", 38, 344, 1112, 470, { fill: C.card, radius: 10, clips: true });
const head = frame(table, "Head", 0, 0, 1112, 40, { fill: "#f7f8fb" });
const cols = [
  ["文档名称", 20, 360], ["分类", 400, 100], ["状态", 510, 100],
  ["当前版本", 620, 120], ["更新时间", 740, 140], ["操作", 1010, 82],
];
cols.forEach(([label, x, w]) => txt(head, "Col · " + label, x, 13, w, 14, label, { size: 11, color: "#8a98ad" }));

const rows = [
  { name: "委托评估机构准入管理办法.pdf", type: "PDF", cat: "制度规范", status: "已发布", sc: C.green, sbg: C.chipGreen, ver: "v3 · 已激活", time: "08-12 14:20", ops: [["查看", C.primary]] },
  { name: "招标投标合规操作指引.docx", type: "DOCX", cat: "制度规范", status: "已发布", sc: C.green, sbg: C.chipGreen, ver: "v2 · 已激活", time: "08-11 09:02", ops: [["查看", C.primary]] },
  { name: "工程建设招标文件范本.pdf", type: "PDF", cat: "模板范本", status: "解析中", sc: C.primary, sbg: C.chipBlue, ver: "v1 · 切块中", time: "08-14 10:41", ops: [["查看", C.primary]] },
  { name: "评标专家管理细则.docx", type: "DOCX", cat: "制度规范", status: "已发布", sc: C.green, sbg: C.chipGreen, ver: "v5 · 已激活", time: "08-09 16:55", ops: [["查看", C.primary]] },
  { name: "供应商黑名单管理制度.pdf", type: "PDF", cat: "制度规范", status: "已发布", sc: C.green, sbg: C.chipGreen, ver: "v1 · 已激活", time: "08-06 11:30", ops: [["查看", C.primary]] },
  { name: "历史标书案例集 2019-2023.pdf", type: "PDF", cat: "案例库", status: "入库失败", sc: C.red, sbg: C.chipRed, ver: "解析失败", time: "08-14 08:12", ops: [["重试", C.red]] },
];
rows.forEach((r, i) => {
  const y = 40 + i * 71;
  const row = frame(table, "Row · " + r.name, 0, y, 1112, 71);
  hline(row, 20, 0, 1072, C.lineSoft);
  const typeBg = r.type === "PDF" ? C.chipRed : C.chipBlue;
  const typeC = r.type === "PDF" ? C.red : C.primary;
  const tc = frame(row, "Type", 20, 22, 28, 26, { fill: typeBg, radius: 6 });
  txt(tc, "T", 0, 7, 28, 12, r.type, { size: 8, color: typeC, bold: true, align: "CENTER" });
  txt(row, "Name", 58, 26, 330, 18, r.name, { size: 13, med: true });
  txt(row, "Cat", 400, 28, 100, 16, r.cat, { size: 12, color: C.sub });
  chip(row, 510, 25, r.status, { bg: r.sbg, color: r.sc, h: 22 });
  txt(row, "Ver", 620, 28, 120, 16, r.ver, { size: 12, color: r.ver.includes("失败") ? C.red : C.ink });
  txt(row, "Time", 740, 28, 140, 16, r.time, { size: 12, color: C.sub });
  let ox = 1010;
  r.ops.forEach(([label, color]) => {
    const t = txt(row, "Op · " + label, ox, 28, textW(label, 12) + 4, 16, label, { size: 12, color, med: true });
    ox += textW(label, 12) + 20;
  });
});

// 5. 分页
txt(CT, "Page Info", 38, 842, 260, 16, "共 128 条记录 · 当前第 1-10 条", { size: 12, color: C.sub });
const pg = frame(CT, "Pagination", 940, 838, 210, 30);
const pages = [["‹", false], ["1", true], ["2", false], ["3", false], ["…", false], ["13", false], ["›", false]];
pages.forEach(([p, act], i) => {
  const x = i * 30;
  const b = frame(pg, "P · " + p, x, 0, 30, 30, {
    fill: act ? C.chipBlue : C.card,
    stroke: act ? undefined : C.line,
    radius: 6,
  });
  txt(b, "T", 0, 8, 30, 14, p, { size: 12, color: act ? C.primary : "#56657d", med: act, align: "CENTER" });
});

return { screen: SCREEN, created: PAGE.children.find((c) => c.name === SCREEN)?.id };
