import re
import csv
import time
import json
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

GITHUB_URL = "https://raw.githubusercontent.com/yousefebrahimi0/1000-AI-collection-tools/main/README.md"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ToolScraper/1.0; +https://example.com)"
}


def get_readme_markdown():
    resp = requests.get(GITHUB_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def extract_tool_links(markdown_text):
    """
    Extract links from markdown. This is heuristic-based and may need refinement
    if the upstream repo structure changes.
    """
    url_pattern = re.compile(r'\((https?://[^\s)]+)\)')
    urls = set(url_pattern.findall(markdown_text))

    filtered = []
    for url in urls:
        # Skip links to the repo itself
        if "github.com/yousefebrahimi0/1000-AI-collection-tools" in url:
            continue
        filtered.append(url)

    return sorted(filtered)


def fetch_html(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
        return None


def guess_product_name_and_company(html, url):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    og_site_name = ""
    og_title = ""

    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        og_site_name = og_site["content"].strip()

    og_title_tag = soup.find("meta", property="og:title")
    if og_title_tag and og_title_tag.get("content"):
        og_title = og_title_tag["content"].strip()

    product_name = og_title or title
    company_name = og_site_name or title

    # Simple cleanup: keep first/last chunk around separators
    for sep in ["|", "–", "-", "•", "—"]:
        if sep in product_name:
            parts = [p.strip() for p in product_name.split(sep) if p.strip()]
            if parts:
                product_name = parts[0]
                break

    for sep in ["|", "–", "-", "•", "—"]:
        if sep in company_name:
            parts = [p.strip() for p in company_name.split(sep) if p.strip()]
            if parts:
                company_name = parts[-1]
                break

    # Fallback to domain if still empty
    if not company_name:
        domain = urlparse(url).netloc
        company_name = domain.replace("www.", "")

    if not product_name:
        product_name = company_name

    return product_name, company_name


def extract_emails(html):
    emails = set()

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.split("mailto:", 1)[1].split("?", 1)[0]
            emails.add(email)

    plain_email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for email in plain_email_pattern.findall(html):
        emails.add(email)

    return sorted(emails)


def extract_social_links(html):
    soup = BeautifulSoup(html, "html.parser")
    linkedin_url = ""
    twitter_url = ""

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com" in href and not linkedin_url:
            linkedin_url = href
        if ("twitter.com" in href or "x.com" in href) and not twitter_url:
            twitter_url = href

    return linkedin_url, twitter_url


def find_careers_page(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    careers_keywords = ["careers", "jobs", "join-us", "joinus", "work-with-us", "work with us"]

    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip().lower()
        href = a["href"]

        if any(kw in href.lower() for kw in careers_keywords) or any(kw in text for kw in careers_keywords):
            return urljoin(base_url, href)

    return ""


def scrape_all_tools(limit=None, delay=1.0):
    md = get_readme_markdown()
    tool_urls = extract_tool_links(md)
    print(f"Found {len(tool_urls)} candidate tool URLs")

    if limit:
        tool_urls = tool_urls[:limit]

    records = []

    for i, url in enumerate(tool_urls, start=1):
        print(f"[{i}/{len(tool_urls)}] Processing {url}")
        html = fetch_html(url)
        if not html:
            records.append({
                "product_name": "",
                "company": "",
                "email": "",
                "linkedin_url": "",
                "twitter_url": "",
                "careers_page": "",
                "tool_url": url,
            })
            continue

        product_name, company_name = guess_product_name_and_company(html, url)
        emails = extract_emails(html)
        linkedin_url, twitter_url = extract_social_links(html)
        careers_page = find_careers_page(html, url)

        record = {
            "product_name": product_name,
            "company": company_name,
            "email": "; ".join(emails),
            "linkedin_url": linkedin_url,
            "twitter_url": twitter_url,
            "careers_page": careers_page,
            "tool_url": url,
        }

        records.append(record)
        time.sleep(delay)  # be polite

    return records


def save_to_csv(records, filename="tools_data.csv"):
    if not records:
        return

    fieldnames = [
        "product_name",
        "company",
        "email",
        "linkedin_url",
        "twitter_url",
        "careers_page",
        "tool_url",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def save_to_json(records, filename="tools_data.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # For testing, you can pass limit=20
    records = scrape_all_tools(limit=None, delay=1.0)
    save_to_csv(records, "tools_data.csv")
    save_to_json(records, "tools_data.json")
    print("Done. Saved tools_data.csv and tools_data.json")