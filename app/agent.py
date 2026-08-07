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

PROMPT_TEMPLATE = """You are writing a short, clear, tutorial-style blog post covering 3 separate robotics news stories, explaining each in simple, educational terms — the way a knowledgeable person explains something to someone curious but new to the topic.

Here are the 3 stories to cover:

Story 1:
Title: {title1}
Summary: {summary1}

Story 2:
Title: {title2}
Summary: {summary2}

Story 3:
Title: {title3}
Summary: {summary3}

Follow this EXACT structure:

# [One overall catchy title covering all 3 stories, your own words]

Write a brief 1-2 sentence intro line for the whole post.

## [Your own short heading for Story 1]
50-100 words explaining this story in plain, simple language, in your own words.

## [Your own short heading for Story 2]
50-100 words explaining this story in plain, simple language, in your own words.

## [Your own short heading for Story 3]
50-100 words explaining this story in plain, simple language, in your own words.

## Why It Matters
A short intro sentence, then a bullet list of 3-4 concrete points connecting these stories to the bigger picture in robotics.

## Conclusion
1-2 sentences wrapping up simply and clearly.

RULES:
- Simple vocabulary — write for a curious beginner, not an industry expert
- Plain, friendly tone — like a helpful tutorial, not a hype-filled press release
- Each story section must stay strictly within 50-100 words
- No AI buzzwords: skip "game-changer," "revolutionize," "delve into," "landscape," "moreover," "furthermore," "in conclusion," "it's worth noting"
- Do NOT copy sentences directly from the summaries — explain everything in your own words
- Do NOT mention you are an AI

Output format: Markdown, following the exact section structure above.
"""


def is_relevant(entry) -> bool:
    text = (entry.get("title", "") + entry.get("summary", "")).lower()
    return any(k.lower() in text for k in KEYWORDS)


def fetch_three_articles() -> list[dict]:
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

    if len(candidates) < 3:
        return candidates

    return random.sample(candidates, 3)


def generate_blog(articles: list[dict]) -> str:
    prompt = PROMPT_TEMPLATE.format(
        title1=articles[0]["title"], summary1=articles[0]["summary"],
        title2=articles[1]["title"], summary2=articles[1]["summary"],
        title3=articles[2]["title"], summary3=articles[2]["summary"],
    )
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


def extract_tags(text: str) -> list[str]:
    base_tags = ["Robotics", "AI", "Technology"]
    text_lower = text.lower()

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


def add_tags(blog_text: str) -> str:
    tags = extract_tags(blog_text)
    tags_line = " ".join(f"`#{t}`" for t in tags)
    return f"{blog_text}\n\n**Tags:** {tags_line}"


def save_blog(title: str, content: str) -> str:
    os.makedirs(BLOG_DIR, exist_ok=True)
    slug = slugify(title)[:60]
    path = os.path.join(BLOG_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run() -> dict:
    print("[FETCHING] Looking for robotics news...")
    articles = fetch_three_articles()

    if len(articles) < 3:
        return {"success": False, "error": "Not enough relevant articles found right now. Try again later."}

    print(f"[GENERATING] Covering 3 stories: {', '.join(a['title'] for a in articles)}")
    blog_md = generate_blog(articles)

    if not blog_md:
        return {"success": False, "error": "Blog generation failed. Try again."}

    blog_md = add_tags(blog_md)

    sources_block = "\n\n---\n**Sources:**\n" + "\n".join(
        f"- [{a['title']}]({a['link']})" for a in articles
    )
    blog_md += sources_block

    first_line = blog_md.split('\n', 1)[0]
    title_for_slug = first_line.replace('#', '').strip() or articles[0]["title"]

    path = save_blog(title_for_slug, blog_md)
    print(f"[SAVED] {path}")

    return {
        "success": True,
        "title": title_for_slug,
        "content": blog_md,
        "source_link": articles[0]["link"],
        "file_path": path,
    }


if __name__ == "__main__":
    run()