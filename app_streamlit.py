import streamlit as st
import pandas as pd
import glob
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Tactical Analyzer", page_icon="⚽", layout="centered")

# --- КОНСТАНТЫ ---
EXTRAPOLATION_FACTOR = 2.17 
BANK_FILE = "bank_history.csv"
PENDING_FILE = "pending_bets.csv"
CONFIG_FILE = "bank_config.json"

league_map = {
    'Англия (АПЛ)': 'E0', 
    'Испания (Ла Лига)': 'SP1', 
    'Италия (Серия А)': 'I1',
    'Германия (Бундеслига)': 'D1',
    'Франция (Лига 1)': 'F1',
    'ВСЕ НИШЕВЫЕ ЛИГИ (Сборная)': 'NICHE'
}

# ==========================================
# 1. ЗАГРУЗКА ДАННЫХ
# ==========================================
@st.cache_data
def load_data():
    file_list = glob.glob('data/**/*.csv', recursive=True)
    file_list = [f for f in file_list if 'bank_history' not in f and 'pitch_epl' not in f and 'pending_bets' not in f]
    
    all_dfs = []
    for file in file_list:
        try:
            temp_df = pd.read_csv(file)
            if 'HST' in temp_df.columns and 'AST' in temp_df.columns:
                if 'HS' not in temp_df.columns: temp_df['HS'] = 0
                if 'AS' not in temp_df.columns: temp_df['AS'] = 0
                if 'HxG' not in temp_df.columns: temp_df['HxG'] = 0
                if 'AxG' not in temp_df.columns: temp_df['AxG'] = 0
                if 'HC' not in temp_df.columns: temp_df['HC'] = 0
                if 'AC' not in temp_df.columns: temp_df['AC'] = 0
                all_dfs.append(temp_df)
        except: pass

    if not all_dfs:
        return pd.DataFrame()
        
    df = pd.concat(all_dfs, ignore_index=True)
    df['TotalGoals'] = df['FTHG'] + df['FTAG']
    df['Div'] = df['Div'].astype(str).str.strip()
    return df

df = load_data()

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def init_files():
    if not os.path.exists(BANK_FILE):
        pd.DataFrame(columns=['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат']).to_csv(BANK_FILE, index=False)
    if not os.path.exists(PENDING_FILE):
        pd.DataFrame(columns=['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма']).to_csv(PENDING_FILE, index=False)

def load_csv(filepath, columns):
    init_files()
    try:
        df_csv = pd.read_csv(filepath)
        df_csv['Кф'] = pd.to_numeric(df_csv['Кф'], errors='coerce').fillna(0)
        df_csv['Сумма'] = pd.to_numeric(df_csv['Сумма'], errors='coerce').fillna(0)
        if 'Валуй' in df_csv.columns:
            df_csv['Валуй'] = df_csv['Валуй'].astype(str).replace('nan', '-')
        if 'Лига' not in df_csv.columns: df_csv['Лига'] = 'Неизвестно'
        return df_csv
    except:
        return pd.DataFrame(columns=columns)

def get_starting_bank():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return float(json.load(f).get("starting_bank", 10000.0))
        except: return 10000.0
    return 10000.0

def save_starting_bank(amount):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"starting_bank": amount}, f)

# ==========================================
# 3. ИНТЕРФЕЙС
# ==========================================
st.title("⚽ Tactical Analyzer")

tab1, tab2 = st.tabs(["Анализ матча", "Мой Банк"])

