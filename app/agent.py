import os
import re
import random
import feedparser
from slugify import slugify
from openai import OpenAI
from app.config import RSS_SOURCES, KEYWORDS, BLOG_DIR, OPENROUTER_API_KEY, OPENROUTER_MODEL

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

AUTHOR_NAME = "Robotic Sir"

PROMPT_TEMPLATE = """You are writing a short, clear, tutorial-style blog post for a robotics blog, explaining a piece of news in simple, educational terms — the way a knowledgeable person explains a concept to someone curious but new to the topic.

News to base this on:
Title: {title}
Summary: {summary}

Follow this EXACT structure:

# [Your own catchy title, not the source title]

## Introduction
2-3 simple sentences introducing the topic and why it matters right now, tied to this news.

## How Does It Work?
Explain the core idea/technology in plain, simple language. If relevant, include a short text-based flow diagram in a code block, like this format:

```text
Step One → Step Two → Step Three → Result
```

Follow with 1-2 sentences giving a concrete real-world example.

## Why Is It Important?
A short intro sentence, then a bullet list of 4-5 concrete points (short phrases, not full paragraphs) explaining why this matters.

## The Future
1 short paragraph (2-3 sentences) about where this technology/trend is heading next.

## Conclusion
1-2 sentences wrapping up the core idea simply and clearly.

RULES:
- Keep total length around 300-450 words — short, clear, easy to read, NOT a long-form essay
- Simple vocabulary — write for a curious beginner, not an industry expert
- Plain, friendly tone — like a helpful tutorial, not a hype-filled press release
- No AI buzzwords: skip "game-changer," "revolutionize," "delve into," "landscape," "moreover," "furthermore," "in conclusion," "it's worth noting"
- Do NOT copy sentences directly from the summary — explain everything in your own words
- Do NOT mention you are an AI

Output format: Markdown, following the exact section structure above.
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


def calculate_reading_time(text: str) -> int:
    word_count = len(text.split())
    minutes = max(1, round(word_count / 200))
    return minutes


def extract_tags(text: str, title: str) -> list[str]:
    base_tags = ["Robotics", "AI", "Technology"]
    text_lower = (title + " " + text).lower()

    tag_map = {
        "Drones": ["drone", "uav", "aerial"],
        "Humanoids": ["humanoid", "bipedal"],
        "ComputerVision": ["vision", "camera", "detect", "image"],
        "Automation": ["automation", "manufacturing", "factory", "warehouse"],
        "MachineLearning": ["machine learning", "neural", "model training"],
    }

    for tag, keywords in tag_map.items():
        if any(kw in text_lower for kw in keywords):
            base_tags.append(tag)

    return list(dict.fromkeys(base_tags))[:5]


def add_metadata(blog_text: str, title: str) -> str:
    reading_time = calculate_reading_time(blog_text)
    tags = extract_tags(blog_text, title)
    tags_line = " ".join(f"`#{t}`" for t in tags)

    lines = blog_text.split('\n', 1)
    heading = lines[0] if lines else f"# {title}"
    rest = lines[1] if len(lines) > 1 else ""

    metadata_block = (
        f"{heading}\n\n"
        f"**Author:** {AUTHOR_NAME}  \n"
        f"**Reading time:** {reading_time} minute{'s' if reading_time != 1 else ''}\n"
        f"{rest}\n\n"
        f"**Tags:** {tags_line}"
    )
    return metadata_block


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

    blog_md = add_metadata(blog_md, article["title"])
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