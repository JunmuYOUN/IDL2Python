---
name: web-source-collector
description: >
  웹 URL(HTTP/FTP)에서 IDL .pro 파일을 수집하는 프로토콜.
  SolarSoft, NASA FTP, 개인 웹서버 등 Git이 아닌 웹 소스에서
  HTML 디렉토리 인덱스를 파싱하고 .pro 파일을 다운로드한다.
  키워드: URL 다운로드, HTTP, FTP, SolarSoft, SSW, 웹 수집,
  sohoftp, nascom, 웹에서 코드 가져와, URL에서 .pro 다운,
  git 아닌 소스, 웹 디렉토리
---

# Web-Source-Collector — 웹 URL에서 IDL 코드 수집

## 개요

Git 저장소가 아닌 웹 URL(HTTP/FTP 디렉토리 인덱스)에서 IDL .pro 파일을 수집하는 절차.
SolarSoft(SSW) FTP, NASA GSFC, 대학 웹서버 등에서 연구 코드를 다운로드하여 inbox/에 배치한다.

---

## 소스 유형 판별

사용자가 URL을 제시하면, 아래 순서로 소스 유형을 판별한다:

```
URL 제시
  │
  ├─ github.com / gitlab.com 포함? → Git 저장소 → git clone
  │
  ├─ .pro로 끝남? → 단일 파일 URL → 직접 다운로드
  │
  └─ 그 외 → 디렉토리 인덱스 가능성 → HTML 파싱 시도
```

---

## 디렉토리 인덱스 수집 절차

### Step 1: 디렉토리 페이지 가져오기

```python
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin
import os

def fetch_directory_listing(url):
    """HTML 디렉토리 인덱스에서 파일 목록을 추출한다."""
    if not url.endswith('/'):
        url += '/'
    
    response = urllib.request.urlopen(url)
    html = response.read().decode('utf-8', errors='replace')
    
    # HTML에서 <a href="..."> 링크를 추출
    links = []
    parser = LinkExtractor()
    parser.feed(html)
    
    files = []
    for link in parser.links:
        # 상대 경로를 절대 경로로 변환
        full_url = urljoin(url, link)
        # 상위 디렉토리(..), 정렬 링크(?C=...) 등 제외
        if link.startswith('?') or link.startswith('/') or link == '../':
            continue
        files.append({'name': link, 'url': full_url})
    
    return files


class LinkExtractor(HTMLParser):
    """HTML에서 <a> 태그의 href를 추출하는 파서."""
    def __init__(self):
        super().__init__()
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    self.links.append(value)
```

### Step 2: .pro 파일 필터링

```python
def filter_pro_files(file_list):
    """파일 목록에서 .pro 파일만 추출한다."""
    pro_files = [f for f in file_list if f['name'].lower().endswith('.pro')]
    doc_files = [f for f in file_list 
                 if f['name'].lower() in ('readme.txt', 'readme.md', 'readme')]
    return pro_files, doc_files
```

### Step 3: 파일 다운로드

```python
def download_files(file_list, dest_dir, verbose=True):
    """파일 목록을 지정 디렉토리에 다운로드한다."""
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

### Step 4: 매니페스트 기록

다운로드 결과를 `{작업경로}/logs/download_manifest.md`에 기록한다:

```markdown
# 웹 소스 수집 매니페스트

## 소스
- URL: https://sohoftp.nascom.nasa.gov/solarsoft/packages/dem_sites/idl/
- 수집 일시: 2026-04-14

## 다운로드 결과
| # | 파일명 | 크기 | 상태 |
|---|---|---|---|
| 1 | dem_sites.pro | 6.3K | OK |
| 2 | dem_gridsites.pro | 14K | OK |
| 3 | robust_min.pro | 1.3K | OK |

## 문서
| 파일 | 내용 |
|---|---|
| readme.txt | 패키지 사용법 |

