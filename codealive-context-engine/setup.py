#!/usr/bin/env python3
"""
CodeAlive Context Engine — Setup

Stores the API key, verifies connectivity, and confirms the skill is ready.
Works with any AI coding agent that supports the SKILL.md format.

Usage:
    python setup.py
    python setup.py --key YOUR_API_KEY          # non-interactive
    python setup.py --key YOUR_API_KEY --env    # store as env var hint instead of credential store
"""

import os
import sys
import platform
import getpass
import subprocess
import json
import urllib.request
import urllib.error
import urllib.parse

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_NAME = "codealive-api-key"
DEFAULT_BASE_URL = "https://app.codealive.ai"


def _is_wsl() -> bool:
    """Detect if running inside Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def normalize_base_url(base_url: str | None) -> str:
    """Normalize a CodeAlive base URL to the deployment origin.

    Accepts both deployment origins and URLs that already end with `/api`.
    """
    raw = (base_url or DEFAULT_BASE_URL).strip()
    if not raw:
        raw = DEFAULT_BASE_URL

    if "://" not in raw:
        normalized = raw.rstrip("/")
        if normalized.endswith("/api"):
            normalized = normalized[:-4]
        return normalized

    parts = urllib.parse.urlsplit(raw)
    path = parts.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4]

    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment)).rstrip("/")


# ── Credential store helpers ──────────────────────────────────────────────────

def read_existing_key() -> str | None:
    """Check if a key is already configured (env var or credential store)."""
    key = os.getenv("CODEALIVE_API_KEY")
    if key:
        return key

    system = platform.system()
    try:
        if system == "Darwin":
            r = subprocess.run(
                ["security", "find-generic-password", "-a", os.getenv("USER", ""), "-s", SERVICE_NAME, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        elif system == "Linux":
            r = subprocess.run(
                ["secret-tool", "lookup", "service", SERVICE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
            # WSL fallback: try Windows Credential Manager
            if _is_wsl():
                wsl_key = _read_wsl_credential()
                if wsl_key:
                    return wsl_key
        elif system == "Windows":
            return _read_windows_credential()
    except Exception:
        pass
    return None


def _read_windows_credential() -> str | None:
    import ctypes, ctypes.wintypes
    CRED_TYPE_GENERIC = 1

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
            ("TargetName", ctypes.wintypes.LPWSTR),
            ("Comment", ctypes.wintypes.LPWSTR),
            ("LastWritten", ctypes.wintypes.FILETIME),
            ("CredentialBlobSize", ctypes.wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
            ("Persist", ctypes.wintypes.DWORD),
            ("AttributeCount", ctypes.wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.wintypes.LPWSTR),
            ("UserName", ctypes.wintypes.LPWSTR),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.CredReadW.restype = ctypes.wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL)),
    ]
    advapi32.CredFree.restype = None
    advapi32.CredFree.argtypes = [ctypes.c_void_p]

    cred_ptr = ctypes.POINTER(CREDENTIAL)()
    if not advapi32.CredReadW(SERVICE_NAME, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
        return None
    try:
        cred = cred_ptr.contents
        if cred.CredentialBlobSize > 0 and cred.CredentialBlob:
            return bytes(cred.CredentialBlob[:cred.CredentialBlobSize]).decode("utf-16-le")
        return None
    finally:
        advapi32.CredFree(cred_ptr)


def _read_wsl_credential() -> str | None:
    """Read credential from Windows Credential Manager via powershell.exe (WSL only)."""
    ps_script = f"""
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class CredReader {{
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern bool CredRead(string target, int type, int flags, out IntPtr cred);
    [DllImport("advapi32.dll")]
    static extern void CredFree(IntPtr cred);
    [StructLayout(LayoutKind.Sequential)]
    struct CREDENTIAL {{
        public int Flags; public int Type;
        [MarshalAs(UnmanagedType.LPWStr)] public string TargetName;
        [MarshalAs(UnmanagedType.LPWStr)] public string Comment;
        public long LastWritten; public int CredentialBlobSize;
        public IntPtr CredentialBlob; public int Persist;
        public int AttributeCount; public IntPtr Attributes;
        [MarshalAs(UnmanagedType.LPWStr)] public string TargetAlias;
        [MarshalAs(UnmanagedType.LPWStr)] public string UserName;
    }}
    public static string Read(string target) {{
        IntPtr ptr;
        if (!CredRead(target, 1, 0, out ptr)) return null;
        try {{
            var c = Marshal.PtrToStructure<CREDENTIAL>(ptr);
            if (c.CredentialBlobSize > 0)
                return Marshal.PtrToStringUni(c.CredentialBlob, c.CredentialBlobSize / 2);
            return null;
        }} finally {{ CredFree(ptr); }}
    }}
}}
'@
[CredReader]::Read('{SERVICE_NAME}')
"""
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (FileNotFoundError, Exception):
        pass
    return None


def store_key(api_key: str) -> bool:
    """Store key in the OS credential store. Returns True on success."""
    system = platform.system()
    try:
        if system == "Darwin":
            # Delete existing entry first (ignore errors if it doesn't exist)
            subprocess.run(
                ["security", "delete-generic-password", "-a", os.getenv("USER", ""), "-s", SERVICE_NAME],
                capture_output=True, timeout=5,
            )
            r = subprocess.run(
                ["security", "add-generic-password", "-a", os.getenv("USER", ""), "-s", SERVICE_NAME, "-w", api_key],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        elif system == "Linux":
            if _is_wsl():
                # Store in Windows Credential Manager via cmdkey
                r = subprocess.run(
                    ["cmd.exe", "/c", "cmdkey", f"/generic:{SERVICE_NAME}", "/user:codealive", f"/pass:{api_key}"],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode == 0:
                    return True
            r = subprocess.run(
                ["secret-tool", "store", "--label=CodeAlive API Key", "service", SERVICE_NAME],
                input=api_key, capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        elif system == "Windows":
            r = subprocess.run(
                ["cmdkey", f"/generic:{SERVICE_NAME}", "/user:codealive", f"/pass:{api_key}"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return False


# ── Verification ──────────────────────────────────────────────────────────────

def verify_key(api_key: str, base_url: str = DEFAULT_BASE_URL) -> tuple[bool, str]:
    """Test the API key by fetching data sources. Returns (success, message)."""
    normalized_base_url = normalize_base_url(base_url)
    url = f"{normalized_base_url}/api/datasources/ready"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            count = len(data) if isinstance(data, list) else 0
            return True, f"Connected. {count} data source{'s' if count != 1 else ''} available."
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Authentication failed — API key is invalid or expired."
        return False, f"API returned HTTP {e.code}."
    except urllib.error.URLError as e:
        return False, f"Cannot connect to {base_url}: {e.reason}"
    except Exception as e:
        return False, str(e)


# ── Interactive setup ─────────────────────────────────────────────────────────

def print_step(n: int, text: str):
    print(f"\n  [{n}/3] {text}")


def main():
    # Parse CLI args for non-interactive use
    api_key_arg = None
    env_mode = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--key" and i < len(sys.argv) - 1:
            api_key_arg = sys.argv[i + 1]
        elif arg == "--env":
            env_mode = True
        elif arg == "--help":
            print(__doc__)
            sys.exit(0)

    system = platform.system()
    base_url = normalize_base_url(os.getenv("CODEALIVE_BASE_URL", DEFAULT_BASE_URL))

    print()
    print("  CodeAlive Context Engine — Setup")
    print("  " + "=" * 38)

    # ── Step 1: Check existing key ────────────────────────────────────────
    print_step(1, "Checking for existing API key...")

    existing = read_existing_key()
    if existing:
        ok, msg = verify_key(existing, base_url)
        if ok:
            print(f"      Found a working API key. {msg}")
            print_ready()
            return
        else:
            print(f"      Found an existing key, but it didn't work: {msg}")
            print(f"      Let's set up a new one.")

    # ── Step 2: Get API key ───────────────────────────────────────────────
    print_step(2, "API key required.")
    print(f"      Get yours at: {base_url}/settings/api-keys")
    print()

    if api_key_arg:
        api_key = api_key_arg
    else:
        try:
            api_key = getpass.getpass("      Paste your API key (input is hidden): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Setup cancelled.")
            sys.exit(1)

    if not api_key:
        print("      No key provided. Setup cancelled.")
        sys.exit(1)

    # Verify before storing
    ok, msg = verify_key(api_key, base_url)
    if not ok:
        print(f"\n      Key verification failed: {msg}")
        print(f"      Please check your key and try again.")
        sys.exit(1)

    print(f"      Key verified. {msg}")

    # ── Step 3: Store the key ─────────────────────────────────────────────
    print_step(3, "Storing API key...")

    if env_mode:
        if system == "Windows":
            print(f"      Run in PowerShell (persists for current user):")
            print(f'      [Environment]::SetEnvironmentVariable("CODEALIVE_API_KEY", "{api_key}", "User")')
            print()
            print(f"      Or in cmd.exe:")
            print(f'      setx CODEALIVE_API_KEY "{api_key}"')
        else:
            shell = os.getenv("SHELL", "")
            profile = "~/.zshrc" if "zsh" in shell else "~/.bashrc"
            print(f"      Add this to your {profile}:")
            print(f'      export CODEALIVE_API_KEY="{api_key}"')
            print()
            print(f"      Then reload: source {profile}")
    else:
        stored = store_key(api_key)
        if stored:
            if system == "Linux" and _is_wsl():
                store_name = "Windows Credential Manager (via WSL)"
            else:
                store_name = {"Darwin": "macOS Keychain", "Linux": "secret-tool", "Windows": "Credential Manager"}.get(system, "credential store")
            print(f"      Saved to {store_name}.")
        else:
            # Fallback: suggest env var
            print(f"      Could not save to OS credential store.")
            if system == "Windows":
                print(f"      Run in PowerShell instead:")
                print(f'      [Environment]::SetEnvironmentVariable("CODEALIVE_API_KEY", "{api_key}", "User")')
            else:
                shell = os.getenv("SHELL", "")
                profile = "~/.zshrc" if "zsh" in shell else "~/.bashrc"
                print(f"      Add this to your {profile} instead:")
                print(f'      export CODEALIVE_API_KEY="{api_key}"')

    print_ready()


def print_ready():
    print()
    print("  " + "-" * 38)
    print("  Ready! Start your agent and ask:")
    print()
    print('    "How is authentication implemented?"')
    print('    "Show me error handling patterns"')
    print('    "Explain the payment processing flow"')
    print()


if __name__ == "__main__":
    main()
