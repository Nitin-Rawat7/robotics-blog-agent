import os
import re
import json
import time
from datetime import datetime, timedelta
import feedparser
from slugify import slugify
from openai import OpenAI
from app.config import RSS_SOURCES, KEYWORDS, BLOG_DIR, OPENROUTER_API_KEY, OPENROUTER_MODEL

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

RECENT_LOG = os.path.join(BLOG_DIR, "..", "recent_topics.json")

SELECTOR_PROMPT = """Below is a list of robotics news headlines with summaries.

Pick the SINGLE most important, most newsworthy, most demanding-of-attention story — the one a serious robotics industry follower would care about most today. Ignore anything that is not core robotics/AI-hardware news (skip general AI, food-tech, unrelated software stories even if they mention "robot" in passing).

RECENTLY COVERED TOPICS (DO NOT PICK ANYTHING SIMILAR):
{recent_topics}

CANDIDATE STORIES:
{numbered_list}

Respond with ONLY the number of your pick. No explanation.

{numbered_list}
"""

PROMPT_TEMPLATE = """You are a robotics journalist writing a blog post. You've covered this beat for years, you have opinions, and you write the way a real person types when they're not overthinking it.

News to base this on:
Title: {title}
Summary: {summary}

You MUST follow this exact article structure from top to bottom:

1. Catchy H1 Title (# Title)
2. Hook & Opening (No introductory fluff, jump straight into the story)
3. 3-4 Main Sections with subheadings (## Subheading Name)
4. A dedicated section with heading "## Key Takeaways" containing 3-4 bullet points
5. A dedicated closing section with heading "## What Comes Next" containing a personal, forward-looking thought

STRICT VOICE & WRITING RULES:
- Word Count: 1200-1500 words.
- Vary sentence length aggressively. Follow a 22-word sentence with a 4-word one.
- Use contractions throughout (it's, don't, you'd, that's).
- Drop in 2-3 small imperfections: start a sentence with "And" or "But", use rhetorical questions or mid-thought em-dashes.
- Include one specific, concrete engineering comparison or analogy.
- Include at least one paragraph of genuine personal opinion where you take a side or admit uncertainty.
- Avoid AI buzzwords completely: "In conclusion", "Moreover", "Furthermore", "It's worth noting", "game-changer", "revolutionize", "delve", "navigate", "landscape".
- Avoid rule-of-three lists inside sentences ("faster, cheaper, and more efficient").
- Reference outside context: past industry failures, competitors, or old predictions.
- Do NOT mention you are an AI.

Output format: Markdown.
"""


def strip_html(text: str) -> str:
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def has_excessive_repetition(text: str, threshold: int = 3) -> bool:
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    seen = {}
    for line in lines:
        seen[line] = seen.get(line, 0) + 1
        if seen[line] >= threshold:
            return True
    return False


def call_openrouter(prompt: str, system_message: str = None, retries: int = 3) -> str:
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                temperature=0.75,
                top_p=0.9,
                presence_penalty=0.4,
                frequency_penalty=0.4,
            )
            content = response.choices[0].message.content

            if content and content.strip() and not has_excessive_repetition(content):
                return content

            reason = "empty" if not content or not content.strip() else "repetitive"
            print(f"[WARN] Response rejected ({reason}) on attempt {attempt}/{retries}")
        except Exception as e:
            print(f"[ERROR] OpenRouter call failed (attempt {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(3)

    return ""


def is_relevant(entry) -> bool:
    text = (entry.get("title", "") + entry.get("summary", "")).lower()
    return any(k.lower() in text for k in KEYWORDS)


def load_recent() -> list[str]:
    if not os.path.exists(RECENT_LOG):
        return []
    with open(RECENT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Keep 7 days of history instead of 24 hours
    cutoff = datetime.utcnow() - timedelta(days=7)
    return [d["slug"] for d in data if datetime.fromisoformat(d["time"]) > cutoff]

def save_recent(title: str) -> None:
    data = []
    if os.path.exists(RECENT_LOG):
        with open(RECENT_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
    
    slug = slugify(title)[:60]
    data.append({"title": title, "slug": slug, "time": datetime.utcnow().isoformat()})
    
    cutoff = datetime.utcnow() - timedelta(days=7)
    data = [d for d in data if datetime.fromisoformat(d["time"]) > cutoff]
    
    with open(RECENT_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fetch_candidates() -> list[dict]:
    recent = load_recent()
    candidates = []

    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            raw_summary = entry.get("summary", "")
            summary = strip_html(raw_summary)
            if is_relevant(entry) and title not in recent:
                candidates.append({
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                })

    return candidates


def pick_most_important(candidates: list[dict]) -> dict:
    if len(candidates) == 1:
        return candidates[0]

    numbered_list = "\n\n".join(
        f"{i+1}. {c['title']}\n{c['summary'][:200]}"
        for i, c in enumerate(candidates)
    )
    prompt = SELECTOR_PROMPT.format(numbered_list=numbered_list)

    result = call_openrouter(prompt).strip()

    try:
        idx = int(result.split()[0]) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    except (ValueError, IndexError):
        pass

    return candidates[0]


def generate_blog(title: str, summary: str, link: str) -> str:
    system_instruction = "You are a human tech journalist who strictly follows formatting structures and writes conversational, non-robotic articles."
    prompt = PROMPT_TEMPLATE.format(title=title, summary=summary)

    blog_text = call_openrouter(prompt, system_message=system_instruction)

    if not blog_text:
        blog_text = (
            f"# {title}\n\n"
            f"We couldn't generate the full write-up this time — the AI model was "
            f"unavailable or rate-limited. Here's what the story is about:\n\n"
            f"{summary}"
        )

    blog_text += f"\n\n---\n*Source: [{title}]({link})*"
    return blog_text


def save_blog(title: str, content: str) -> str:
    os.makedirs(BLOG_DIR, exist_ok=True)
    slug = slugify(title)[:60]
    path = os.path.join(BLOG_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run() -> dict:
    print("[FETCHING] Looking for robotics news...")
    candidates = fetch_candidates()

    if not candidates:
        return {"success": False, "error": "No relevant articles found right now. Try again later."}

    print(f"[FOUND] {len(candidates)} candidates. Picking the most important...")
    article = pick_most_important(candidates)

    print(f"[SELECTED] {article['title']}")
    save_recent(article["title"])

    print("[GENERATING] Writing humanized blog post...")
    blog_md = generate_blog(article["title"], article["summary"], article["link"])

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