with tab1:
    with st.expander("Ввод данных за 1-й тайм", expanded=True):
        league_name = st.selectbox("Лига", list(league_map.keys()))
        match_name = st.text_input("Название матча", "Реал - Барса")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Хозяева")
            ht_home = st.number_input("Голы", 0, 10, 0, key="ht_home")
            hst = st.number_input("Удары в створ", 0, 20, 0, key="hst")
            hts = st.number_input("Общие удары", 0, 40, 0, key="hts")
            hxg = st.number_input("xG", 0.0, 10.0, 0.0, 0.1, key="hxg")
            hc = st.number_input("Угловые", 0, 20, 0, key="hc")
            
        with c2:
            st.markdown("### Гости")
            ht_away = st.number_input("Голы ", 0, 10, 0, key="ht_away")
            ast = st.number_input("Удары в створ ", 0, 20, 0, key="ast")
            ats = st.number_input("Общие удары ", 0, 40, 0, key="ats")
            axg = st.number_input("xG ", 0.0, 10.0, 0.0, 0.1, key="axg")
            ac = st.number_input("Угловые ", 0, 20, 0, key="ac")
            
    if st.button("АНАЛИЗИРОВАТЬ", type="primary", use_container_width=True):
        if df.empty:
            st.error("База данных не загружена. Проверь папку data.")
        else:
            league_code = league_map[league_name]
            
            hst_est = round(hst * EXTRAPOLATION_FACTOR); ast_est = round(ast * EXTRAPOLATION_FACTOR)
            hts_est = round(hts * EXTRAPOLATION_FACTOR); ats_est = round(ats * EXTRAPOLATION_FACTOR)
            hxg_est = round(hxg * EXTRAPOLATION_FACTOR, 2); axg_est = round(axg * EXTRAPOLATION_FACTOR, 2)
            hc_est = round(hc * EXTRAPOLATION_FACTOR); ac_est = round(ac * EXTRAPOLATION_FACTOR)
            
            if league_code == 'NICHE':
                top5 = ['E0', 'SP1', 'I1', 'D1', 'F1']
                league_df = df[~df['Div'].isin(top5)].copy()
            else:
                league_df = df[df['Div'] == league_code].copy()
                
            score_df = league_df[(league_df['HTHG'] == ht_home) & (league_df['HTAG'] == ht_away)].copy()
            
            if score_df.empty:
                st.warning(f"Нет матчей со счетом {ht_home}:{ht_away}")
            else:
                scenario_name = ""
                filtered_df = pd.DataFrame()
                
                total_corners_1h = hc + ac
                if total_corners_1h >= 8 and hst <= 3 and ast <= 3: 
                    scenario_name = f"{ht_home}:{ht_away} + Много угловых ({hc}:{ac})"
                    filtered_df = score_df[((score_df['HC'] + score_df['AC']) >= hc_est + ac_est - 3)]
                    
                if filtered_df.empty and (hxg > 0 or axg > 0):
                    xg_df = score_df[score_df['HxG'] > 0]
                    if len(xg_df) > 0:
                        strict_xg = xg_df[(xg_df['HxG'] >= hxg_est - 0.5) & (xg_df['HxG'] <= hxg_est + 0.5) & (xg_df['AxG'] >= axg_est - 0.5) & (xg_df['AxG'] <= axg_est + 0.5)]
                        if len(strict_xg) >= 5:
                            filtered_df = strict_xg
                            scenario_name = f"{ht_home}:{ht_away} (xG: ~{hxg_est}-{axg_est})"
                            
                if filtered_df.empty:
                    strict_condition = ((score_df['HST'] >= hst_est - 2) & (score_df['HST'] <= hst_est + 2) & (score_df['AST'] >= ast_est - 2) & (score_df['AST'] <= ast_est + 2))
                    if hts > 0 or ats > 0:
                        strict_condition = strict_condition & (score_df['HS'] >= hts_est - 3) & (score_df['HS'] <= hts_est + 3) & (score_df['AS'] >= ats_est - 3) & (score_df['AS'] <= ats_est + 3)
                    strict_df = score_df[strict_condition]
                    if len(strict_df) >= 15:
                        filtered_df = strict_df
                        scenario_name = f"{ht_home}:{ht_away} (Точный: ~{hst_est}-{ast_est} в створ)"
                        
                if filtered_df.empty:
                    flex_df = pd.DataFrame()
                    if hst > ast:
                        ratio = hst / ast if ast > 0 else 10.0
                        if ratio >= 3.0: scenario_name = f"{ht_home}:{ht_away} + Тотальное доминирование хозяев"; flex_df = score_df[(score_df['HST'] >= score_df['AST'] * 3)]
                        elif ratio >= 2.0: scenario_name = f"{ht_home}:{ht_away} + Сильное доминирование хозяев"; flex_df = score_df[(score_df['HST'] >= score_df['AST'] * 2) & (score_df['HST'] < score_df['AST'] * 3)]
                        elif ratio >= 1.5: scenario_name = f"{ht_home}:{ht_away} + Умеренное доминирование хозяев"; flex_df = score_df[(score_df['HST'] >= score_df['AST'] * 1.5) & (score_df['HST'] < score_df['AST'] * 2)]
                        else: scenario_name = f"{ht_home}:{ht_away} + Небольшой перевес хозяев"; flex_df = score_df[(score_df['HST'] > score_df['AST']) & (score_df['HST'] < score_df['AST'] * 1.5)]
                    elif ast > hst:
                        ratio = ast / hst if hst > 0 else 10.0
                        if ratio >= 3.0: scenario_name = f"{ht_home}:{ht_away} + Тотальное доминирование гостей"; flex_df = score_df[(score_df['AST'] >= score_df['HST'] * 3)]
                        elif ratio >= 2.0: scenario_name = f"{ht_home}:{ht_away} + Сильное доминирование гостей"; flex_df = score_df[(score_df['AST'] >= score_df['HST'] * 2) & (score_df['AST'] < score_df['HST'] * 3)]
                        elif ratio >= 1.5: scenario_name = f"{ht_home}:{ht_away} + Умеренное доминирование гостей"; flex_df = score_df[(score_df['AST'] >= score_df['HST'] * 1.5) & (score_df['AST'] < score_df['HST'] * 2)]
                        else: scenario_name = f"{ht_home}:{ht_away} + Небольшой перевес гостей"; flex_df = score_df[(score_df['AST'] > score_df['HST']) & (score_df['AST'] < score_df['HST'] * 1.5)]
                    else:
                        scenario_name = f"{ht_home}:{ht_away} + Равные удары в створ"; flex_df = score_df[abs(score_df['HST'] - score_df['AST']) <= 2]
                        
                    if len(flex_df) > 0 and (hts > 0 or ats > 0):
                        if hts > ats: flex_df = flex_df[flex_df['HS'] > flex_df['AS']]
                        elif ats > hts: flex_df = flex_df[flex_df['AS'] > flex_df['HS']]
                        
                    if len(flex_df) >= 5: filtered_df = flex_df
                    else:
                        filtered_df = score_df
                        scenario_name = f"{ht_home}:{ht_away} (Только по счету, мало данных)"
                        
                sample_size = len(filtered_df)
                if sample_size >= 50: reliability = "🟢 НАДЕЖНО"
                elif sample_size >= 20: reliability = "🟡 СРЕДНЕ"
                else: reliability = "🔴 НЕНАДЕЖНО"
                
                st.info(f"**Сценарий:** {scenario_name}\n\n**Выборка:** {sample_size} матчей {reliability}")
                
                total_goals = filtered_df['TotalGoals']
                probs = {
                    "ТМ 1.5": (total_goals < 1.5).mean() * 100, "ТБ 1.5": (total_goals > 1.5).mean() * 100,
                    "ТМ 2.5": (total_goals < 2.5).mean() * 100, "ТБ 2.5": (total_goals > 2.5).mean() * 100,
                    "ТМ 3.5": (total_goals < 3.5).mean() * 100, "ТБ 3.5": (total_goals > 3.5).mean() * 100,
                    "П1 (Хозяева)": (filtered_df['FTR'] == 'H').mean() * 100,
                    "Х (Ничья)": (filtered_df['FTR'] == 'D').mean() * 100,
                    "П2 (Гости)": (filtered_df['FTR'] == 'A').mean() * 100,
                    "ОЗ (Да)": ((filtered_df['FTHG'] > 0) & (filtered_df['FTAG'] > 0)).mean() * 100,
                    "ОЗ (Нет)": 100 - ((filtered_df['FTHG'] > 0) & (filtered_df['FTAG'] > 0)).mean() * 100
                }
                
                ht_goals = ht_home + ht_away
                markets = []
                if ht_goals == 0: markets = ["ТМ 1.5", "ТБ 1.5", "ТМ 2.5", "ТБ 2.5", "ОЗ (Да)", "ОЗ (Нет)", "П1 (Хозяева)", "Х (Ничья)", "П2 (Гости)"]
                elif ht_goals == 1: markets = ["ТМ 1.5", "ТБ 1.5", "ТМ 2.5", "ТБ 2.5", "ОЗ (Да)", "ОЗ (Нет)", "П1 (Хозяева)", "Х (Ничья)", "П2 (Гости)"]
                elif ht_goals == 2: markets = ["ТМ 2.5", "ТБ 2.5", "П1 (Хозяева)", "Х (Ничья)", "П2 (Гости)"]
                else: markets = ["ТМ 3.5", "ТБ 3.5", "П1 (Хозяева)", "Х (Ничья)", "П2 (Гости)"]
                
                st.write("---")
                for m in markets:
                    with st.container():
                        c1, c2, c3 = st.columns([2, 1, 1])
                        c1.write(f"**{m}**")
                        c2.write(f"**{probs[m]:.1f}%**")
                        
                        odds_val = st.session_state.get(f"odds_{m}", 1.0)
                        odds = c3.number_input("Кф", min_value=1.0, value=odds_val, key=f"odds_{m}", label_visibility="collapsed")
                        
                        if odds > 1.0:
                            roi = ((probs[m] / 100) * odds - 1) * 100
                            if roi > 0:
                                st.success(f"Валуй: +{roi:.1f}%", icon="✅")
                            else:
                                st.error(f"Валуй: {roi:.1f}%", icon="❌")
                                
                            if st.button("Добавить в ожидание", key=f"add_{m}"):
                                df_pending = load_csv(PENDING_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма'])
                                new_row = {'Дата': datetime.now().strftime("%Y-%m-%d %H:%M"), 'Лига': league_name, 'Матч': match_name, 'Ставка': m, 'Кф': odds, 'Валуй': f"{roi:+.1f}%", 'Сумма': 100}
                                df_pending = pd.concat([df_pending, pd.DataFrame([new_row])], ignore_index=True)
                                df_pending.to_csv(PENDING_FILE, index=False)
                                st.toast(f"Ставка '{m}' добавлена!", icon="🎉")

with tab2:
    st.header("Мой Банк")
    
    df_bank = load_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
    df_pending = load_csv(PENDING_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма'])
    starting_bank = get_starting_bank()
    
    with st.expander("Настройки банка"):
        new_start = st.number_input("Начальный банк", value=starting_bank)
        if st.button("Сохранить банк"):
            save_starting_bank(new_start)
            st.success("Начальный банк обновлен!")
            st.rerun()
    
    total_bets = len(df_bank)
    if total_bets > 0:
        wins = len(df_bank[df_bank['Результат'] == 'Выигрыш'])
        losses = len(df_bank[df_bank['Результат'] == 'Проигрыш'])
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        total_staked = df_bank['Сумма'].sum()
        profit = 0
        for _, row in df_bank.iterrows():
            if row['Результат'] == 'Выигрыш': profit += (row['Сумма'] * row['Кф']) - row['Сумма']
            elif row['Результат'] == 'Проигрыш': profit -= row['Сумма']
        current_bank = starting_bank + profit
        roi = (profit / total_staked * 100) if total_staked > 0 else 0
    else:
        win_rate, total_staked, profit, current_bank, roi = 0, 0, 0, starting_bank, 0
        
    col1, col2 = st.columns(2)
    col1.metric("Текущий банк", f"{current_bank:,.0f} ₽")
    col2.metric("ROI", f"{roi:+.1f}%")
    
    st.write(f"Ставок: **{total_bets}** | Выигрышей: **{wins if total_bets > 0 else 0}** | Проигрышей: **{losses if total_bets > 0 else 0}**")
    st.write(f"Винрейт: **{win_rate:.1f}%** | Оборот: **{total_staked:,.0f} ₽**")
    
    if total_bets > 0:
        balance = [starting_bank]
        cur = starting_bank
        for _, row in df_bank.iterrows():
            if row['Результат'] == 'Выигрыш': cur += (row['Сумма'] * row['Кф']) - row['Сумма']
            elif row['Результат'] == 'Проигрыш': cur -= row['Сумма']
            balance.append(cur)
        fig, ax = plt.subplots(figsize=(8, 3))
        fig.patch.set_facecolor('#0e1117')
        ax.set_facecolor('#0e1117')
        ax.plot(range(len(balance)), balance, marker='o', color="#00E676")
        ax.axhline(y=starting_bank, color="gray", linestyle="--")
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.set_title("Динамика банка", color="white")
        ax.set_ylabel("Баланс (₽)", color="white")
        st.pyplot(fig)
        
    if not df_pending.empty:
        st.subheader("⏳ Ожидают результата")
        for i, row in df_pending.iterrows():
            with st.expander(f"{row['Матч']} | {row['Ставка']} | Кф: {row['Кф']}"):
                st.write(f"Лига: {row['Лига']} | Сумма: {row['Сумма']}₽ | Валуй: {row['Валуй']}")
                res = st.selectbox("Результат", ["Выигрыш", "Проигрыш", "Возврат"], key=f"res_{i}")
                c1, c2 = st.columns(2)
                if c1.button("Готово", key=f"done_{i}", use_container_width=True):
                    df_b = load_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
                    new_row = {'Дата': row['Дата'], 'Лига': row['Лига'], 'Матч': row['Матч'], 'Ставка': row['Ставка'], 'Кф': row['Кф'], 'Валуй': row['Валуй'], 'Сумма': row['Сумма'], 'Результат': res}
                    df_b = pd.concat([df_b, pd.DataFrame([new_row])], ignore_index=True)
                    df_b.to_csv(BANK_FILE, index=False)
                    df_p = df_pending.drop(i)
                    df_p.to_csv(PENDING_FILE, index=False)
                    st.rerun()
                if c2.button("Удалить", key=f"del_{i}", use_container_width=True, type="primary"):
                    df_p = df_pending.drop(i)
                    df_p.to_csv(PENDING_FILE, index=False)
                    st.rerun()
                    
    if not df_bank.empty:
        st.subheader("📜 История ставок")
        st.dataframe(df_bank[['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Сумма', 'Результат']], use_container_width=True)
