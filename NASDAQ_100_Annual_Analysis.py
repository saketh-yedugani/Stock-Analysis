import pandas as pd
import requests
import yfinance as yf
import numpy as np
from datetime import datetime


# NASDAQ 100 symbols

url = "https://www.slickcharts.com/nasdaq100"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
response.raise_for_status()
tables = pd.read_html(response.text)
nasdaq100_table = tables[0]
symbols = nasdaq100_table['Symbol'].tolist()  


# Financials (Gross Profit, Liabilities, EPS)

current_year = datetime.now().year - 1
start_year = current_year - 3  # last 4 years
results = []

for symbol in symbols:
    ticker = yf.Ticker(symbol)
    try:
        income = ticker.financials.T
        balance = ticker.balance_sheet.T

        # Ensure numeric
        income = income.apply(pd.to_numeric, errors='coerce')
        balance = balance.apply(pd.to_numeric, errors='coerce')

        # Collect Gross Profit & EPS
        for year in income.index:
            year_int = year.year
            if start_year <= year_int <= current_year:
                gp = income.get('Gross Profit', pd.Series()).get(year, np.nan)

                # EPS (Basic EPS or Diluted EPS)
                if 'Basic EPS' in income.columns:
                    eps = income['Basic EPS'].get(year, np.nan)
                elif 'Diluted EPS' in income.columns:
                    eps = income['Diluted EPS'].get(year, np.nan)
                else:
                    eps = np.nan

                results.append({
                    'Symbol': symbol,
                    'Year': year_int,
                    'Gross_Profit': gp,
                    'EPS': eps
                })

        # Collect Balance Sheet items
        for year in balance.index:
            year_int = year.year
            if start_year <= year_int <= current_year:
                cl = balance.get('Current Liabilities', pd.Series()).get(year, np.nan)
                ocl = balance.get('Other Current Liabilities', pd.Series()).get(year, 0)
                ta = balance.get('Total Assets', pd.Series()).get(year, np.nan)

                # Update existing record
                match = next((r for r in results if r['Symbol']==symbol and r['Year']==year_int), None)
                if match:
                    match['Current_Liabilities'] = cl
                    match['Other_Current_Liabilities'] = ocl
                    match['Total_Assets'] = ta
                else:
                    results.append({
                        'Symbol': symbol,
                        'Year': year_int,
                        'Gross_Profit': np.nan,
                        'EPS': np.nan,
                        'Current_Liabilities': cl,
                        'Other_Current_Liabilities': ocl,
                        'Total_Assets': ta
                    })
    except Exception as e:
        print(f"Could not fetch financials for {symbol}: {e}")

df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values(['Symbol','Year'])

    # Convert all numeric columns
    num_cols = ['Gross_Profit','EPS','Current_Liabilities','Other_Current_Liabilities','Total_Assets']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Gross Profit YOY %
    df['Gross_Profit_YOY_%'] = df.groupby('Symbol')['Gross_Profit'].transform(lambda x: ((x - x.shift(1))/x.shift(1))*100)

    # Current Liabilities YOY %
    df['Liability_YOY_%'] = df.groupby('Symbol')['Current_Liabilities'].transform(lambda x: ((x - x.shift(1))/x.shift(1))*100)

    # EPS YOY %
    df['EPS_YOY_%'] = df.groupby('Symbol')['EPS'].transform(lambda x: ((x - x.shift(1))/x.shift(1))*100)

    # Liability-to-Asset Ratio
    df['Liability_to_Asset_Ratio'] = ((df['Current_Liabilities'].fillna(0) + df['Other_Current_Liabilities'].fillna(0)) / df['Total_Assets'] * 100)

    # Pivot tables
    df_gp = df.pivot(index='Symbol', columns='Year', values='Gross_Profit_YOY_%')
    df_liab = df.pivot(index='Symbol', columns='Year', values='Liability_YOY_%')
    df_eps = df.pivot(index='Symbol', columns='Year', values='EPS_YOY_%')
    df_ratio = df.groupby('Symbol')['Liability_to_Asset_Ratio'].mean().to_frame()

    years_order = [current_year, current_year-1, current_year-2, current_year-3]
    df_gp = df_gp.reindex(columns=years_order)
    df_liab = df_liab.reindex(columns=years_order)
    df_eps = df_eps.reindex(columns=years_order)

    df_gp.columns = [f"{year}(GP%)" for year in df_gp.columns]
    df_liab.columns = [f"{year}(LiabilityYOY%)" for year in df_liab.columns]
    df_eps.columns = [f"{year}(EPS%)" for year in df_eps.columns]

    df_final = pd.concat([df_gp, df_liab, df_eps, df_ratio], axis=1)
