#!/usr/bin/env python3
"""Script to download all AOSP NDK prebuilt dependencies specified in manifest.xml."""
import base64
import io
import os
import pathlib
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

MANIFEST_URL = "https://android.googlesource.com/platform/manifest/+/refs/heads/master-ndk/default.xml?format=TEXT"

def main():
    print("Fetching master-ndk manifest.xml...")
    req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        xml_data = base64.b64decode(resp.read()).decode("utf-8")

    root = ET.fromstring(xml_data)
    
    target_projects = []
    for proj in root.findall("project"):
        path = proj.attrib.get("path")
        name = proj.attrib.get("name")
        revision = proj.attrib.get("revision", "mirror-goog-main-ndk")
        
        if not path or path == "ndk":
            continue
            
        target_projects.append((path, name, revision))

    base_dir = pathlib.Path(__file__).resolve().parents[2]
    print(f"Base output directory: {base_dir}")
    print(f"Found {len(target_projects)} prebuilt/external projects to fetch (Linux, Darwin, Windows).")

    for path, name, revision in target_projects:
        dest = base_dir / path
        notice_file = dest / "NOTICE"
        copying_file = dest / "COPYING"
        if dest.exists() and (notice_file.exists() or copying_file.exists()):
            print(f"[SKIP] {path} already present.")
            continue

        url = f"https://android.googlesource.com/{name}/+archive/refs/heads/{revision}.tar.gz"
        if revision.startswith("7977ed") or len(revision) == 40: # SHA commit hash
            url = f"https://android.googlesource.com/{name}/+archive/{revision}.tar.gz"

        print(f"[FETCH] {name} ({revision}) -> {path}...")
        dest.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
                print(f"  Downloaded {len(data)} bytes. Extracting...")
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                    tar.extractall(dest)
                print(f"  Successfully extracted to {path}")
        except Exception as e:
            print(f"  [WARNING] Failed to fetch {name}: {e}")

if __name__ == "__main__":
    main()
