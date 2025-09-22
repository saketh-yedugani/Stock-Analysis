# Stock Analysis Project
After reading multiple books on stock analysis, I selected a set of key metrics to help filter the best-performing stocks to invest in.

The goal of this project is to save time by programmatically analyzing S&P 500, NASDAQ 100, and Dow Jones 30 companies, instead of manually reviewing financial reports. This way, I can quickly identify strong candidates for investment.

# Analysis Metrics-

# 1. Gross Profit Growth (GP%)-
-GP_Trend_Score measures the growth trend of Gross Profit over the last 4 years.
-If gross profit consistently grows, the score approaches 1.

# 2. Liabilities Year-over-Year (Liability YOY%)
-Tracks whether a company’s liabilities are increasing or decreasing.
-Liability_Trend_Score ranges between -1 and 1, where a decreasing liability trend gives a higher score.

# 3. Earnings Per Share (EPS%)
-EPS_Trend_Score reflects the growth of earnings per share over time.
-The score ranges from -1 to 1, with consistent growth leaning positive.

# 4. Liability-to-Asset Ratio
-Calculates what percentage of a company’s assets can cover its liabilities.
-Normalized into a score between -1 and 1 for fair comparison across companies.

# 5. Institutional Holdings
-Shows how much of the company is owned by the top 10 global investment institutions (e.g., Vanguard, BlackRock, JPMorgan).
-Also tracks whether their holdings increased or decreased recently.

# Final Scoring
-The Final Score is the weighted sum of all the above metrics
-Companies are then ranked based on their Final Score, making it easier to identify strong investment opportunities.