## 실패
없음
```

---

## 전체 수집 함수 (통합)

```python
def collect_from_url(url, inbox_dir, log_dir=None, verbose=True):
    """웹 URL에서 .pro 파일을 수집하여 inbox에 저장한다.
    
    Parameters
    ----------
    url : str
        웹 디렉토리 URL 또는 단일 .pro 파일 URL.
    inbox_dir : str
        다운로드 파일을 저장할 inbox 경로.
    log_dir : str or None
        매니페스트를 저장할 로그 경로.
    verbose : bool
        진행 상황 출력.
    
    Returns
    -------
    list of str
        다운로드된 파일 이름 목록.
    """
    import os
    
    os.makedirs(inbox_dir, exist_ok=True)
    
    # 단일 파일 URL 판별
    if url.lower().endswith('.pro'):
        fname = os.path.basename(url)
        dest = os.path.join(inbox_dir, fname)
        urllib.request.urlretrieve(url, dest)
        if verbose:
            print(f"Downloaded single file: {fname}")
        return [fname]
    
    # 디렉토리 인덱스 수집
    if verbose:
        print(f"Scanning directory: {url}")
    
    file_list = fetch_directory_listing(url)
    pro_files, doc_files = filter_pro_files(file_list)
    
    if verbose:
        print(f"Found {len(pro_files)} .pro files, {len(doc_files)} doc files")
    
    # .pro 파일 다운로드
    downloaded, failed = download_files(pro_files + doc_files, inbox_dir, verbose)
    
    # 매니페스트 기록
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        manifest_path = os.path.join(log_dir, 'download_manifest.md')
        with open(manifest_path, 'w') as f:
            f.write(f"# 웹 소스 수집 매니페스트\n\n")
            f.write(f"## 소스\n- URL: {url}\n\n")
            f.write(f"## 다운로드 결과\n")
            f.write(f"| # | 파일명 | 상태 |\n|---|---|---|\n")
            for i, name in enumerate(downloaded):
                f.write(f"| {i+1} | {name} | OK |\n")
            if failed:
                f.write(f"\n## 실패\n")
                for item in failed:
                    f.write(f"- {item['name']}: {item['error']}\n")
        if verbose:
            print(f"Manifest saved: {manifest_path}")
    
    return downloaded
```

---

## 하위 디렉토리 재귀 수집

일부 SSW 패키지는 하위 디렉토리 구조를 가진다. 재귀 수집이 필요한 경우:

```python
def collect_recursive(url, inbox_dir, log_dir=None, max_depth=3, verbose=True):
    """하위 디렉토리를 재귀적으로 탐색하여 .pro 파일을 수집한다."""
    if max_depth <= 0:
        return []
    
    file_list = fetch_directory_listing(url)
    pro_files, doc_files = filter_pro_files(file_list)
    
    # 하위 디렉토리 식별 (이름이 /로 끝나는 링크)
    subdirs = [f for f in file_list 
               if f['name'].endswith('/') and f['name'] != '../']
    
    all_downloaded = []
    
    # 현재 디렉토리 파일 다운로드
    if pro_files or doc_files:
        downloaded, _ = download_files(pro_files + doc_files, inbox_dir, verbose)
        all_downloaded.extend(downloaded)
    
    # 하위 디렉토리 재귀
    for subdir in subdirs:
        sub_inbox = os.path.join(inbox_dir, subdir['name'].rstrip('/'))
        sub_downloaded = collect_recursive(
            subdir['url'], sub_inbox, log_dir, max_depth - 1, verbose)
        all_downloaded.extend(sub_downloaded)
    
    return all_downloaded
```

---

## 주의사항

### 네트워크 의존
- 웹 수집은 네트워크 연결이 필요하다
- 다운로드 실패 시 재시도 1회 후, 여전히 실패하면 기록하고 진행
- 사용자에게 네트워크 상태를 확인 요청할 수 있다

### SolarSoft 특이사항
- `sohoftp.nascom.nasa.gov`는 HTTPS로 접근 가능 (인증 불필요)
- 일부 SSW 패키지는 `.pro` 외에 `.dat`, `.fits` 등 데이터 파일이 함께 있을 수 있다
- README/문서가 있으면 반드시 함께 다운로드 — 분석에 중요한 맥락 제공

### 파일 인코딩
- 대부분 ASCII/UTF-8이지만, 오래된 코드는 Latin-1일 수 있다
- 다운로드 후 인코딩 자동 감지 시도

### 라이선스
- 다운로드 전 라이선스 확인을 사용자에게 안내한다
- SSW 패키지는 대부분 공개이나, 일부는 사용 조건이 있을 수 있다
