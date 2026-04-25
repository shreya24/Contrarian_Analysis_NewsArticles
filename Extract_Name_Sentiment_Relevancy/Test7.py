# code written with gpt-5 model. Did not return author_name for paywalled article. code is working though
# It was not working at first. Changed code a bit from the version for gpt-4
import os
import asyncio
import pandas as pd
import aiohttp
import json
import random
import math
from typing import Optional


async def main(url):
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_KEY = "abc"
    OPENAI_MODEL = "gpt-5-mini"  # must support web_search_preview with Responses API
    OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"  # Responses API

    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 100))
    RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", 300))
    REQUEST_INTERVAL = 60 / RATE_LIMIT_RPM

    global semaphore
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def build_prompt(u):
        return f"""
Input news article url is: {u}

Questions:
1) Who is the author of this article? 
2) What is the overall sentiment of the article toward the mentioned company? Use one of: "positive", "neutral", "negative".
3) Is this article relevant for predicting the company's upcoming earnings? Return true/false.
- Consider relevance TRUE if it includes concrete signals likely to affect revenue, margins, costs, guidance, demand, regulations, product/price changes, major deals, supply chain issues, unit volumes, or management commentary tied to the current/next quarter. Rumors/gossip/general market news should be FALSE.
        """.strip()
    


    def extract_text_response(result: dict) -> Optional[str]:
        # 1) Convenience field many SDKs expose
        s = result.get("output_text")
        if isinstance(s, str) and s.strip():
            return s

        # 2) Canonical Responses structure
        for item in result.get("output", []) or []:
            for part in item.get("content", []) or []:
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    return part["text"]

        # 3) Some SDKs expose a 'message' wrapper
        msg = result.get("message")
        if isinstance(msg, dict):
            for part in msg.get("content", []) or []:
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    return part["text"]
        return None

    async def process_row_async(u):
        async with semaphore:
            user_prompt = build_prompt(u)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            }

            # Responses API payload with web_search_preview tool enabled & forced
            payload = {
                "model": OPENAI_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Use the web_search_preview tool to find and read the specified news article URL, "
                                    "extract the requested fields, and return ONLY valid JSON that matches the schema. "
                                    "Do not include explanations or extra text."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_prompt}
                        ],
                    },
                ],
                "tools": [
                    {"type": "web_search_preview"}
                ],
                "tool_choice": {"type": "web_search_preview"},
                "text": {
                    "format": {
                        "type": "json_schema", 
                        "name": "article_analysis_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "author_names": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "author_name": {"type": "string"}
                                        },
                                        "required": ["author_name"],
                                        "additionalProperties": False,
                                    },
                                },
                                "sentiment": {
                                    "type": "string",
                                    "enum": ["positive", "neutral", "negative"],
                                },
                                "relevant_for_earnings": {"type": "boolean"},
                            },
                            "required": [
                                "author_names",
                                "sentiment",
                                "relevant_for_earnings"
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "max_output_tokens": 6000,
            }
            # simple jitter to respect RPM
            await asyncio.sleep(REQUEST_INTERVAL * (0.8 + 0.4 * random.random()))

            MAX_RETRIES = 3
            BACKOFF_BASE = 1.8

            client_timeout = aiohttp.ClientTimeout(
                total=120,           # generous total budget
                connect=20,          # connect timeout
                sock_read=90,        # read timeout
                sock_connect=20,     # TLS handshake, etc.
            )

            try:
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    attempt = 0
                    while True:
                        try:
                            async with session.post(OPENAI_ENDPOINT, headers=headers, json=payload) as response:
                                body_text = await response.text()

                                # Retry on 429 and 5xx
                                if response.status in (429, 500, 502, 503, 504):
                                    if attempt < MAX_RETRIES:
                                        sleep_s = (BACKOFF_BASE ** attempt) + random.random()
                                        await asyncio.sleep(sleep_s)
                                        attempt += 1
                                        continue
                                    else:
                                        raise RuntimeError(f"OpenAI API Error {response.status}: {body_text[:500]}")

                                if response.status != 200:
                                    raise RuntimeError(f"OpenAI API Error {response.status}: {body_text[:500]}")

                                # Success: parse JSON
                                try:
                                    result = json.loads(body_text)
                                except json.JSONDecodeError as je:
                                    raise RuntimeError(f"Non-JSON response from API: {body_text[:500]}") from je

                                text_response = extract_text_response(result)
                                if not text_response:
                                    raise RuntimeError("No text content found in Responses API payload.")

                                try:
                                    json_output = json.loads(text_response)
                                except json.JSONDecodeError:
                                    # Return a structured error instead of None so the caller can keep going
                                    print(f"Warning: Could not parse model JSON. Raw text:\n{text_response}")
                                    json_output = {
                                        "author_names": [],
                                        "sentiment": "neutral",
                                        "relevant_for_earnings": False,
                                        "_error": "model_output_not_valid_json"
                                    }
                                return json_output

                        except asyncio.TimeoutError:
                            if attempt < MAX_RETRIES:
                                sleep_s = (BACKOFF_BASE ** attempt) + random.random()
                                await asyncio.sleep(sleep_s)
                                attempt += 1
                                continue
                            else:
                                raise RuntimeError("Timed out calling Responses API after retries.")
                        except aiohttp.ClientError as ce:
                            if attempt < MAX_RETRIES:
                                sleep_s = (BACKOFF_BASE ** attempt) + random.random()
                                await asyncio.sleep(sleep_s)
                                attempt += 1
                                continue
                            else:
                                raise RuntimeError(f"Network error calling Responses API: {ce!r}")
            except Exception as e:
                # Ensure the exception message is visible
                print(f"Error processing row: {e}")
                return None

    processed = await process_row_async(url)
    print(processed)
    return processed


if __name__ == "__main__":
    author_list = []
    sentiment_list = []
    relevance_list = []

    processed_rows = asyncio.run(
        main("https://www.wsj.com/tech/apple-violated-antitrust-ruling-federal-judge-finds-66b85957")
    )

    # author
    if processed_rows and "author_names" in processed_rows and isinstance(processed_rows["author_names"], list) and len(processed_rows["author_names"]) > 0:
        name = processed_rows["author_names"][0].get("author_name")
    else:
        name = None
    author_list.append(name)

    # sentiment
    sentiment = None
    if processed_rows and isinstance(processed_rows, dict):
        s = processed_rows.get("sentiment")
        if s in {"positive", "neutral", "negative"}:
            sentiment = s
    sentiment_list.append(sentiment)

    # relevance
    relevance = None
    if processed_rows and isinstance(processed_rows, dict):
        rel_val = processed_rows.get("relevant_for_earnings")
        if isinstance(rel_val, bool):
            relevance = rel_val
    relevance_list.append(relevance)