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

CATEGORIES = {
    "humanoid": ["humanoid", "bipedal", "android robot"],
    "drone": ["drone", "uav", "aerial robot", "quadcopter"],
    "industrial": ["industrial", "manufacturing", "warehouse", "factory", "cobot", "assembly line"],
    "ai_hardware": ["isaac", "jetson", "omniverse", "nvidia", "gpu", "chip"],
    "arm_gripper": ["robotic arm", "gripper", "manipulator", "actuator"],
    "research": ["study", "paper", "researchers", "university"],
}


def classify_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for category, kws in CATEGORIES.items():
        if any(kw in text for kw in kws):
            return category
    return "general"


SELECTOR_PROMPT = """Below is a list of robotics news headlines with summaries.

Pick the SINGLE most important, most newsworthy, most demanding-of-attention story — the one a serious robotics industry follower would care about most today. Ignore anything that is not core robotics/AI-hardware news (skip general AI, food-tech, unrelated software stories even if they mention "robot" in passing).

CANDIDATE STORIES:
{numbered_list}

Respond with ONLY the number of your pick. No explanation.
"""

PROMPT_TEMPLATE = """You are a robotics journalist with your own blog. You've covered this beat for years — you've seen hype cycles come and go, you have favorite companies and ones you're skeptical of, and you write the way you'd explain something to a friend over coffee, not the way a press release reads.

News to base this post on:
Title: {title}
Summary: {summary}

Write a complete blog post with this structure:

1. **Title** (# heading) — your own angle on the story, not a restatement of the source headline
2. **Opening** — 2-3 sentences that pull the reader in immediately. A surprising fact, a pointed question, or your own reaction to the news. No throat-clearing, no "In the world of robotics today..."
3. **The story** — 3-4 sections (## headings) explaining what actually happened and why it matters. Don't just restate the summary — explain it like you're catching a friend up, filling gaps with what you know about the space
4. **Your take** — at least one full paragraph, clearly your own opinion. Take a real position: excited, skeptical, cautiously optimistic, whatever fits. Reference something specific from the industry's past (a company that tried something similar and failed, a prediction that didn't age well, a competitor's different approach) to back up your view
5. **## Key Takeaways** — 3-4 sharp, specific bullet points (not vague summaries — each should teach the reader something concrete)
6. **## What Comes Next** — a short closing thought, forward-looking, in your own voice

WRITING STYLE — this is what makes it sound real, not generated:
- Sentences of wildly different lengths sitting next to each other. A long one that winds through a thought, then something short. Like that.
- Contractions everywhere — it's, don't, that's, you'd, wouldn't
- At least one sentence that starts with "And" or "But"
- At least one rhetorical question
- One genuinely specific, non-generic analogy — tied to something concrete in engineering or robotics, not a cliché
- Numbers and specifics where you have them (dates, dollar amounts, model names) — vague writing reads as fake
- No AI-sounding filler: skip "In today's fast-paced world," "game-changer," "revolutionize," "delve into," "it's worth noting," "moreover," "furthermore," "landscape," "navigate," "underscore," "in conclusion"
- Don't write in perfectly balanced three-item lists inside sentences ("faster, cheaper, and smarter") — real writers usually just pick one or two things to emphasize
- One small personal aside somewhere — a pet peeve, a past prediction you got wrong, something you've noticed covering this beat — even a single sentence

CONTENT RULES:
- Rewrite everything in your own words — never lift phrasing from the summary
- Add real context: competitors, history, past attempts at similar things, what usually goes wrong or right in situations like this
- Never mention you're an AI or that this is generated

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


def load_recent() -> list[dict]:
    if not os.path.exists(RECENT_LOG):
        return []
    with open(RECENT_LOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = []
    for d in data:
        try:
            if datetime.fromisoformat(d["time"]) > cutoff:
                result.append(d)
        except (KeyError, ValueError):
            continue
    return result


def get_recent_slugs(recent: list[dict]) -> list[str]:
    return [d.get("slug") or slugify(d.get("title", ""))[:60] for d in recent]


def get_recent_categories(recent: list[dict], limit: int = 3) -> list[str]:
    sorted_recent = sorted(recent, key=lambda d: d["time"], reverse=True)
    return [d.get("category", "general") for d in sorted_recent[:limit]]


def save_recent(title: str, category: str) -> None:
    data = []
    if os.path.exists(RECENT_LOG):
        with open(RECENT_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)

    slug = slugify(title)[:60]
    data.append({
        "title": title,
        "slug": slug,
        "category": category,
        "time": datetime.utcnow().isoformat(),
    })

    cutoff = datetime.utcnow() - timedelta(days=7)
    cleaned = []
    for d in data:
        try:
            if datetime.fromisoformat(d["time"]) > cutoff:
                cleaned.append(d)
        except (KeyError, ValueError):
            continue

    with open(RECENT_LOG, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)


def fetch_candidates() -> list[dict]:
    recent = load_recent()
    recent_slugs = get_recent_slugs(recent)
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
            title_slug = slugify(title)[:60]
            if is_relevant(entry) and title_slug not in recent_slugs:
                candidates.append({
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "category": classify_category(title, summary),
                })

    return candidates


def pick_most_important(candidates: list[dict]) -> dict:
    if len(candidates) == 1:
        return candidates[0]

    recent = load_recent()
    recent_categories = get_recent_categories(recent, limit=3)

    # Prefer candidates whose category hasn't been covered in the last 3 posts
    fresh_pool = [c for c in candidates if c["category"] not in recent_categories]
    pool = fresh_pool if fresh_pool else candidates

    numbered_list = "\n\n".join(
        f"{i+1}. [{c['category']}] {c['title']}\n{c['summary'][:200]}"
        for i, c in enumerate(pool)
    )
    prompt = SELECTOR_PROMPT.format(numbered_list=numbered_list)

    result = call_openrouter(prompt).strip()

    try:
        idx = int(result.split()[0]) - 1
        if 0 <= idx < len(pool):
            return pool[idx]
    except (ValueError, IndexError):
        pass

    return pool[0]


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

    print(f"[SELECTED] ({article['category']}) {article['title']}")
    save_recent(article["title"], article["category"])

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