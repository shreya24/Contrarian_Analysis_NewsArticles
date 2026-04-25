# Contrarian_Analysis_NewsArticles
This code was written as part of my Big data project, "Can systematic identification and tracking of contrarian financial analysts provide superior investment signals compared to following market consensus?", under the guidance of Professor Pantelis Loupos.

1. Extract_NewsArticle_HeadBody: Uses newsapi platform for getting news articles heading and content body using their APIs.
2. Scraping_GetNewsArticles: Scrapes news articles from media publishers basis using Playwright. 
3. Extract_Name_Sentiment_Relevancy: Used to extract author name, sentiment, and relevancy of article to earnings or not.
4. EarningsDateExtractorSEC: I tried extracting earnings dates for companies from SEC filings. We planned to use these dates and extract news articles 30 days around these dates.
5. LangChain_SentimentAnalysis: I tried using GPT-4o-mini inside LangChain to extract author name, sentiment, and relevancy of article to earnings or not.
6. Llama3_Sentiment_Analysis: I tried using Llama3 on groq cloud for sentiment analysis
7. Contrarian_Identification_Summary: Compares reported and forecasted EPS to classify articles as aligned or contrarian. Percentage of sentiment correctly predicting the earnings surprise shown

