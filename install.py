#!/usr/bin/env python3
import os, sys, shutil, subprocess, platform

def run(cmd):
    print(f">>> {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.returncode != 0 and res.stderr:
        print(f"Warning/Error: {res.stderr.strip()}")
    return res.returncode

def main():
    print("==================================================")
    print("     HERMES AGENT: FULL SKILLS & TOOLS INSTALL    ")
    print("==================================================
")

    # 1. Enable Toolsets
    print("[*] Step 1: Enabling Hermes Toolsets...")
    toolsets = [
        'browser', 'clarify', 'code_execution', 'computer_use', 'connections',
        'cronjob', 'delegation', 'file', 'image_gen', 'memory',
        'session_search', 'skills', 'terminal', 'todo', 'tts', 'vision', 'web'
    ]
    for plat in ['cli', 'telegram', 'discord', 'whatsapp']:
        run(['hermes', 'tools', 'enable', '--platform', plat] + toolsets)

    # 2. MCP Server
    print("
[*] Step 2: Registering MCP Servers...")
    run(['hermes', 'mcp', 'add', 'blender', '--command', 'uvx mcp-for-blender'])

    # 3. Hub & URL Skills
    print("
[*] Step 3: Installing Hub & Community Skills...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    snap_path = os.path.join(base_dir, 'hermes_skills_snapshot.json')
    if os.path.exists(snap_path):
        ret = run(['hermes', 'skills', 'snapshot', 'import', snap_path, '--force'])
    
    # Fallback to direct installs if snapshot failed
    hub_skills = [
        'official/research/rss-feeds',
        'official/social-media/reddit-reading',
        '@xeric7/douban-self-taste-skill',
        '@akdira/akdira-taste-skill-v1',
        '@casperzinou/talonforge-god-mode',
        'skills-sh/NousResearch/hermes-agent/skills/creative/songwriting-and-ai-music',
        'https://raw.githubusercontent.com/cloudflare/security-audit-skill/main/skills/security-audit/SKILL.md',
        'https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/taste-skill/SKILL.md',
        'https://raw.githubusercontent.com/bitwize-music-studio/claude-ai-music-skills/main/skills/sheet-music-publisher/SKILL.md',
        'https://raw.githubusercontent.com/hex/claude-council/main/skills/council-execution/SKILL.md',
        'https://raw.githubusercontent.com/hex/claude-council/main/skills/deep-execution/SKILL.md',
        'https://raw.githubusercontent.com/hex/claude-council/main/skills/local-council-execution/SKILL.md',
        'https://raw.githubusercontent.com/hex/claude-council/main/skills/provider-integration/SKILL.md'
    ]
    for s in hub_skills:
        run(['hermes', 'skills', 'install', s])

    # 4. Custom Local Skills
    print("
[*] Step 4: Installing Custom Engineering Skills...")
    hermes_home = os.environ.get('HERMES_HOME')
    if not hermes_home:
        if platform.system() == 'Windows':
            hermes_home = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'hermes')
        else:
            hermes_home = os.path.expanduser('~/.hermes')
    
    target_skills_dir = os.path.join(hermes_home, 'skills')
    os.makedirs(target_skills_dir, exist_ok=True)
    print(f"Target skills directory: {target_skills_dir}")

    copied_count = 0
    for item in os.listdir(base_dir):
        src = os.path.join(base_dir, item)
        if os.path.isdir(src) and not item.startswith('.'):
            dst = os.path.join(target_skills_dir, item)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
            copied_count += 1
            print(f"  + Installed custom skill package: {item}")

    print(f"
[✓] SUCCESS: {copied_count} custom skill packages installed, tools & hub skills active!")
    print("Run 'hermes skills list' and 'hermes tools list' to verify.")

if __name__ == '__main__':
    main()
