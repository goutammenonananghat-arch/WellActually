from flask import Flask, request, jsonify, send_from_directory
import requests
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

# =============================================
# PASTE YOUR API KEYS HERE
# =============================================
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"
TAVILY_API_KEY = "YOUR_TAVILY_API_KEY_HERE"   # get free key at tavily.com — no card needed
# =============================================


def tavily_search(query, max_results=5):
    """Search the web using Tavily and return clean text results."""
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=15,
        )
        data = resp.json()

        parts = []
        if data.get("answer"):
            parts.append(f"SUMMARY: {data['answer']}")
        for r in data.get("results", []):
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            parts.append(f"SOURCE: {title}\nCONTENT: {content}\nURL: {url}")

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        print(f"  Tavily error: {e}")
        return ""


def groq_call(messages, max_tokens=4000, temperature=0.5):
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        timeout=60,
    )
    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")


@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "gem6.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    system = data.get("system", "")
    messages = data.get("messages", [])
    claim = messages[0]["content"] if messages else ""

    print(f"\n🔍 Claim: {claim}")

    # ── STEP 1: Ask Groq what to search for ───────────────────────────────────
    print("🧠 Step 1: Deciding what to search...")
    search_plan_prompt = f"""A user wants to fact-check this football claim: "{claim}"

List 3-4 specific web search queries that would find the real statistics needed to evaluate this claim.
Focus on: career totals, current season stats, trophies/titles won, award history, head-to-head records.

Reply ONLY with a JSON array of query strings. Example:
["Mo Salah Premier League goals career total 2025", "Mo Salah assists Premier League all time", "Liverpool Premier League titles won"]"""

    queries = []
    try:
        raw = groq_call([{"role": "user", "content": search_plan_prompt}], max_tokens=300, temperature=0.2)
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            queries = json.loads(raw[start:end])
        print(f"📋 Planned searches: {queries}")
    except Exception as e:
        print(f"  Search planning failed: {e}")
        queries = [claim + " football statistics 2025"]

    # ── STEP 2: Execute searches via Tavily ───────────────────────────────────
    print(f"🌐 Step 2: Searching ({len(queries)} queries)...")
    all_results = []
    for q in queries[:4]:
        print(f"   → {q}")
        result = tavily_search(q)
        if result:
            all_results.append(f"SEARCH: {q}\n{result}")

    research_text = "\n\n========\n\n".join(all_results) if all_results else "No search results found."
    print(f"📝 Research gathered: {len(research_text)} chars")

    # ── STEP 3: Format into JSON using Groq ───────────────────────────────────
    print("📊 Step 3: Formatting into JSON...")
    format_prompt = f"""You have gathered the following real web search results to fact-check this claim:

CLAIM: "{claim}"

SEARCH RESULTS:
{research_text}

Now use ONLY the numbers found in the search results above to build the response.
Do not use any numbers from your own memory — only use what the searches found.

{system}

CLAIM TO INVESTIGATE: {claim}

Output ONLY the raw JSON object. Start with {{ and end with }}. No text outside the JSON."""

    try:
        text = groq_call([{"role": "user", "content": format_prompt}], max_tokens=3500, temperature=0.6)

        print(f"\n--- FINAL RESPONSE ---")
        print(f"Length: {len(text)}")
        print(f"First 300 chars: {text[:300]}")
        print(f"Last 100 chars: {text[-100:]}")
        print("----------------------\n")

        return jsonify({"content": [{"type": "text", "text": text}]})

    except Exception as e:
        print(f"Step 3 error: {e}")
        return jsonify({"content": [{"type": "text", "text": ""}]}), 500


if __name__ == "__main__":
    print("=" * 50)
    print("  Well Actually 🤓👆 — Server")
    print("=" * 50)
    if "YOUR_TAVILY" in TAVILY_API_KEY:
        print("⚠️  WARNING: Add your Tavily API key! (free at tavily.com)")
    else:
        print("✅ Tavily search key loaded")
    if "YOUR_GROQ" in GROQ_API_KEY:
        print("⚠️  WARNING: Set your Groq API key!")
    else:
        print("✅ Groq key loaded")
    print("🌐 Mode: Tavily search → Groq format (reliable 3-step pipeline)")
    print("✅ Running at http://localhost:5050")
    print("👉 Open your browser and go to: http://localhost:5050")
    app.run(port=5050)