import { spawn } from "node:child_process"
import http from "node:http"

const url = "http://127.0.0.1:5174"
const isWindows = process.platform === "win32"
const npmCmd = isWindows ? "npm.cmd" : "npm"
const npxCmd = isWindows ? "npx.cmd" : "npx"

let stopping = false

const server = spawn(
  npmCmd,
  ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5174", "--strictPort"],
  {
    detached: !isWindows,
    stdio: ["ignore", "pipe", "pipe"],
  }
)

server.stdout.on("data", chunk => process.stdout.write(chunk))
server.stderr.on("data", chunk => process.stderr.write(chunk))
server.on("exit", code => {
  if (!stopping) {
    console.error(`Vite server exited before UI audit completed with code ${code ?? "unknown"}.`)
    process.exit(code ?? 1)
  }
})

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function canReachServer() {
  return new Promise(resolve => {
    const req = http.get(url, res => {
      res.resume()
      resolve(Boolean(res.statusCode && res.statusCode < 500))
    })
    req.on("error", () => resolve(false))
    req.setTimeout(1000, () => {
      req.destroy()
      resolve(false)
    })
  })
}

async function waitForServer() {
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    if (await canReachServer()) return
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function stopServer() {
  stopping = true
  if (server.killed) return
  if (isWindows) {
    server.kill()
  } else {
    process.kill(-server.pid, "SIGTERM")
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    stopServer()
    process.exit(130)
  })
}

try {
  await waitForServer()
  const audit = spawn(
    npxCmd,
    ["playwright", "test", "e2e/ui-audit.spec.mjs", "--browser=chromium", "--config=playwright.config.js", "--reporter=line"],
    { stdio: "inherit" }
  )
  const code = await new Promise(resolve => audit.on("exit", resolve))
  stopServer()
  process.exit(code ?? 1)
} catch (error) {
  console.error(error)
  stopServer()
  process.exit(1)
}
