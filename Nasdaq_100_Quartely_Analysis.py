import pandas as pd
import requests
import yfinance as yf
import numpy as np


# NASDAQ 100 symbols

url = "https://www.slickcharts.com/nasdaq100"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
response.raise_for_status()
tables = pd.read_html(response.text)
sp500_table = tables[0]
symbols = sp500_table['Symbol'].tolist()  


# Quarterly Financials

results = []

for symbol in symbols:
    ticker = yf.Ticker(symbol)
    try:
        income_q = ticker.quarterly_financials.T
        balance_q = ticker.quarterly_balance_sheet.T

        income_q = income_q.apply(pd.to_numeric, errors='coerce')
        balance_q = balance_q.apply(pd.to_numeric, errors='coerce')

        # Income statement
        for period in income_q.index:
            gp = income_q.get('Gross Profit', pd.Series()).get(period, np.nan)
            if 'Basic EPS' in income_q.columns:
                eps = income_q['Basic EPS'].get(period, np.nan)
            elif 'Diluted EPS' in income_q.columns:
                eps = income_q['Diluted EPS'].get(period, np.nan)
            else:
                eps = np.nan
            results.append({
                'Symbol': symbol,
                'Period': period,
                'Gross_Profit': gp,
                'EPS': eps
            })

        # Balance sheet
        for period in balance_q.index:
            cl = balance_q.get('Current Liabilities', pd.Series()).get(period, np.nan)
            ocl = balance_q.get('Other Current Liabilities', pd.Series()).get(period, 0)
            ta = balance_q.get('Total Assets', pd.Series()).get(period, np.nan)
            # Match existing row if exists
            match = next((r for r in results if r['Symbol'] == symbol and r['Period'] == period), None)
            if match:
                match['Current_Liabilities'] = cl
                match['Other_Current_Liabilities'] = ocl
                match['Total_Assets'] = ta
            else:
                results.append({
                    'Symbol': symbol,
                    'Period': period,
                    'Gross_Profit': np.nan,
                    'EPS': np.nan,
                    'Current_Liabilities': cl,
                    'Other_Current_Liabilities': ocl,
                    'Total_Assets': ta
                })
    except Exception as e:
        print(f"Could not fetch quarterly financials for {symbol}: {e}")

df = pd.DataFrame(results)
if not df.empty:
    df = df.sort_values(['Symbol', 'Period'])
    num_cols = ['Gross_Profit','EPS','Current_Liabilities','Other_Current_Liabilities','Total_Assets']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['Quarter'] = df['Period'].dt.to_period("Q").astype(str)

    # QoQ %
    df['Gross_Profit_QoQ_%'] = df.groupby('Symbol')['Gross_Profit'].transform(lambda x: (x - x.shift(1)) / x.shift(1) * 100)
    df['EPS_QoQ_%'] = df.groupby('Symbol')['EPS'].transform(lambda x: (x - x.shift(1)) / x.shift(1) * 100)
    df['Liability_QoQ_%'] = df.groupby('Symbol')['Current_Liabilities'].transform(lambda x: (x - x.shift(1)) / x.shift(1) * 100)

    # Liability-to-Asset ratio
    df['Liability_to_Asset_Ratio'] = (df['Current_Liabilities'].fillna(0) + df['Other_Current_Liabilities'].fillna(0)) / df['Total_Assets'] * 100

   
    # Pivot tables using pivot_table (avoids duplicates)
    
    df_gp = df.pivot_table(index='Symbol', columns='Quarter', values='Gross_Profit_QoQ_%', aggfunc='mean')
    df_liab = df.pivot_table(index='Symbol', columns='Quarter', values='Liability_QoQ_%', aggfunc='mean')
    df_eps = df.pivot_table(index='Symbol', columns='Quarter', values='EPS_QoQ_%', aggfunc='mean')
    df_ratio = df.groupby('Symbol')['Liability_to_Asset_Ratio'].mean().to_frame()

    # Keep last 4 quarters only
    last4_qtrs = sorted(df['Quarter'].unique())[-4:]
    df_gp = df_gp.reindex(columns=last4_qtrs)
    df_liab = df_liab.reindex(columns=last4_qtrs)
    df_eps = df_eps.reindex(columns=last4_qtrs)

    # Rename columns
    df_gp.columns = [f"{q}(GP%)" for q in df_gp.columns]
    df_liab.columns = [f"{q}(Liability%)" for q in df_liab.columns]
    df_eps.columns = [f"{q}(EPS%)" for q in df_eps.columns]

    # Combine financials
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
                org_row = institutional_holders[institutional_holders['Holder'].str.contains(org, case=False, na=False)]
                if not org_row.empty:
                    holder_name = org_row['Holder'].iloc[0]
                    pct_held = org_row['pctHeld'].iloc[0] * 100
                    pct_change = org_row['pctChange'].iloc[0] * 100
                    results.append(f"{holder_name}: Held {pct_held:.2f}% | Change {pct_change:.2f}%")
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

inst_data = {t: get_filtered_institutional_data_df(t, organizations_list) for t in symbols}
df_institutional = pd.DataFrame.from_dict(inst_data, orient='index', columns=['Institutional_Holdings'])


# Trend Scoring (last 4 quarters)

df_combined = df_final.merge(df_institutional, left_index=True, right_index=True).reset_index()
df_combined.rename(columns={"index": "Symbol"}, inplace=True)

def trend_score(values):
    values = [v for v in values if pd.notna(v)]
    if len(values) < 2:
        return 0
    x = np.arange(len(values))
    y = np.array(values)
    slope = np.polyfit(x, y, 1)[0]
    return np.tanh(slope / 50)

gp_quarters = [c for c in df_combined.columns if "(GP%)" in c][-4:]
liab_quarters = [c for c in df_combined.columns if "(Liability%)" in c][-4:]
eps_quarters = [c for c in df_combined.columns if "(EPS%)" in c][-4:]

df_combined['GP_Trend_Score'] = df_combined.apply(lambda row: trend_score([row[q] for q in gp_quarters]), axis=1)
df_combined['Liability_Trend_Score'] = df_combined.apply(lambda row: -trend_score([row[q] for q in liab_quarters]), axis=1)
df_combined['EPS_Trend_Score'] = df_combined.apply(lambda row: trend_score([row[q] for q in eps_quarters]), axis=1)

min_val = df_combined["Liability_to_Asset_Ratio"].min()
max_val = df_combined["Liability_to_Asset_Ratio"].max()
df_combined["Liability_to_Asset_Score"] = (df_combined["Liability_to_Asset_Ratio"] - min_val) / (max_val - min_val)

df_combined["Final_Score"] = (
    df_combined["GP_Trend_Score"] +
    df_combined["Liability_Trend_Score"] +
    df_combined["EPS_Trend_Score"] +
    df_combined["Liability_to_Asset_Score"]
)

df_combined = df_combined.sort_values("Final_Score", ascending=False).reset_index(drop=True)


# Export

output_file = "Nasdaq100_Quarterly_Data_Analysis.xlsx"
df_combined.to_excel(output_file, sheet_name="All_Data", index=False)
print(f"\n Quarterly data exported: {output_file}")
print(df_combined[["Symbol","Final_Score"]])
