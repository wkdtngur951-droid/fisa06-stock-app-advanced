import datetime
from io import BytesIO
import os
import json
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv


FAV_FILE = "favorites.json"  # 파일 이름 정의

# 파일에서 읽어오는 함수
def load_favorites():
    if os.path.exists(FAV_FILE):
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

# 파일에 저장하는 함수
def save_favorites(favorites):
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(list(favorites), f, ensure_ascii=False)

# 환경 변수 로드
load_dotenv()
my_name = os.getenv('MY_NAME', 'User')

# --- 1. 시도별 매핑 데이터 ---
SIDO_COORDS = {
    "서울특별시": [37.5665, 126.9780], "부산광역시": [35.1796, 129.0756],
    "대구광역시": [35.8714, 128.6014], "인천광역시": [37.4563, 126.7052],
    "광주광역시": [35.1595, 126.8526], "대전광역시": [36.3504, 127.3845],
    "울산광역시": [35.5384, 129.3114], "세종특별자치시": [36.4800, 127.2890],
    "경기도": [37.2752, 127.0095], "강원특별자치도": [37.8854, 127.7298],
    "충청북도": [36.6350, 127.4912], "충청남도": [36.6588, 126.6728],
    "전북특별자치도": [35.8205, 127.1086],
    "전라남도": [34.8161, 126.4629], "경상북도": [36.5760, 128.5056],
    "경상남도": [35.2377, 128.6923], "제주특별자치도": [33.4890, 126.4983]
}

NAME_REPLACEMENTS = {
    "전북": "전북특별자치도", "전라북도": "전북특별자치도",
    "강원": "강원특별자치도", "강원도": "강원특별자치도",
    "경기": "경기도", "서울": "서울특별시", "경남": "경상남도",
    "경북": "경상북도", "충남": "충청남도", "충북": "충청북도",
    "전남": "전라남도", "제주": "제주특별자치도"
}

# --- 2. 세션 상태 초기화 ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = load_favorites()
if 'search_input_val' not in st.session_state:
    st.session_state.search_input_val = ""
if 'active_company' not in st.session_state:
    st.session_state.active_company = None

# --- 3. 데이터 로드 함수 ---
@st.cache_data
def get_krx_data():
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        df = pd.read_html(url, header=0, flavor='bs4', encoding='EUC-KR')[0]
        df = df[['회사명', '종목코드', '지역']].copy()
        df['종목코드'] = df['종목코드'].apply(lambda x: f'{x:06}')
        return df
    except Exception as e:
        st.error(f"상장사 명단 로드 실패: {e}")
        return pd.DataFrame()

@st.cache_data
def load_geo():
    with open('sido.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 4. 사이드바 ---
with st.sidebar:
    st.header("📍 즐겨찾기")
    for fav in sorted(list(st.session_state.favorites)):
        c1, c2 = st.columns([0.8, 0.2])
        if c1.button(f"🔍 {fav}", key=f"side_{fav}"):
            st.session_state.search_input_val = fav
            st.session_state.active_company = fav
            st.rerun()
        if c2.button("❌", key=f"del_{fav}"):
            st.session_state.favorites.remove(fav)
            save_favorites(st.session_state.favorites) # 파일 저장 코드 추가
            st.rerun()

# --- 5. 메인 UI ---
st.title("KRX 종목 분석 대시보드")
st.caption(f"{my_name}")

input_comp = st.text_input('회사명을 입력하세요', value=st.session_state.search_input_val)

d2 = datetime.datetime.now()
selected_dates = st.date_input(
    '조회 기간', 
    (datetime.date(d2.year, 1, 1), d2.date()), 
    format="YYYY.MM.DD"
)

col1, col2 = st.columns([0.2, 0.8])
with col1:
    if st.button('데이터 조회', use_container_width=True):
        st.session_state.active_company = input_comp
        st.session_state.search_input_val = input_comp
with col2:
    if input_comp:
        is_f = input_comp in st.session_state.favorites
        if st.button("⭐" if is_f else "☆"):
            if is_f: 
                st.session_state.favorites.remove(input_comp)
            else: 
                st.session_state.favorites.add(input_comp)
            
            save_favorites(st.session_state.favorites) # 파일 저장 코드 추가
            st.rerun()

# --- 6. 결과 렌더링 ---
if st.session_state.active_company:
    target_name = st.session_state.active_company
    df_krx = get_krx_data()
    info = df_krx[df_krx['회사명'] == target_name]
    
    if info.empty:
        st.error(f"'{target_name}' 기업 정보를 찾을 수 없습니다.")
    else:
        info = info.iloc[0]
        code, region_raw = info['종목코드'], str(info['지역'])
        
        try:
            # 날짜 처리
            start_d = selected_dates[0].strftime("%Y-%m-%d")
            end_d = selected_dates[1].strftime("%Y-%m-%d")
            price_df = fdr.DataReader(code, start_d, end_d)

            if price_df.empty:
                st.warning("해당 기간의 주가 데이터가 존재하지 않습니다.")
            else:
                # [차트 영역]
                st.subheader(f"{target_name} ({code}) 차트 분석")
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                   vertical_spacing=0.05, row_heights=[0.7, 0.3])

                fig.add_trace(go.Candlestick(
                    x=price_df.index, open=price_df['Open'], high=price_df['High'],
                    low=price_df['Low'], close=price_df['Close'], name='Price',
                    increasing_line_color='#d62728', decreasing_line_color='#1f77b4'
                ), row=1, col=1)

                fig.add_trace(go.Bar(
                    x=price_df.index, y=price_df['Volume'], name='Volume',
                    marker_color='gray', opacity=0.5
                ), row=2, col=1)

                fig.update_layout(
                    template='plotly_white', xaxis_rangeslider_visible=False,
                    margin=dict(l=10, r=10, t=10, b=10), height=500, showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)

                # [지도 영역]
                st.subheader(f"📍 본사 소재지: {region_raw}")
                
                # 매칭 로직 안전하게 수정
                matched_key = None
                for k, v in NAME_REPLACEMENTS.items():
                    if k in region_raw:
                        matched_key = v
                        break
                
                center = SIDO_COORDS.get(matched_key, [36.5, 127.5])
                zoom = 10 if matched_key else 7
                
                m = folium.Map(location=center, zoom_start=zoom, tiles="cartodbpositron")
                folium.GeoJson(load_geo(), style_function=lambda x: {
                    'fillColor': '#f1f1f1', 'fillOpacity': 0.1, 'color': 'gray', 'weight': 1
                }).add_to(m)
                
                if matched_key:
                    folium.Marker(
                        location=center, 
                        popup=f"<b>{target_name}</b>", 
                        icon=folium.Icon(color='red', icon='university', prefix='fa')
                    ).add_to(m)
                    st.success(f"본사는 {matched_key}에 위치해 있습니다.")
                
                st_folium(m, width=725, height=400, key=f"map_{target_name}")

                # [다운로드 영역]
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    price_df.to_excel(writer, index=True)
                st.download_button(
                    label="📥 엑셀 데이터 저장", 
                    data=output.getvalue(), 
                    file_name=f"{target_name}_주가.xlsx"
                )

        except IndexError:
            st.info("시작 날짜와 종료 날짜를 모두 선택해주세요.")
        except Exception as e:
            st.error(f"데이터 렌더링 중 오류 발생: {e}")