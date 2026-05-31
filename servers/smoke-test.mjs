// Smoke test: spawn the bundled MCP server, run an initialize + tools/list
// handshake over stdio, and confirm it responds without a missing-module crash.
import { spawn } from "node:child_process";

const child = spawn(process.execPath, ["dist/minimal-mcp-server.js"], {
  stdio: ["pipe", "pipe", "pipe"],
});

let out = "";
let err = "";
child.stdout.on("data", (d) => { out += d.toString(); });
child.stderr.on("data", (d) => { err += d.toString(); });

function send(obj) {
  child.stdin.write(JSON.stringify(obj) + "\n");
}

send({ jsonrpc: "2.0", id: 1, method: "initialize", params: {
  protocolVersion: "2024-11-05",
  capabilities: {},
  clientInfo: { name: "smoke", version: "0.0.0" },
}});

setTimeout(() => {
  send({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });
}, 400);

// Exercise the tool-input-validation path (where ajv runtime requires would fire).
// connect will fail to reach a DB, but the SDK validates args first — that's the
// code path we care about. A JSON-RPC response (even an error) = no module crash.
setTimeout(() => {
  send({ jsonrpc: "2.0", id: 3, method: "tools/call", params: {
    name: "connect",
    arguments: { server: "localhost", database: "nope", authType: "sql", username: "x", password: "y" },
  }});
}, 800);

setTimeout(() => {
  child.kill();
  const crashed = /Cannot find module|MODULE_NOT_FOUND/i.test(out + err);
  const gotTools = /"tools"\s*:/.test(out);
  const gotInit = /"serverInfo"|"protocolVersion"/.test(out);
  const gotCall = /"id"\s*:\s*3/.test(out);
  console.log("--- STDERR (first 800 chars) ---");
  console.log(err.slice(0, 800));
  console.log("--- RESULT ---");
  console.log("missing-module crash:", crashed);
  console.log("initialize responded:", gotInit);
  console.log("tools/list responded:", gotTools);
  console.log("tools/call responded (id 3):", gotCall);
  process.exit(crashed || !gotTools || !gotCall ? 1 : 0);
}, 2500);