else:
    df_final = pd.DataFrame(index=symbols)


# Institutional Holdings

def get_filtered_institutional_data_df(ticker_symbol, organizations):
    try:
        stock = yf.Ticker(ticker_symbol)
        institutional_holders = stock.institutional_holders

        if institutional_holders is not None and not institutional_holders.empty:
            results = []
            for org in organizations:
                org_row = institutional_holders[
                    institutional_holders['Holder'].str.contains(org, case=False, na=False)
                ]
                if not org_row.empty:
                    holder_name = org_row['Holder'].iloc[0]
                    pct_held = org_row['pctHeld'].iloc[0] * 100
                    pct_change = org_row['pctChange'].iloc[0] * 100
                    results.append(f"{holder_name}: Held {pct_held:.2f}% | Change {pct_change:.2f}%   ")
            return "; ".join(results) if results else "No match"
        else:
            return "No institutional holders data"
    except Exception as e:
        return f"Error: {e}"

organizations_list = [
    "Vanguard", "Charles Schwab", "BlackRock", "Morgan Stanley",
    "BNY Mellon", "Fidelity", "Goldman Sachs", "Standard Chartered",
    "UBS Group", "Wells Fargo","Berkshire Hathaway","JPMorgan Chase & Co"
]

inst_data = {}
for ticker in symbols:
    inst_data[ticker] = get_filtered_institutional_data_df(ticker, organizations_list)

df_institutional = pd.DataFrame.from_dict(inst_data, orient='index', columns=['Institutional_Holdings'])


# Merge financial + institutional data

df_combined = df_final.merge(df_institutional, left_index=True, right_index=True).reset_index()
df_combined.rename(columns={"index": "Symbol"}, inplace=True)


# Continuous Trend Scoring (-1 to 1)

def trend_score(values):
    values = [v for v in values if pd.notna(v)]
    if len(values) < 2:
        return 0
    x = np.arange(len(values))
    y = np.array(values)
    slope = np.polyfit(x, y, 1)[0]
    return np.tanh(slope / 50)  

df_combined["GP_Trend_Score"] = df_combined.apply(lambda row: trend_score([row.get(f"{y}(GP%)") for y in years_order[::-1]]), axis=1)
df_combined["Liability_Trend_Score"] = df_combined.apply(lambda row: -trend_score([row.get(f"{y}(LiabilityYOY%)") for y in years_order[::-1]]), axis=1)  # negative slope good
df_combined["EPS_Trend_Score"] = df_combined.apply(lambda row: trend_score([row.get(f"{y}(EPS%)") for y in years_order[::-1]]), axis=1)

# Normalize Liability-to-Asset Ratio
min_val = df_combined["Liability_to_Asset_Ratio"].min()
max_val = df_combined["Liability_to_Asset_Ratio"].max()
df_combined["Liability_to_Asset_Score"] = (df_combined["Liability_to_Asset_Ratio"] - min_val) / (max_val - min_val)

# Final Score
df_combined["Final_Score"] = (
    df_combined["GP_Trend_Score"] +
    df_combined["Liability_Trend_Score"] +
    df_combined["EPS_Trend_Score"] +
    df_combined["Liability_to_Asset_Score"]
)

df_combined = df_combined.sort_values("Final_Score", ascending=False).reset_index(drop=True)


# Export to Excel

output_file = "Nasdaq100_Annually_Data_Analysis.xlsx"
df_combined.to_excel(output_file, sheet_name="All_Data", index=False)

print(f"\nAnually data exported: {output_file}")
print(df_combined[["Symbol","Final_Score"]])

