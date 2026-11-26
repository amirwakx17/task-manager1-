const fs = require("node:fs");
const path = require("node:path");

const backendUrl = (process.env.BACKEND_URL || "").trim().replace(/\/+$/, "");
if (!/^https:\/\/[^/]+$/i.test(backendUrl)) {
  throw new Error("Set BACKEND_URL to the deployed HTTPS Render service URL.");
}

const root = path.resolve(__dirname, "..");
const dist = path.join(root, "dist");
fs.mkdirSync(dist, { recursive: true });
fs.cpSync(path.join(root, "frontend"), dist, { recursive: true });
fs.writeFileSync(
  path.join(dist, "config.js"),
  `window.TASK_MANAGER_API = ${JSON.stringify(backendUrl)};\n`,
);
