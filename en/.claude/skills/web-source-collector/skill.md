---
name: web-source-collector
description: >
  Protocol for collecting IDL .pro files from web URLs (HTTP/FTP).
  Parses HTML directory indexes and downloads .pro files from non-Git web
  sources such as SolarSoft, NASA FTP, and personal web servers.
  Keywords: URL download, HTTP, FTP, SolarSoft, SSW, web collection,
  sohoftp, nascom, fetch code from the web, download .pro from a URL,
  non-git source, web directory
---

# Web-Source-Collector — Collecting IDL Code from Web URLs

## Overview

A procedure for collecting IDL .pro files from non-Git web URLs (HTTP/FTP directory indexes).
It downloads research code from sources such as SolarSoft (SSW) FTP, NASA GSFC, and university web servers, and places it in inbox/.

---

## Source Type Detection

When the user provides a URL, determine the source type in the following order:

```
URL provided
  │
  ├─ contains github.com / gitlab.com? → Git repository → git clone
  │
  ├─ ends with .pro? → single-file URL → direct download
  │
  └─ otherwise → possible directory index → attempt HTML parsing
```

---

## Directory Index Collection Procedure

### Step 1: Fetch the Directory Page

```python
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin
import os

def fetch_directory_listing(url):
    """Extract the file list from an HTML directory index."""
    if not url.endswith('/'):
        url += '/'
    
    response = urllib.request.urlopen(url)
    html = response.read().decode('utf-8', errors='replace')
    
    # Extract <a href="..."> links from the HTML
    links = []
    parser = LinkExtractor()
    parser.feed(html)
    
    files = []
    for link in parser.links:
        # Convert relative paths to absolute paths
        full_url = urljoin(url, link)
        # Exclude the parent directory (..), sort links (?C=...), etc.
        if link.startswith('?') or link.startswith('/') or link == '../':
            continue
        files.append({'name': link, 'url': full_url})
    
    return files


class LinkExtractor(HTMLParser):
    """Parser that extracts the href of <a> tags from HTML."""
    def __init__(self):
        super().__init__()
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    self.links.append(value)
```

### Step 2: Filter .pro Files

```python
def filter_pro_files(file_list):
    """Extract only the .pro files from the file list."""
    pro_files = [f for f in file_list if f['name'].lower().endswith('.pro')]
    doc_files = [f for f in file_list 
                 if f['name'].lower() in ('readme.txt', 'readme.md', 'readme')]
    return pro_files, doc_files
```

### Step 3: Download Files

```python
def download_files(file_list, dest_dir, verbose=True):
    """Download the file list into the specified directory."""
    os.makedirs(dest_dir, exist_ok=True)
    downloaded = []
    failed = []
    
    for f in file_list:
        dest_path = os.path.join(dest_dir, f['name'])
        try:
            urllib.request.urlretrieve(f['url'], dest_path)
            downloaded.append(f['name'])
            if verbose:
                print(f"  Downloaded: {f['name']}")
        except Exception as e:
            failed.append({'name': f['name'], 'error': str(e)})
            if verbose:
                print(f"  FAILED: {f['name']} — {e}")
    
    return downloaded, failed
```

### Step 4: Record the Manifest

Record the download results in `{work_path}/logs/download_manifest.md`:

```markdown
# Web Source Collection Manifest

## Source
- URL: https://sohoftp.nascom.nasa.gov/solarsoft/packages/dem_sites/idl/
- Collection date: 2026-04-14

## Download Results
| # | Filename | Size | Status |
|---|---|---|---|
| 1 | dem_sites.pro | 6.3K | OK |
| 2 | dem_gridsites.pro | 14K | OK |
| 3 | robust_min.pro | 1.3K | OK |

## Documentation
| File | Contents |
|---|---|
| readme.txt | Package usage |

## Failures
None
```

---

## Full Collection Function (integrated)

```python
def collect_from_url(url, inbox_dir, log_dir=None, verbose=True):
    """Collect .pro files from a web URL and save them into inbox.
    
    Parameters
    ----------
    url : str
        Web directory URL or single .pro file URL.
    inbox_dir : str
        inbox path where downloaded files are saved.
    log_dir : str or None
        Log path where the manifest is saved.
    verbose : bool
        Print progress.
    
    Returns
    -------
    list of str
        List of downloaded file names.
    """
    import os
    
    os.makedirs(inbox_dir, exist_ok=True)
    
    # Detect a single-file URL
    if url.lower().endswith('.pro'):
        fname = os.path.basename(url)
        dest = os.path.join(inbox_dir, fname)
        urllib.request.urlretrieve(url, dest)
        if verbose:
            print(f"Downloaded single file: {fname}")
        return [fname]
    
    # Collect the directory index
    if verbose:
        print(f"Scanning directory: {url}")
    
    file_list = fetch_directory_listing(url)
    pro_files, doc_files = filter_pro_files(file_list)
    
    if verbose:
        print(f"Found {len(pro_files)} .pro files, {len(doc_files)} doc files")
    
    # Download .pro files
    downloaded, failed = download_files(pro_files + doc_files, inbox_dir, verbose)
    
    # Record the manifest
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        manifest_path = os.path.join(log_dir, 'download_manifest.md')
        with open(manifest_path, 'w') as f:
            f.write(f"# Web Source Collection Manifest\n\n")
            f.write(f"## Source\n- URL: {url}\n\n")
            f.write(f"## Download Results\n")
            f.write(f"| # | Filename | Status |\n|---|---|---|\n")
            for i, name in enumerate(downloaded):
                f.write(f"| {i+1} | {name} | OK |\n")
            if failed:
                f.write(f"\n## Failures\n")
                for item in failed:
                    f.write(f"- {item['name']}: {item['error']}\n")
        if verbose:
            print(f"Manifest saved: {manifest_path}")
    
    return downloaded
```

---

## Recursive Subdirectory Collection

Some SSW packages have a subdirectory structure. When recursive collection is needed:

```python
def collect_recursive(url, inbox_dir, log_dir=None, max_depth=3, verbose=True):
    """Recursively traverse subdirectories to collect .pro files."""
    if max_depth <= 0:
        return []
    
    file_list = fetch_directory_listing(url)
    pro_files, doc_files = filter_pro_files(file_list)
    
    # Identify subdirectories (links whose name ends with /)
    subdirs = [f for f in file_list 
               if f['name'].endswith('/') and f['name'] != '../']
    
    all_downloaded = []
    
    # Download files in the current directory
    if pro_files or doc_files:
        downloaded, _ = download_files(pro_files + doc_files, inbox_dir, verbose)
        all_downloaded.extend(downloaded)
    
    # Recurse into subdirectories
    for subdir in subdirs:
        sub_inbox = os.path.join(inbox_dir, subdir['name'].rstrip('/'))
        sub_downloaded = collect_recursive(
            subdir['url'], sub_inbox, log_dir, max_depth - 1, verbose)
        all_downloaded.extend(sub_downloaded)
    
    return all_downloaded
```

---

## Cautions

### Network Dependency
- Web collection requires a network connection
- On download failure, retry once; if it still fails, log it and continue
- You may ask the user to check the network status

### SolarSoft Specifics
- `sohoftp.nascom.nasa.gov` is accessible over HTTPS (no authentication needed)
- Some SSW packages may include data files such as `.dat` and `.fits` in addition to `.pro`
- If a README/documentation exists, always download it too — it provides important context for analysis

### File Encoding
- Most are ASCII/UTF-8, but older code may be Latin-1
- Attempt automatic encoding detection after download

### License
- Advise the user to verify the license before downloading
- Most SSW packages are public, but some may have usage conditions
