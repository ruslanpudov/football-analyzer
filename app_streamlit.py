import streamlit as st
import pandas as pd
import glob
import json
import base64
import requests
from io import StringIO
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="Tactical Analyzer", page_icon="⚽", layout="centered")

# ==========================================
# КАСТОМНЫЙ CSS
# ==========================================
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .main .block-container {
        animation: fadeIn 0.4s ease-out;
    }
    
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4) !important;
        border: 1px solid #333 !important;
        background: linear-gradient(145deg, #1a1a1a, #121212) !important;
    }
    
    .stButton > button {
        transition: all 0.1s ease-in-out;
        border-radius: 8px !important;
    }
    .stButton > button:active {
        transform: scale(0.96);
    }
    
    button[kind="primary"] {
        color: black !important;
        background-color: #00E676 !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 14px 0 rgba(0, 230, 118, 0.39) !important;
    }
    button[kind="primary"]:hover {
        background-color: #00C853 !important;
        box-shadow: 0 6px 20px 0 rgba(0, 230, 118, 0.5) !important;
    }
    
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #333;
    }
    </style>
""", unsafe_allow_html=True)

# --- GITHUB SETTINGS ---
try:
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)
    GITHUB_REPO = st.secrets.get("GITHUB_REPO", "ruslanpudov/football-analyzer")
except:
    GITHUB_TOKEN = None
    GITHUB_REPO = "ruslanpudov/football-analyzer"

GITHUB_BRANCH = "main"
EXTRAPOLATION_FACTOR = 2.17

BANK_FILE = "bank_history.csv"
PENDING_FILE = "pending_bets.csv"
CONFIG_FILE = "bank_config.json"

league_map = {
    'Англия (АПЛ)': 'E0', 'Испания (Ла Лига)': 'SP1', 'Италия (Серия А)': 'I1',
    'Германия (Бундеслига)': 'D1', 'Франция (Лига 1)': 'F1',
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
                for col in ['HS', 'AS', 'HxG', 'AxG', 'HC', 'AC']:
                    if col not in temp_df.columns: temp_df[col] = 0
                all_dfs.append(temp_df)
        except: pass
    if not all_dfs: return pd.DataFrame()
    df = pd.concat(all_dfs, ignore_index=True)
    df['TotalGoals'] = df['FTHG'] + df['FTAG']
    df['Div'] = df['Div'].astype(str).str.strip()
    return df

df = load_data()

# ==========================================
# 2. GITHUB API
# ==========================================
def gh_read_file(path, default=""):
    if not GITHUB_TOKEN: return default
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            return base64.b64decode(content_b64).decode('utf-8')
        return default
    except: return default

def gh_write_file(path, content, message="Update via Streamlit"):
    if not GITHUB_TOKEN: return False
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        r = requests.get(api_url, headers=headers, timeout=10)
        sha = r.json().get("sha") if r.status_code == 200 else None
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        payload = {"message": message, "content": encoded, "branch": GITHUB_BRANCH}
        if sha: payload["sha"] = sha
        r = requests.put(api_url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201]
    except: return False

def gh_read_csv(path, columns):
    content = gh_read_file(path, "")
    if not content.strip(): return pd.DataFrame(columns=columns)
    try:
        dfc = pd.read_csv(StringIO(content))
        # КОНВЕРТИРУЕМ СУММУ В ЦЕЛЫЕ ЧИСЛА (убираем лишние нули)
        dfc['Сумма'] = pd.to_numeric(dfc['Сумма'], errors='coerce').fillna(0).round(0).astype(int)
        dfc['Кф'] = pd.to_numeric(dfc['Кф'], errors='coerce').fillna(0)
        if 'Валуй' in dfc.columns: dfc['Валуй'] = dfc['Валуй'].astype(str).replace('nan', '-')
        if 'Лига' not in dfc.columns: dfc['Лига'] = 'Неизвестно'
        return dfc
    except: return pd.DataFrame(columns=columns)

def gh_write_csv(path, dfc):
    return gh_write_file(path, dfc.to_csv(index=False))

def get_starting_bank():
    content = gh_read_file(CONFIG_FILE, "")
    if not content.strip(): return 10000.0
    try: return float(json.loads(content).get("starting_bank", 10000.0))
    except: return 10000.0

def save_starting_bank(amount):
    return gh_write_file(CONFIG_FILE, json.dumps({"starting_bank": amount}))

# ==========================================
# 3. ВСПОМОГАТЕЛЬНЫЕ
# ==========================================
def get_prob_color(prob):
    if prob >= 80: return "#00E676"
    elif prob >= 65: return "#81C784"
    elif prob >= 50: return "#FFF59D"
    elif prob >= 35: return "#EF9A9A"
    else: return "#E53935"

def style_history(df_h):
    profits = []
    for _, r in df_h.iterrows():
        if r['Результат'] == 'Выигрыш': p = (r['Сумма'] * r['Кф']) - r['Сумма']
        elif r['Результат'] == 'Проигрыш': p = -r['Сумма']
        else: p = 0
        profits.append(f"{p:+.1f} ₽")
    
    display_df = df_h[['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Сумма', 'Результат']].copy()
    display_df['Прибыль'] = profits

    def highlight_result(s):
        return ['color: #00E676; font-weight: bold' if v == 'Выигрыш' else ('color: #E53935; font-weight: bold' if v == 'Проигрыш' else 'color: #FFF59D; font-weight: bold') for v in s]
        
    def highlight_profit(s):
        res = []
        for v in s:
            try:
                num = float(str(v).replace(' ₽', '').replace('+', ''))
                res.append('color: #00E676; font-weight: bold' if num > 0 else 'color: #E53935; font-weight: bold')
            except: res.append('')
        return res

    return display_df.style.format({
        'Кф': '{:.2f}',
        'Сумма': '{:.0f}'
    }).apply(highlight_result, subset=['Результат']).apply(highlight_profit, subset=['Прибыль'])

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================
st.title("⚽ Tactical Analyzer")

if not GITHUB_TOKEN:
    st.warning("⚠️ GITHUB_TOKEN не найден.")

# 3 ВКЛАДКИ
tab1, tab_profile, tab2 = st.tabs(["Анализ матча", "Профиль команды", "Мой Банк"])

# ==========================================
# ВКЛАДКА 1: АНАЛИЗ МАТЧА
# ==========================================
with tab1:
    with st.expander("Ввод данных за 1-й тайм", expanded=True):
        league_name = st.selectbox("Лига", list(league_map.keys()))
        match_name = st.text_input("Название матча", "")
        
        col_home, col_away = st.columns(2)
        
        with col_home:
            st.markdown("### 🏠 Хозяева")
            ht_home = st.number_input("Голы", 0, 10, 0, key="ht_home")
            hst = st.number_input("Удары в створ", 0, 20, 0, key="hst")
            hts = st.number_input("Общие удары", 0, 40, 0, key="hts")
            hxg = st.number_input("xG", 0.0, 10.0, 0.0, 0.1, key="hxg")
            hc = st.number_input("Угловые", 0, 20, 0, key="hc")
            
        with col_away:
            st.markdown("### ✈️ Гости")
            ht_away = st.number_input("Голы ", 0, 10, 0, key="ht_away")
            ast = st.number_input("Удары в створ ", 0, 20, 0, key="ast")
            ats = st.number_input("Общие удары ", 0, 40, 0, key="ats")
            axg = st.number_input("xG ", 0.0, 10.0, 0.0, 0.1, key="axg")
            ac = st.number_input("Угловые ", 0, 20, 0, key="ac")
            
    if st.button("АНАЛИЗИРОВАТЬ", type="primary", use_container_width=True):
        if df.empty:
            st.error("База данных не загружена.")
        else:
            league_code = league_map[league_name]
            hst_est, ast_est = round(hst*EXTRAPOLATION_FACTOR), round(ast*EXTRAPOLATION_FACTOR)
            hts_est, ats_est = round(hts*EXTRAPOLATION_FACTOR), round(ats*EXTRAPOLATION_FACTOR)
            hxg_est, axg_est = round(hxg*EXTRAPOLATION_FACTOR, 2), round(axg*EXTRAPOLATION_FACTOR, 2)
            hc_est, ac_est = round(hc*EXTRAPOLATION_FACTOR), round(ac*EXTRAPOLATION_FACTOR)
            
            if league_code == 'NICHE':
                top5 = ['E0', 'SP1', 'I1', 'D1', 'F1']
                league_df = df[~df['Div'].isin(top5)].copy()
            else:
                league_df = df[df['Div'] == league_code].copy()
                
            score_df = league_df[(league_df['HTHG'] == ht_home) & (league_df['HTAG'] == ht_away)].copy()
            
            if score_df.empty:
                st.warning(f"Нет матчей со счетом {ht_home}:{ht_away}")
            else:
                scenario_name, filtered_df = "", pd.DataFrame()
                total_corners_1h = hc + ac
                
                if total_corners_1h >= 8 and hst <= 3 and ast <= 3:
                    scenario_name = f"{ht_home}:{ht_away} + Много угловых ({hc}:{ac})"
                    filtered_df = score_df[((score_df['HC'] + score_df['AC']) >= hc_est + ac_est - 3)]
                    
                if filtered_df.empty and (hxg > 0 or axg > 0):
                    xg_df = score_df[score_df['HxG'] > 0]
                    if len(xg_df) > 0:
                        strict_xg = xg_df[(xg_df['HxG'] >= hxg_est - 0.5) & (xg_df['HxG'] <= hxg_est + 0.5) & (xg_df['AxG'] >= axg_est - 0.5) & (xg_df['AxG'] <= axg_est + 0.5)]
                        if len(strict_xg) >= 5:
                            filtered_df, scenario_name = strict_xg, f"{ht_home}:{ht_away} (xG: ~{hxg_est}-{axg_est})"
                            
                if filtered_df.empty:
                    strict_cond = ((score_df['HST'] >= hst_est - 2) & (score_df['HST'] <= hst_est + 2) & (score_df['AST'] >= ast_est - 2) & (score_df['AST'] <= ast_est + 2))
                    if hts > 0 or ats > 0:
                        strict_cond = strict_cond & (score_df['HS'] >= hts_est - 3) & (score_df['HS'] <= hts_est + 3) & (score_df['AS'] >= ats_est - 3) & (score_df['AS'] <= ats_est + 3)
                    strict_df = score_df[strict_cond]
                    if len(strict_df) >= 15:
                        filtered_df, scenario_name = strict_df, f"{ht_home}:{ht_away} (Точный: ~{hst_est}-{ast_est} в створ)"
                        
                if filtered_df.empty:
                    flex_df = pd.DataFrame()
                    if hst > ast:
                        ratio = hst / ast if ast > 0 else 10.0
                        if ratio >= 3.0: scenario_name, flex_df = f"{ht_home}:{ht_away} + Тотальное доминирование хозяев", score_df[(score_df['HST'] >= score_df['AST'] * 3)]
                        elif ratio >= 2.0: scenario_name, flex_df = f"{ht_home}:{ht_away} + Сильное доминирование хозяев", score_df[(score_df['HST'] >= score_df['AST'] * 2) & (score_df['HST'] < score_df['AST'] * 3)]
                        elif ratio >= 1.5: scenario_name, flex_df = f"{ht_home}:{ht_away} + Умеренное доминирование хозяев", score_df[(score_df['HST'] >= score_df['AST'] * 1.5) & (score_df['HST'] < score_df['AST'] * 2)]
                        else: scenario_name, flex_df = f"{ht_home}:{ht_away} + Небольшой перевес хозяев", score_df[(score_df['HST'] > score_df['AST']) & (score_df['HST'] < score_df['AST'] * 1.5)]
                    elif ast > hst:
                        ratio = ast / hst if hst > 0 else 10.0
                        if ratio >= 3.0: scenario_name, flex_df = f"{ht_home}:{ht_away} + Тотальное доминирование гостей", score_df[(score_df['AST'] >= score_df['HST'] * 3)]
                        elif ratio >= 2.0: scenario_name, flex_df = f"{ht_home}:{ht_away} + Сильное доминирование гостей", score_df[(score_df['AST'] >= score_df['HST'] * 2) & (score_df['AST'] < score_df['HST'] * 3)]
                        elif ratio >= 1.5: scenario_name, flex_df = f"{ht_home}:{ht_away} + Умеренное доминирование гостей", score_df[(score_df['AST'] >= score_df['HST'] * 1.5) & (score_df['AST'] < score_df['HST'] * 2)]
                        else: scenario_name, flex_df = f"{ht_home}:{ht_away} + Небольшой перевес гостей", score_df[(score_df['AST'] > score_df['HST']) & (score_df['AST'] < score_df['HST'] * 1.5)]
                    else:
                        scenario_name, flex_df = f"{ht_home}:{ht_away} + Равные удары", score_df[abs(score_df['HST'] - score_df['AST']) <= 2]
                        
                    if len(flex_df) > 0 and (hts > 0 or ats > 0):
                        if hts > ats: flex_df = flex_df[flex_df['HS'] > flex_df['AS']]
                        elif ats > hts: flex_df = flex_df[flex_df['AS'] > flex_df['HS']]
                    if len(flex_df) >= 5: filtered_df = flex_df
                    else:
                        filtered_df = score_df
                        scenario_name = f"{ht_home}:{ht_away} (Только по счету, мало данных)"
                        
                sample_size = len(filtered_df)
                reliability = "🟢 НАДЕЖНО" if sample_size >= 50 else ("🟡 СРЕДНЕ" if sample_size >= 20 else "🔴 НЕНАДЕЖНО")
                
                st.info(f"**Сценарий:** {scenario_name}\n\n**Выборка:** {sample_size} матчей {reliability}")
                
                tg = filtered_df['TotalGoals']
                probs = {
                    "ТМ 1.5": (tg < 1.5).mean()*100, "ТБ 1.5": (tg > 1.5).mean()*100,
                    "ТМ 2.5": (tg < 2.5).mean()*100, "ТБ 2.5": (tg > 2.5).mean()*100,
                    "ТМ 3.5": (tg < 3.5).mean()*100, "ТБ 3.5": (tg > 3.5).mean()*100,
                    "П1 (Хозяева)": (filtered_df['FTR'] == 'H').mean()*100,
                    "Х (Ничья)": (filtered_df['FTR'] == 'D').mean()*100,
                    "П2 (Гости)": (filtered_df['FTR'] == 'A').mean()*100,
                    "ОЗ (Да)": ((filtered_df['FTHG'] > 0) & (filtered_df['FTAG'] > 0)).mean()*100,
                    "ОЗ (Нет)": 100 - ((filtered_df['FTHG'] > 0) & (filtered_df['FTAG'] > 0)).mean()*100
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
                        
                        if probs[m] > 75 and probs[m] == max([probs[x] for x in markets]):
                            c1.markdown(f"**{m}** 🔥 <span style='color:#FFF59D; font-size:12px;'>ТОП</span>", unsafe_allow_html=True)
                        else:
                            c1.write(f"**{m}**")
                            
                        c2.markdown(f"<span style='color:{get_prob_color(probs[m])}; font-size: 18px; font-weight: bold;'>{probs[m]:.1f}%</span>", unsafe_allow_html=True)
                        
                        odds = c3.number_input("Кф", min_value=1.0, value=st.session_state.get(f"odds_{m}", 1.0), key=f"odds_{m}", label_visibility="collapsed")
                        
                        if odds > 1.0:
                            roi = ((probs[m]/100) * odds - 1) * 100
                            if roi > 0: st.success(f"Валуй: +{roi:.1f}%", icon="✅")
                            else: st.error(f"Валуй: {roi:.1f}%", icon="❌")
                            
                            if st.button(f"➕ Добавить: {m}", key=f"add_{m}", use_container_width=True):
                                df_pending = gh_read_csv(PENDING_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма'])
                                new_row = {'Дата': datetime.now().strftime("%Y-%m-%d %H:%M"), 'Лига': league_name, 'Матч': match_name, 'Ставка': m, 'Кф': odds, 'Валуй': f"{roi:+.1f}%", 'Сумма': 100}
                                df_pending = pd.concat([df_pending, pd.DataFrame([new_row])], ignore_index=True)
                                if gh_write_csv(PENDING_FILE, df_pending):
                                    st.toast(f"Ставка '{m}' сохранена!", icon="🎉")
                                    st.balloons()
                                    st.rerun()

# ==========================================
# ВКЛАДКА 2: ПРОФИЛЬ КОМАНДЫ
# ==========================================
with tab_profile:
    st.header("Профиль команды")
    
    if df.empty:
        st.warning("База данных не загружена.")
    else:
        home_teams = df['HomeTeam'].dropna().astype(str).unique()
        away_teams = df['AwayTeam'].dropna().astype(str).unique()
        all_teams = sorted(list(set(home_teams) | set(away_teams)))
        
        selected_team = st.selectbox("Выбери команду", all_teams)
        
        if selected_team:
            team_matches = df[(df['HomeTeam'] == selected_team) | (df['AwayTeam'] == selected_team)].copy()
            
            if team_matches.empty:
                st.info("Нет данных по этой команде.")
            else:
                last_10 = team_matches.tail(10).copy()
                
                total_goals_for, total_goals_against = 0, 0
                total_xg_for, total_xg_against = 0, 0
                total_shots_for, total_shots_against = 0, 0
                total_st_for, total_st_against = 0, 0
                wins, draws, losses = 0, 0, 0
                
                display_data = []
                
                for _, row in last_10.iterrows():
                    is_home = row['HomeTeam'] == selected_team
                    opp = row['AwayTeam'] if is_home else row['HomeTeam']
                    
                    goals_for = int(row['FTHG']) if is_home else int(row['FTAG'])
                    goals_against = int(row['FTAG']) if is_home else int(row['FTHG'])
                    xg_for = row['HxG'] if is_home else row['AxG']
                    xg_against = row['AxG'] if is_home else row['HxG']
                    shots_for = int(row['HS']) if is_home else int(row['AS'])
                    shots_against = int(row['AS']) if is_home else int(row['HS'])
                    st_for = int(row['HST']) if is_home else int(row['AST'])
                    st_against = int(row['AST']) if is_home else int(row['HST'])
                    
                    if pd.isna(xg_for): xg_for = 0
                    if pd.isna(xg_against): xg_against = 0
                    
                    total_goals_for += goals_for
                    total_goals_against += goals_against
                    total_xg_for += xg_for
                    total_xg_against += xg_against
                    total_shots_for += shots_for
                    total_shots_against += shots_against
                    total_st_for += st_for
                    total_st_against += st_against
                    
                    if goals_for > goals_against: wins += 1
                    elif goals_for == goals_against: draws += 1
                    else: losses += 1
                    
                    res_color = "#00E676" if goals_for > goals_against else ("#E53935" if goals_for < goals_against else "#FFF59D")
                    res_text = "В" if goals_for > goals_against else ("П" if goals_for < goals_against else "Н")
                    
                    display_data.append({
                        'Соперник': opp,
                        'Счет': f"{goals_for} - {goals_against}",
                        'Рез': res_text,
                        'xG (За)': float(f"{xg_for:.2f}"),
                        'xG (Пр)': float(f"{xg_against:.2f}"),
                        'Удары (За)': shots_for,
                        'Удары (Пр)': shots_against,
                        'В створ (За)': st_for,
                        'В створ (Пр)': st_against,
                        'Цвет': res_color
                    })
                
                display_df = pd.DataFrame(display_data)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Форма (В-Н-П)", f"{wins}-{draws}-{losses}", f"За последние {len(last_10)}")
                col2.metric("Ср. xG (За)", f"{total_xg_for / len(last_10):.2f}", f"Ср. Удары: {total_shots_for / len(last_10):.1f}")
                col3.metric("Ср. xG (Пр)", f"{total_xg_against / len(last_10):.2f}", f"Ср. Удары: {total_shots_against / len(last_10):.1f}")
                
                st.write("---")
                st.subheader("Последние матчи")
                
                styled_df = display_df[['Соперник', 'Счет', 'Рез', 'xG (За)', 'xG (Пр)', 'Удары (За)', 'Удары (Пр)', 'В створ (За)', 'В створ (Пр)']].copy()
                def highlight_res_col(s):
                    return [f'color: {display_df.iloc[i]["Цвет"]}; font-weight: bold' for i in range(len(s))]
                
                styled_df = styled_df.style.format({
                    'xG (За)': '{:.2f}',
                    'xG (Пр)': '{:.2f}',
                    'Удары (За)': '{:.0f}',
                    'Удары (Пр)': '{:.0f}',
                    'В створ (За)': '{:.0f}',
                    'В створ (Пр)': '{:.0f}'
                }).apply(highlight_res_col, subset=['Рез'])
                
                st.dataframe(styled_df, use_container_width=True, height=400)

# ==========================================
# ВКЛАДКА 3: МОЙ БАНК
# ==========================================
with tab2:
    st.header("Мой Банк")
    
    df_bank = gh_read_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
    df_pending = gh_read_csv(PENDING_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма'])
    starting_bank = get_starting_bank()
    
    if len(df_bank) > 0:
        df_bank['Лига'] = df_bank['Лига'].fillna('Не указана')
        df_bank.loc[df_bank['Лига'] == 'Неизвестно', 'Лига'] = 'Не указана'
        
        league_stats = df_bank.groupby('Лига').apply(lambda x: pd.Series({
            'Profit': sum((r['Сумма'] * r['Кф']) - r['Сумма'] if r['Результат'] == 'Выигрыш' else (-r['Сумма'] if r['Результат'] == 'Проигрыш' else 0) for _, r in x.iterrows()),
            'Staked': x['Сумма'].sum(),
        }), include_groups=False)
        league_stats = league_stats[league_stats['Staked'] > 0]
        if not league_stats.empty:
            league_stats['ROI'] = (league_stats['Profit'] / league_stats['Staked'] * 100).round(1)
            league_stats = league_stats.sort_values('ROI', ascending=False)
            league_str = " | ".join([f"{idx}: {row['ROI']:+.0f}%" for idx, row in league_stats.head(3).iterrows()])
        else: league_str = "Нет данных"

        market_stats = df_bank.groupby('Ставка').apply(lambda x: pd.Series({
            'Profit': sum((r['Сумма'] * r['Кф']) - r['Сумма'] if r['Результат'] == 'Выигрыш' else (-r['Сумма'] if r['Результат'] == 'Проигрыш' else 0) for _, r in x.iterrows()),
            'Staked': x['Сумма'].sum(),
        }), include_groups=False)
        market_stats = market_stats[market_stats['Staked'] > 0]
        if not market_stats.empty:
            market_stats['ROI'] = (market_stats['Profit'] / market_stats['Staked'] * 100).round(1)
            market_stats = market_stats.sort_values('ROI', ascending=False)
            market_str = " | ".join([f"{idx}: {row['ROI']:+.0f}%" for idx, row in market_stats.head(3).iterrows()])
        else: market_str = "Нет данных"
        
        with st.expander("📊 Аналитика по лигам и рынкам (ROI)"):
            st.markdown(f"🏆 **Лучшие лиги:** {league_str}")
            st.markdown(f"🎯 **Лучшие рынки:** {market_str}")
    
    with st.expander("⚙️ Настройки банка"):
        new_start = st.number_input("Начальный банк", value=starting_bank)
        if st.button("Сохранить банк"):
            if save_starting_bank(new_start):
                st.success("Банк сохранен!")
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
        
        col1, col2 = st.columns(2)
        col1.metric("Текущий банк", f"{current_bank:,.0f} ₽", f"{profit:+.0f} ₽")
        
        roi_color = "#00E676" if roi >= 0 else "#E53935"
        col2.markdown(f"<p style='font-size: 14px; color: #AAAAAA; margin-bottom: -5px;'>ROI</p>", unsafe_allow_html=True)
        col2.markdown(f"<p style='font-size: 36px; font-weight: bold; margin-top: 0px; color: {roi_color};'>{roi:+.1f}%</p>", unsafe_allow_html=True)
        
        st.write(f"Ставок: **{total_bets}** | Выигрышей: **{wins}** | Проигрышей: **{losses}**")
        st.progress(min(win_rate / 100.0, 1.0), text=f"Винрейт: {win_rate:.1f}%")
    
    if total_bets > 0:
        balance, cur = [starting_bank], starting_bank
        for _, row in df_bank.iterrows():
            if row['Результат'] == 'Выигрыш': cur += (row['Сумма'] * row['Кф']) - row['Сумма']
            elif row['Результат'] == 'Проигрыш': cur -= row['Сумма']
            balance.append(cur)
            
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(balance))), y=balance, mode='lines+markers', 
                                 name='Баланс', line=dict(color='#00E676', width=3), marker=dict(size=6)))
        fig.add_hline(y=starting_bank, line_dash="dash", line_color="gray", annotation_text="Начальный банк")
        fig.update_layout(title="Динамика банка", xaxis_title="Номер ставки", yaxis_title="Баланс (₽)",
                          template="plotly_dark", height=300, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
    if not df_pending.empty:
        st.subheader("⏳ Ожидают результата")
        for i, row in df_pending.iterrows():
            with st.container(border=True):
                st.markdown(f"### {row['Матч']}")
                st.caption(f"{row['Лига']} | {row['Ставка']} | Кф: **{row['Кф']}** | Валуй: **{row['Валуй']}** | Сумма: **{row['Сумма']}₽**")
                
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("✅", key=f"win_{i}", help="Выигрыш", use_container_width=True):
                    df_b = gh_read_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
                    new_row = {'Дата': row['Дата'], 'Лига': row['Лига'], 'Матч': row['Матч'], 'Ставка': row['Ставка'], 'Кф': row['Кф'], 'Валуй': row['Валуй'], 'Сумма': row['Сумма'], 'Результат': 'Выигрыш'}
                    df_b = pd.concat([df_b, pd.DataFrame([new_row])], ignore_index=True)
                    df_p = df_pending.drop(i)
                    gh_write_csv(BANK_FILE, df_b); gh_write_csv(PENDING_FILE, df_p)
                    st.toast("💰 Касса!", icon="🤑")
                    st.balloons()
                    st.rerun()
                if c2.button("❌", key=f"loss_{i}", help="Проигрыш", use_container_width=True):
                    df_b = gh_read_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
                    new_row = {'Дата': row['Дата'], 'Лига': row['Лига'], 'Матч': row['Матч'], 'Ставка': row['Ставка'], 'Кф': row['Кф'], 'Валуй': row['Валуй'], 'Сумма': row['Сумма'], 'Результат': 'Проигрыш'}
                    df_b = pd.concat([df_b, pd.DataFrame([new_row])], ignore_index=True)
                    df_p = df_pending.drop(i)
                    gh_write_csv(BANK_FILE, df_b); gh_write_csv(PENDING_FILE, df_p)
                    st.toast("😔 Мимо...", icon="💸")
                    st.rerun()
                if c3.button("↩️", key=f"ret_{i}", help="Возврат", use_container_width=True):
                    df_b = gh_read_csv(BANK_FILE, ['Дата', 'Лига', 'Матч', 'Ставка', 'Кф', 'Валуй', 'Сумма', 'Результат'])
                    new_row = {'Дата': row['Дата'], 'Лига': row['Лига'], 'Матч': row['Матч'], 'Ставка': row['Ставка'], 'Кф': row['Кф'], 'Валуй': row['Валуй'], 'Сумма': row['Сумма'], 'Результат': 'Возврат'}
                    df_b = pd.concat([df_b, pd.DataFrame([new_row])], ignore_index=True)
                    df_p = df_pending.drop(i)
                    gh_write_csv(BANK_FILE, df_b); gh_write_csv(PENDING_FILE, df_p)
                    st.rerun()
                if c4.button("🗑️", key=f"del_{i}", help="Удалить", use_container_width=True):
                    df_p = df_pending.drop(i)
                    gh_write_csv(PENDING_FILE, df_p)
                    st.rerun()
                    
    if not df_bank.empty:
        st.subheader("📜 История ставок")
        
        csv_data = df_bank.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Скачать историю (CSV)", data=csv_data, file_name="my_bets.csv", mime="text/csv")
        
        st.dataframe(style_history(df_bank), use_container_width=True, height=300)
        
        with st.expander("⚙️ Управление историей"):
            for i, row in df_bank.iterrows():
                cols = st.columns([3, 1, 1])
                cols[0].write(f"{row['Дата']} | {row['Матч']} | {row['Ставка']} ({row['Результат']})")
                if cols[1].button("✏️", key=f"edit_hist_{i}", help="Редактировать", use_container_width=True):
                    st.session_state[f"editing_{i}"] = True
                if cols[2].button("🗑️", key=f"del_hist_{i}", help="Удалить", use_container_width=True):
                    df_b = df_bank.drop(i)
                    gh_write_csv(BANK_FILE, df_b)
                    st.rerun()
                    
                if st.session_state.get(f"editing_{i}", False):
                    with st.form(f"form_{i}"):
                        new_match = st.text_input("Матч", row['Матч'])
                        new_stake = st.text_input("Ставка", row['Ставка'])
                        new_odds = st.number_input("Кф", value=float(row['Кф']))
                        new_res = st.selectbox("Результат", ["Выигрыш", "Проигрыш", "Возврат"], index=["Выигрыш", "Проигрыш", "Возврат"].index(row['Результат']))
                        if st.form_submit_button("Сохранить"):
                            df_bank.at[i, 'Матч'] = new_match
                            df_bank.at[i, 'Ставка'] = new_stake
                            df_bank.at[i, 'Кф'] = new_odds
                            df_bank.at[i, 'Результат'] = new_res
                            gh_write_csv(BANK_FILE, df_bank)
                            st.session_state[f"editing_{i}"] = False
                            st.rerun()
