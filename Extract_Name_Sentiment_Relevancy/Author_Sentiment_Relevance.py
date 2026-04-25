import os
import asyncio
import pandas as pd
import aiohttp
import json
import random


async def main(url):
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_KEY = "abc"
    OPENAI_MODEL = "gpt-4o-search-preview"
    OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

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
        """

    async def process_row_async(u):
        async with semaphore:
            prompt = build_prompt(u)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }

            payload = {
                "model": OPENAI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Find and read the specified news article URL, "
                            "extract the requested fields, and return **only valid JSON** that matches the provided schema. "
                            "Do not include explanations or extra text."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "article_analysis_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "author_names": {
                                    "type": "array",
                                    "description": "List of authors found on the page.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "author_name": {
                                                "type": "string",
                                                "description": "The name of the author."
                                            }
                                        },
                                        "required": ["author_name"],
                                        "additionalProperties": False
                                    }
                                },
                                "sentiment": {
                                    "type": "string",
                                    "description": "Overall sentiment of the article toward the company.",
                                    "enum": ["positive", "neutral", "negative"]
                                },
                                "relevant_for_earnings": {
                                    "type": "boolean",
                                    "description": "True if the article contains concrete information useful for predicting near-term earnings."
                                }
                            },
                            "required": ["author_names", "sentiment", "relevant_for_earnings"],
                            "additionalProperties": False
                        }
                    }
                },
                "max_completion_tokens": 2000
                # "temperature": 0
            }

            # simple jitter to respect RPM
            await asyncio.sleep(REQUEST_INTERVAL * (0.8 + 0.4 * random.random()))

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=20) as response:
                        if response.status == 200:
                            result = await response.json()
                            print("RAW RESPONSE:", result)
                            text_response = result["choices"][0]["message"]["content"]
                            
                            try:
                                json_output = json.loads(text_response)
                            except json.JSONDecodeError:
                                print(f"Warning: Could not parse JSON, returning raw text instead:\n{text_response}")
                                json_output = {}
                            return json_output
                        else:
                            error_text = await response.text()
                            raise RuntimeError(f"OpenAI API Error {response.status}: {error_text}")
                            # print(f"OpenAI API Error {response.status}: {await response.text()}")
                            # return None
            except Exception as e:
                print(f"Error processing row: {e}")
                return None

    processed = await process_row_async(url)
    print(processed)
    return processed


if __name__ == "__main__":
    author_list = []
    sentiment_from_OpenAI_list = []
    relevance_list = []

    input_file = "/Users/shreya/Documents/UCDavis/BAX_423_Big_Data_Analytics/Final_Project/Summer_Quarter/S_P_500/StockNewsAPI_NewsExtracted/ALB_combined_earnings.xlsx"
    xls = pd.ExcelFile(input_file)

    for sheet_name in xls.sheet_names:
        print(f"\nProcessing sheet: {sheet_name}")
        df = pd.read_excel(input_file, sheet_name=sheet_name)
        urls = df["news_url"]
        for url in urls:
            processed_rows = asyncio.run(main(url))

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
            sentiment_from_OpenAI_list.append(sentiment)

            # relevance
            relevance = None
            if processed_rows and isinstance(processed_rows, dict):
                rel_val = processed_rows.get("relevant_for_earnings")
                if isinstance(rel_val, bool):
                    relevance = rel_val
            relevance_list.append(relevance)

        for url in urls:
            processed_rows = asyncio.run(main(url))

        # author
        if processed_rows and "author_names" in processed_rows and isinstance(processed_rows["author_names"], list) and len(processed_rows["author_names"]) > 0:
            name = processed_rows["author_names"][0].get("author_name")
        else:
            name = None
        author_list.append(name)

        # sentiment
        sentiment_from_OpenAI = None
        if processed_rows and isinstance(processed_rows, dict):
            s = processed_rows.get("sentiment")
            if s in {"positive", "neutral", "negative"}:
                sentiment_from_OpenAI = s
        sentiment_from_OpenAI_list.append(sentiment_from_OpenAI)

        # relevance
        relevance = None
        if processed_rows and isinstance(processed_rows, dict):
            rel_val = processed_rows.get("relevant_for_earnings")
            if isinstance(rel_val, bool):
                relevance = rel_val
        relevance_list.append(relevance)

        df["author_name"] = author_list
        df["sentiment_from_OpenAI"] = sentiment_from_OpenAI_list
        df["relevant_for_earnings"] = relevance_list

        output_path = "/Users/shreya/Documents/UCDavis/BAX_423_Big_Data_Analytics/Final_Project/Summer_Quarter/S_P_500/StockNewsAPI_NewsExtracted/ALB_combined_earnings_enriched.xlsx"
        df.to_csv(output_path, index=False)
        print(f"Wrote {len(df)} rows to {output_path}")