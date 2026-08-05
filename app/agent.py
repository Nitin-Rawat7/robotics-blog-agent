import os
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

Respond with ONLY the number of your pick. No explanation.

{numbered_list}
"""

PROMPT_TEMPLATE = """You are a robotics journalist writing a blog post. You've covered this beat for years, you have opinions, and you write the way a real person types when they're not overthinking it.

News to base this on:
Title: {title}
Summary: {summary}

Write a full blog post following these rules:

STRUCTURE
- 500-1000 words
- Catchy H1 title, your own words, not the source title
- Open with a hook: a question, a blunt claim, a scene, or a mildly sarcastic observation — never "In today's news..." or "Recently, ..."
- 3-4 sections with subheadings (##)
- One "Key Takeaways" list near the end (3-4 bullets)
- Short "What Comes Next" closing thought

VOICE — this is the important part
- Vary sentence length aggressively. Follow a 22-word sentence with a 4-word one. Real people don't write in uniform rhythm.
- Use contractions throughout (it's, don't, you'd, that's) — never "it is," "do not," etc.
- Drop in at least 2-3 small imperfections real writers have: a sentence starting with "And" or "But," a rhetorical question, a mid-thought aside in em dashes, one deliberate sentence fragment for emphasis.
- Include one specific, concrete comparison or analogy that isn't generic (not "like a double-edged sword" — something sharper and more particular to robotics/engineering).
- Write at least one paragraph of genuine opinion where you take a side, hedge like a real person ("I could be wrong here, but..."), or admit uncertainty.
- Avoid AI tics completely: no "In conclusion," "Moreover," "Furthermore," "It's worth noting," "In today's fast-paced world," "game-changer," "revolutionize," "delve into," "navigate," "landscape," "underscore."
- Avoid rule-of-three lists inside sentences ("faster, cheaper, and more efficient") — real writers usually pick one or two things, not three balanced items.
- Reference something concrete and slightly tangential (a past failed product, an old prediction that didn't pan out, a personal pet peeve about the industry) to ground it in lived perspective, not just the summary.

CONTENT
- Explain the news in your own words — do not paraphrase the summary sentence-by-sentence
- Add outside context: history, competitors, past failures/successes in similar attempts
- Do not mention you are an AI

Output format: Markdown.
"""


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
                temperature=0.8,
                top_p=0.9,
                presence_penalty=0.2,
                frequency_penalty=0.2,
                max_tokens=2500,
            )
            choice = response.choices[0]
            content = choice.message.content

            # Reject if too short to be a real blog (just a title/heading)
            if content and len(content.strip()) > 400:
                return content

            print(f"[WARN] Response too short on attempt {attempt}/{retries} "
                  f"(len={len(content) if content else 0}, "
                  f"finish_reason={choice.finish_reason})")
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
    cutoff = datetime.utcnow() - timedelta(hours=24)
    return [d["title"] for d in data if datetime.fromisoformat(d["time"]) > cutoff]


def save_recent(title: str) -> None:
    data = []
    if os.path.exists(RECENT_LOG):
        with open(RECENT_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.append({"title": title, "time": datetime.utcnow().isoformat()})
    cutoff = datetime.utcnow() - timedelta(hours=24)
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
            if is_relevant(entry) and title not in recent:
                candidates.append({
                    "title": title,
                    "summary": entry.get("summary", ""),
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
    system_instruction = "You write like an opinionated, informal tech blogger who hates PR fluff and corporate buzzwords."
    prompt = PROMPT_TEMPLATE.format(title=title, summary=summary)

    blog_text = call_openrouter(prompt, system_message=system_instruction)

    if not blog_text:
        blog_text = (
            f"# {title}\n\n"
            f"We couldn't generate the full write-up this time — the AI model was "
            f"unavailable or rate-limited. Here's the original summary:\n\n"
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