#!/usr/bin/env python3
import os, subprocess
r = subprocess.run(["python3", "/Users/yanping.ma/ryan-personal-knowledge/infrastructure/devops-core-gen.py"], capture_output=True, text=True)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr)
