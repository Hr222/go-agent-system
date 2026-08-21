#!/usr/bin/env node
/**
 * 通过 figma-mcp-bridge 的 /rpc 端点向 Figma 插件发送 execute_code 请求。
 * 若目标文件同目录存在 _prelude.js，会自动拼接在其前面。
 * 用法:
 *   node figma-rpc.mjs <code-file.js>     # 执行 JS 文件内容（函数体，可用 return / await）
 *   node figma-rpc.mjs -e "return 1+1"    # 执行内联代码
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";

const arg = process.argv[2];
if (!arg) {
  console.error("usage: node figma-rpc.mjs <code-file.js> | -e <inline-code>");
  process.exit(1);
}

let code;
if (arg === "-e") {
  code = process.argv[3];
} else {
  const preludePath = join(dirname(arg), "_prelude.js");
  code = (existsSync(preludePath) ? readFileSync(preludePath, "utf8") + "\n" : "")
    + readFileSync(arg, "utf8");
}

const res = await fetch("http://localhost:1994/rpc", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ tool: "execute_code", params: { code } }),
});

const body = await res.json();
if (body.error) {
  console.error("RPC error:", body.error);
  process.exit(1);
}
console.log(JSON.stringify(body.data?.result ?? null, null, 2));
