import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
BLOG_DIR = os.path.join(DATA_DIR, "blogs")

RSS_SOURCES = [
    "https://spectrum.ieee.org/feeds/topic/robotics.rss",
    "https://www.therobotreport.com/feed/",
    "https://techcrunch.com/tag/robotics/feed/",
    "https://blogs.nvidia.com/feed/",
    "https://roboticsandautomationnews.com/feed/",
]

KEYWORDS = [
    "robot",
    "robotics",
    "humanoid",
    "robotic arm",
    "drone",
    "autonomous machine",
    "isaac",
    "jetson",
    "omniverse",
]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"