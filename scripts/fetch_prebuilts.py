#!/usr/bin/env python3
"""Script to download AOSP NDK prebuilt dependencies with percentage progress tracking and parallel downloads."""
import argparse
import base64
import concurrent.futures
import io
import os
import pathlib
import sys
import tarfile
import threading
import urllib.request
import xml.etree.ElementTree as ET

MANIFEST_URL = "https://android.googlesource.com/platform/manifest/+/refs/heads/master-ndk/default.xml?format=TEXT"

progress_lock = threading.Lock()
completed_count = 0
total_count = 0

def fetch_single_project(args_tuple):
    global completed_count, total_count
    path, name, revision, base_dir = args_tuple
    dest = base_dir / path
    notice_file = dest / "NOTICE"
    copying_file = dest / "COPYING"
    
    if dest.exists() and (notice_file.exists() or copying_file.exists()):
        with progress_lock:
            completed_count += 1
            pct = (completed_count / total_count) * 100
            print(f"[{completed_count}/{total_count} - {pct:.1f}%] [SKIP] {path} already present.")
        return path, True

    url = f"https://android.googlesource.com/{name}/+archive/refs/heads/{revision}.tar.gz"
    if revision.startswith("7977ed") or len(revision) == 40: # SHA commit hash
        url = f"https://android.googlesource.com/{name}/+archive/{revision}.tar.gz"

    print(f"[FETCH START] {name} ({revision}) -> {path}...")
    dest.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content_length = resp.headers.get("Content-Length")
            data = bytearray()
            chunk_size = 1024 * 1024 # 1MB chunks
            
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                data.extend(chunk)
                if content_length:
                    dl_pct = (len(data) / int(content_length)) * 100
                    # Print download progress inside large archives
                    if len(data) % (50 * 1024 * 1024) < chunk_size: # Every 50MB
                        print(f"  Downloading {path}: {len(data)/(1024*1024):.1f}MB ({dl_pct:.1f}%)")

            print(f"  Downloaded {len(data)} bytes for {path}. Extracting...")
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                tar.extractall(dest)
            
            with progress_lock:
                completed_count += 1
                pct = (completed_count / total_count) * 100
                print(f"[{completed_count}/{total_count} - {pct:.1f}%] [SUCCESS] {path}")
            return path, True
    except Exception as e:
        with progress_lock:
            completed_count += 1
            pct = (completed_count / total_count) * 100
            print(f"[{completed_count}/{total_count} - {pct:.1f}%] [FAILED] {path}: {e}")
        return path, False

def main():
    global completed_count, total_count
    parser = argparse.ArgumentParser(description="Fetch AOSP NDK prebuilts.")
    parser.add_argument("--host", choices=["linux", "darwin", "windows", "all"], default="linux",
                        help="Host platform prebuilts to download (default: linux).")
    parser.add_argument("-j", "--jobs", type=int, default=4,
                        help="Number of parallel download threads (default: 4).")
    args = parser.parse_args()

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
            
        if args.host != "all":
            if args.host == "linux" and ("darwin" in path or "windows" in path):
                continue
            elif args.host == "darwin" and ("linux" in path or "windows" in path):
                continue
            elif args.host == "windows" and ("linux" in path or "darwin" in path):
                continue

        target_projects.append((path, name, revision))

    total_count = len(target_projects)
    completed_count = 0

    base_dir = pathlib.Path(__file__).resolve().parents[2]
    print(f"Base output directory: {base_dir}")
    print(f"Found {total_count} projects to fetch (host filter: '{args.host}', threads: {args.jobs}).")

    task_args = [(path, name, revision, base_dir) for path, name, revision in target_projects]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(executor.map(fetch_single_project, task_args))

    successes = sum(1 for _, ok in results if ok)
    print(f"Fetch completed: {successes}/{total_count} (100.0%) projects ready.")

if __name__ == "__main__":
    main()
