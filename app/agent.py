import os
import random
import feedparser
from slugify import slugify
from openai import OpenAI
from app.config import RSS_SOURCES, KEYWORDS, BLOG_DIR, OPENROUTER_API_KEY, OPENROUTER_MODEL

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

PROMPT_TEMPLATE = """You are a robotics enthusiast writing a short blog update.

Title: {title}
Summary: {summary}

Rules:
- Exactly 10 lines, no more no less
- Simple, human, conversational tone
- Add one personal opinion line
- No headings, no bullet points
- Do NOT mention you are an AI
- Do NOT copy sentences directly from the summary — rewrite in your own words

Output format: Markdown, start with a short catchy H1 title, then 10 lines.
"""


def is_relevant(entry) -> bool:
    text = (entry.get("title", "") + entry.get("summary", "")).lower()
    return any(k.lower() in text for k in KEYWORDS)


def fetch_one_article() -> dict | None:
    candidates = []

    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            continue

        for entry in feed.entries:
            if is_relevant(entry):
                candidates.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                })

    if not candidates:
        return None

    return random.choice(candidates)


def generate_blog(title: str, summary: str) -> str:
    prompt = PROMPT_TEMPLATE.format(title=title, summary=summary)
    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        return content if content else ""
    except Exception as e:
        print(f"[ERROR] OpenRouter call failed: {e}")
        return ""


def save_blog(title: str, content: str) -> str:
    os.makedirs(BLOG_DIR, exist_ok=True)
    slug = slugify(title)[:60]
    path = os.path.join(BLOG_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run() -> dict:
    print("[FETCHING] Looking for robotics news...")
    article = fetch_one_article()

    if not article:
        return {"success": False, "error": "No relevant articles found right now. Try again later."}

    print(f"[GENERATING] {article['title']}")
    blog_md = generate_blog(article["title"], article["summary"])

    if not blog_md:
        return {"success": False, "error": "Blog generation failed. Try again."}

    blog_md += f"\n\n---\n*Source: [{article['title']}]({article['link']})*"

    path = save_blog(article["title"], blog_md)
    print(f"[SAVED] {path}")

    return {
        "success": True,
        "title": article["title"],
        "content": blog_md,
        "source_link": article["link"],
        "file_path": path,
    }


if __name__ == "__main__":
    run()