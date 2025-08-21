import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64

# --- 이미지 파일을 Base64로 인코딩하는 함수 ---
def get_image_as_base64(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

# --- 0. 이스터에그 캐릭터 준비 ---
# 이미지 파일이 실제로 존재하는 경로를 확인해야 합니다.
try:
    image_path = "대구경찰마스코트.png"
    image_base64 = get_image_as_base64(image_path)
    
    # CSS 스타일: 오른쪽 상단 고정, 크기 조정, 애니메이션 수정
    st.markdown(f"""
    <style>
    /* 회전 애니메이션 정의 */
    @keyframes spin {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}

    /* 투명도를 70%로 바꾸는 애니메이션 정의 */
    @keyframes reduceOpacity {{
        to {{ opacity: 0.7; }}
    }}

    /* 캐릭터 기본 스타일 (오른쪽 상단 고정) */
    .easter-egg-character {{
        position: fixed;
        top: 90px;
        right: 100px;
        width: 160px;
        height: 160px;
        background-image: url("data:image/png;base64,{image_base64}");
        background-size: contain;
        background-repeat: no-repeat;
        z-index: 9999;
        opacity: 0.9; 
        pointer-events: none; /* 클릭 방지 */

        /* - spin 애니메이션: 3초에 한 바퀴, 총 7번 반복 (총 21초)
        - reduceOpacity 애니메이션: 1초 동안 투명도를 0.7로 변경, 21초 뒤에 시작
        - forwards: 애니메이션이 끝나면 마지막 상태(투명도 0.7)를 유지
        */
        animation: spin 3s linear 7, reduceOpacity 1s ease-out 21s forwards;
    }}
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="easter-egg-character"></div>', unsafe_allow_html=True)

except FileNotFoundError:
    st.warning("경찰 마스코트 이미지 파일('대구경찰마스코트.png')을 찾을 수 없습니다.")


# --- 1. 페이지 설정 및 데이터 로딩 ---

st.set_page_config(layout="wide", page_title="대구 범죄 분석 대시보드")

# --- 1.1. 지도 및 범죄 데이터 로딩 ---
@st.cache_data
def load_data():
    # CSV와 GeoJSON 파일을 로드합니다.
    try:
        crime_data = pd.read_csv("daegu_crime_data.csv").fillna(0)
        crime_data = crime_data[crime_data['행정동'] != '소계']
        daegu_map = gpd.read_file("daegu_map.geojson")

        # GeoDataFrame과 범죄 데이터를 병합합니다.
        if 'adm_nm' in daegu_map.columns:
            daegu_map['행정동_키'] = daegu_map['adm_nm'].str.split().str[-1]
            merged_data = daegu_map.merge(crime_data, left_on='행정동_키', right_on='행정동', how='inner')
            return merged_data
        else:
            st.error("지도 데이터에서 'adm_nm' 컬럼을 찾을 수 없습니다.")
            return None
    except FileNotFoundError as e:
        st.error(f"데이터 파일 로딩 오류: {e}. 'daegu_crime_data.csv' 또는 'daegu_map.geojson' 파일이 있는지 확인해주세요.")
        return None

# --- 1.2. 범죄율 증감 데이터 로딩 ---
@st.cache_data
def load_trend_data():
    try:
        # '범죄율 증감.xlsx' 파일을 로드합니다.
        trend_df = pd.read_excel("범죄율 증감.xlsx")
        trend_df = trend_df.rename(columns={trend_df.columns[0]: '분기'})
        return trend_df
    except FileNotFoundError as e:
        st.error(f"데이터 파일 로딩 오류: {e}. '범죄율 증감.xlsx' 파일이 있는지 확인해주세요.")
        return None


gdf = load_data()
trend_df = load_trend_data()


# --- 2. 변수 설정 ---

# 위험 요인과 안전 요인으로 사용될 컬럼 목록 정의
risk_factors = ["유흥업소 수", "초등학교 수", "중,고등학교 수", "요리 주점", 
                "등록인구", "여성비율", "외국인비율"]
safety_factors = ["치안기관", "어린이용 CCTV 수", "안전비상벨 수", "기타 CCTV 수", 
                  "시설물 CCTV 수", "가로등 수", "보안등 수", "생활방범 CCTV 수"]

# --- 2.1. 초기 가중치 설정 ---
initial_risk_weights = {
    "유흥업소 수": 0.05, "초등학교 수": 0.04, "중,고등학교 수": 0.03,
    "요리 주점": 0.02, "등록인구": 0.50, "여성비율": 0.10, "외국인비율": 0.05
}
initial_safety_weights = {
    "치안기관": 0.25, "어린이용 CCTV 수": 0.20, "안전비상벨 수": 0.20,
    "기타 CCTV 수": 0.05, "시설물 CCTV 수": 0.10, "가로등 수": 0.06, 
    "보안등 수": 0.06, "생활방범 CCTV 수": 0.40
}

# --- 3. 메인 타이틀 ---

st.title("대구광역시 범죄 취약장소 식별 및 위험도/안전도 분석")
st.markdown("---")

# --- 4. 탭 구성 ---

tab1, tab2, tab3, tab4, tab_overview, tab_corr = st.tabs(["순위험도 분석", "개별 항목 시각화", "위험지역 분석", "안전지역 분석", "# 분석 개요", "참고(인구수와 범죄발생수)"])


if gdf is not None and not gdf.empty:

    # ========================= 탭 1: 순위험도 분석 =========================
    with tab1:
        col_sidebar, col_main = st.columns([0.25, 0.75])
        
        with col_sidebar:
            st.header("가중치 조절")
            st.info("순 위험도 = Σ(위험도 수치 * 가중치) - Σ(안전도 수치 * 가중치)")
            
            if 'risk_weights' not in st.session_state:
                st.session_state.risk_weights = initial_risk_weights
            if 'safety_weights' not in st.session_state:
                st.session_state.safety_weights = initial_safety_weights

            with st.expander("🔴 위험 요소 가중치", expanded=True):
                for factor in risk_factors:
                    st.session_state.risk_weights[factor] = st.slider(
                        factor, 0.0, 0.5, 
                        st.session_state.risk_weights.get(factor, 0.1), 
                        0.01, key=f"risk_{factor}"
                    )
            
            with st.expander("🔵 안전 요소 가중치", expanded=True):
                for factor in safety_factors:
                    st.session_state.safety_weights[factor] = st.slider(
                        factor, 0.0, 0.5, 
                        st.session_state.safety_weights.get(factor, 0.1), 
                        0.01, key=f"safety_{factor}"
                    )

        with col_main:
            st.subheader("순위험도 대시보드")
            
            total_risk_weight = sum(st.session_state.risk_weights.values())
            total_safety_weight = sum(st.session_state.safety_weights.values())
            
            norm_risk_weights = {k: v / total_risk_weight if total_risk_weight > 0 else 0 
                                 for k, v in st.session_state.risk_weights.items()}
            norm_safety_weights = {k: v / total_safety_weight if total_safety_weight > 0 else 0 
                                   for k, v in st.session_state.safety_weights.items()}
            
            gdf['총위험도'] = sum(gdf[factor].fillna(0) * weight for factor, weight in norm_risk_weights.items())
            gdf['총안전도'] = sum(gdf[factor].fillna(0) * weight for factor, weight in norm_safety_weights.items())
            gdf['순위험도'] = gdf['총위험도'] - gdf['총안전도']

            map_col, data_col = st.columns([0.6, 0.4])

            with map_col:
                fig = px.choropleth_mapbox(
                    gdf, geojson=gdf.geometry, locations=gdf.index, color="순위험도",
                    center={"lat": 35.8714, "lon": 128.6014}, mapbox_style="carto-positron", zoom=10,
                    opacity=0.6, color_continuous_scale="Bluered", labels={'순위험도': '순위험도 점수'},
                    hover_name="행정동", hover_data={'총위험도': ':.3f', '총안전도': ':.3f', '행정동': False}
                )
                fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig, use_container_width=True)

            with data_col:
                st.subheader("순위험도 순위")
                
                sort_enabled = st.checkbox("순위험도 높은 순으로 정렬")
                display_df = gdf[['행정동', '순위험도', '총위험도', '총안전도']]
                
                if sort_enabled:
                    display_df = display_df.sort_values(by='순위험도', ascending=False)
                
                st.dataframe(display_df.style.format({
                    '순위험도': '{:.3f}', '총위험도': '{:.3f}', '총안전도': '{:.3f}'
                }), use_container_width=True)
            
            st.markdown("---")
            st.subheader("순위험도-범죄발생수 상관관계 분석")
            
            correlation = gdf['순위험도'].corr(gdf['범죄발생수(유동인구기준)'])
            
            corr_col, plot_col = st.columns([0.3, 0.7])
            
            with corr_col:
                st.metric("상관계수 (Pearson)", f"{correlation:.3f}")
                st.info("""
                **상관계수**
                - **1에 가까울수록**: 강한 양의 관계
                - **-1에 가까울수록**: 강한 음의 관계
                - **0에 가까울수록**: 관계 거의 없음
                """)

            with plot_col:
                scatter_fig = px.scatter(
                    gdf, x='순위험도', y='범죄발생수(유동인구기준)', trendline='ols',
                    hover_name='행정동',
                    labels={'순위험도': '계산된 순위험도 점수', 
                            '범죄발생수(유동인구기준)': '범죄발생수 (유동인구 기준)'},
                    title='순위험도와 범죄발생수의 관계'
                )
                scatter_fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(scatter_fig, use_container_width=True)

    # ========================= 탭 2: 개별 항목 시각화 =========================
    with tab2:
        col_sidebar, col_main = st.columns([0.25, 0.75])
        
        with col_sidebar:
            st.header("데이터 선택")
            st.info("요소를 선택하세요.")
            selectable_columns = safety_factors + risk_factors
            selected_column = st.selectbox(
                '표시할 데이터 항목:',
                options=selectable_columns,
                key="individual_selection"
            )
        
        with col_main:
            st.subheader(f"{selected_column} 데이터 시각화")
            gdf[selected_column] = gdf[selected_column].fillna(0)

            if selected_column in safety_factors:
                color_scale = px.colors.sequential.Blues
                legend_title = "안전 점수"
            else:
                color_scale = px.colors.sequential.Reds
                legend_title = "위험 점수"
            
            map_col, data_col = st.columns([0.6, 0.4])

            with map_col:
                fig = px.choropleth_mapbox(
                    gdf, geojson=gdf.geometry, locations=gdf.index, color=selected_column,
                    center={"lat": 35.8714, "lon": 128.6014}, mapbox_style="carto-positron", zoom=10,
                    opacity=0.6, color_continuous_scale=color_scale, labels={selected_column: legend_title},
                    hover_name="행정동", hover_data={selected_column: ':.3f', '행정동': False}
                )
                fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
                st.plotly_chart(fig, use_container_width=True)

            with data_col:
                st.subheader(f"{selected_column} 점수 순위")
                display_df = gdf[['행정동', selected_column]].sort_values(by=selected_column, ascending=False)
                st.dataframe(
                    display_df, use_container_width=True,
                    column_config={
                        selected_column: st.column_config.ProgressColumn(
                            f"{selected_column}", format="%.2f",
                            min_value=float(gdf[selected_column].min()), 
                            max_value=float(gdf[selected_column].max()),
                        ),
                    }
                )

    # ========================= 탭 3: 위험지역 분석 =========================
    with tab3:
        st.header("위험지역 6곳의 공통 패턴 분석")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("극도의 인구 과밀", "2.69배")
            st.markdown("<p style='color:red; font-size: 0.875rem;'>▲ 평균 대비</p>", unsafe_allow_html=True)
        with col2:
            st.metric("외국인 집중지역", "2.24배")
            st.markdown("<p style='color:red; font-size: 0.875rem;'>▲ 평균 대비</p>", unsafe_allow_html=True)
        with col3:
            st.metric("치안기관 절대부족", "16%")
            st.markdown("<p style='color:red; font-size: 0.875rem;'>▼ 평균 대비</p>", unsafe_allow_html=True)
        with col4:
            st.metric("CCTV 인프라 붕괴", "24%")
            st.markdown("<p style='color:red; font-size: 0.875rem;'>▼ 평균 대비</p>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.subheader("전체 평균 대비 비율")
            comparison_df = pd.DataFrame({
                '항목': ['등록인구', '외국인비율', '여성비율', '유흥업소수', 
                         '치안기관', '생활방범CCTV', '어린이CCTV', '시설물CCTV', '안전비상벨'],
                '비율': [2.69, 2.24, 0.90, 0.23, 0.16, 0.24, 0.30, 0.08, 0.55],
                '유형': ['위험요소', '위험요소', '위험요소', '위험요소', 
                         '안전요소', '안전요소', '안전요소', '안전요소', '안전요소']
            })
            
            fig1 = px.bar(
                comparison_df, x='비율', y='항목', color='유형', orientation='h',
                labels={'비율': '전체 평균 대비 비율', '항목': '항목'},
                color_discrete_map={
                    '위험요소': '#ef4444',
                    '안전요소': '#3b82f6',
                    '중성요소': '#64748b'
                }
            )
            fig1.update_layout(height=400)
            st.plotly_chart(fig1, use_container_width=True)
        
        with chart_col2:
            st.subheader("각 지역별 주요 지표 비교")
            individual_df = pd.DataFrame({
                '지역': ['진천동', '신당동', '안심1동', '무태조야동', '월성1동', '관문동'],
                '등록인구': [10.0, 6.74, 7.94, 5.29, 7.71, 8.24],
                '치안기관': [0.37, 0.20, 0.0, 0.17, 0.0, 0.25],
                'CCTV': [0.11, 0.06, 0.25, 0.04, 0.83, 0.13],
                '외국인비율': [0.32, 10.0, 0.33, 4.83, 0.07, 4.42]
            })
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=individual_df['지역'], y=individual_df['등록인구'], 
                                      mode='lines+markers', name='등록인구', 
                                      line=dict(color='#ef4444', width=3)))
            fig2.add_trace(go.Scatter(x=individual_df['지역'], y=individual_df['치안기관'], 
                                      mode='lines+markers', name='치안기관', 
                                      line=dict(color='#3b82f6', width=3)))
            fig2.add_trace(go.Scatter(x=individual_df['지역'], y=individual_df['CCTV'], 
                                      mode='lines+markers', name='CCTV', 
                                      line=dict(color='#10b981', width=3)))
            
            fig2.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        st.subheader("위험도가 높은 상위 6개 지역의 양상")
        
        pattern_col1, pattern_col2, pattern_col3 = st.columns(3)
        
        with pattern_col1:
            st.error("**극도의 인구 과밀**")
            st.write("평균의 **2.69배** 높은 인구밀도")
            st.caption("사람이 몰릴수록 범죄 기회 증가")
            st.markdown("---")
            
            st.error("**외국인 집중지역**")
            st.write("평균의 **2.24배** 높은 외국인 비율")
            st.caption("언어장벽, 문화차이로 치안 사각지대")
        
        with pattern_col2:
            st.info("**치안기관 절대부족**")
            st.write("평균의 **16%** 수준")
            st.caption("즉시 대응할 경찰력 부재")
            st.markdown("---")
            
            st.info("**CCTV 인프라 붕괴**")
            st.write("평균의 **24%** 수준")
            st.caption("범죄 예방·수사 도구 부족")
        
        with pattern_col3:
            st.info("**비상벨 부족**")
            st.write("평균의 **55%** 수준")
            st.caption("긴급상황 대응체계 미흡")
            st.markdown("---")
            
            st.warning("**유흥업소는 적음**")
            st.write("평균의 **23%** 수준")
            st.caption("일반적 편견과 다른 현실")
        
        st.markdown("---")
        st.subheader("동별 상세 분석")
        
        st.markdown("""
        <style>
        .card { padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between; }
        .danger-card { background: linear-gradient(135deg, #fecaca, #f87171); border-left: 4px solid #dc2626; }
        .warning-card { background: linear-gradient(135deg, #fed7aa, #fdba74); border-left: 4px solid #ea580c; }
        .info-card { background: linear-gradient(135deg, #dbeafe, #bfdbfe); border-left: 4px solid #2563eb; }
        .success-card { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #059669; }
        .purple-card { background: linear-gradient(135deg, #e9d5ff, #d8b4fe); border-left: 4px solid #7c3aed; }
        .yellow-card { background: linear-gradient(135deg, #fef3c7, #fed7aa); border-left: 4px solid #ca8a04; }
        .card-title { font-size: 1.2rem; font-weight: bold; margin-bottom: 0.5rem; color: #1f2937; }
        .card-subtitle { font-size: 0.9rem; margin-top: 0.5rem; background: rgba(255,255,255,0.8); padding: 0.5rem; border-radius: 0.25rem; font-weight: bold; }
        .stat-item { margin-bottom: 0.25rem; }
        </style>
        """, unsafe_allow_html=True)
        
        area_col1, area_col2, area_col3 = st.columns(3)
        
        with area_col1:
            st.markdown("""
            <div class="card danger-card">
                <div>
                    <div class="card-title">진천동 (1위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 10.0 (3.5배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.37 (0.5배 낮음)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 0.11 (0.1배 낮음)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 9.08</div>
                </div>
                <div class="card-subtitle">극도의 인구과밀에 비해 안전시설 절대부족</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card yellow-card">
                <div>
                    <div class="card-title">월성1동 (4위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 7.71 (2.7배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.00 (완전공백)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 0.82 (0.9배)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 6.96</div>
                </div>
                <div class="card-subtitle">순수 주거지역이지만 치안공백으로 위험</div>
            </div>
            """, unsafe_allow_html=True)

        with area_col2:
            st.markdown("""
            <div class="card purple-card">
                <div>
                    <div class="card-title">신당동 (2위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 6.74 (2.4배 높음)</div>
                    <div class="stat-item"><strong>외국인비율:</strong> 10.0 (12배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.20 (0.3배 낮음)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 6.07</div>
                </div>
                <div class="card-subtitle">외국인 초집중지역 + CCTV 거의 없음</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="card success-card">
                <div>
                    <div class="card-title">관문동 (5위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 8.24 (2.9배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.25 (0.3배 낮음)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 0.13 (0.15배 낮음)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 6.05</div>
                </div>
                <div class="card-subtitle">CCTV 극부족 + 치안기관 부족</div>
            </div>
            """, unsafe_allow_html=True)

        with area_col3:
            st.markdown("""
            <div class="card warning-card">
                <div>
                    <div class="card-title">안심1동 (3위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 7.94 (2.8배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.00 (완전공백)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 0.25 (0.3배 낮음)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 9.06</div>
                </div>
                <div class="card-subtitle">치안기관 완전공백 + 높은 인구밀도</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card info-card">
                <div>
                    <div class="card-title">무태조야동 (6위)</div>
                    <div class="stat-item"><strong>등록인구:</strong> 5.29 (1.9배 높음)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 0.17 (0.2배 낮음)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 0.04 (0.05배 낮음)</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 6.05</div>
                </div>
                <div class="card-subtitle">전반적 안전시설 부족 + 비상벨 거의 없음</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.success("""
        ### 결론
        **인구 과밀집** + **치안시설 부족** + **외국인 집중(특수)**
        
        이 6곳은 모두 **사람은 많이 몰려있는데 지켜줄 시설이 부족한** 전형적인 치안 사각지대의 특징을 보입니다.
        
        특히 신당동의 경우, 외국인 집중지역의 특수성을, 진천동은 극도의 인구과밀 문제를, 
        안심1동과 월성1동은 치안공백의 심각성을 각각 보여줍니다.
        """)

    # ========================= 탭 4: 안전지역 분석 =========================
    with tab4:
        st.header("안전지역 6곳의 공통 패턴 분석")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("낮은 인구밀도", "0.31배")
            st.markdown("<p style='color:green; font-size: 0.875rem;'>▼ 평균 대비</p>", unsafe_allow_html=True)
        with col2:
            st.metric("풍부한 치안기관", "2.70배")
            st.markdown("<p style='color:green; font-size: 0.875rem;'>▲ 평균 대비</p>", unsafe_allow_html=True)
        with col3:
            st.metric("충분한 CCTV", "5.65배")
            st.markdown("<p style='color:green; font-size: 0.875rem;'>▲ 평균 대비</p>", unsafe_allow_html=True)
        with col4:
            st.metric("낮은 범죄발생", "0.54배")
            st.markdown("<p style='color:green; font-size: 0.875rem;'>▼ 평균 대비</p>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.subheader("안전지역 vs 위험지역 vs 전체평균")
            comparison_df = pd.DataFrame({
                '항목': ['인구밀도', '안전비상벨', '치안기관', 'CCTV', '어린이CCTV', '가로등 수'],
                '안전지역': [0.31, 3.40, 2.70, 5.65, 5.49, 2.5],
                '위험지역': [2.69, 0.55, 0.16, 0.24, 0.30, 0.8],
                '전체평균': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
            })
            
            fig3 = px.bar(comparison_df, x='항목', y=['안전지역', '위험지역', '전체평균'],
                          barmode='group', 
                          color_discrete_map={'안전지역': '#10b981', 
                                              '위험지역': '#ef4444', 
                                              '전체평균': '#64748b'})
            fig3.update_layout(height=400)
            st.plotly_chart(fig3, use_container_width=True)
        
        with chart_col2:
            st.subheader("극명한 대비")
            contrast_df = pd.DataFrame({
                '항목': ['인구밀도', '치안기관', 'CCTV', '범죄발생'],
                '안전지역': [0.88, 2.19, 5.47, 1.62],
                '위험지역': [7.68, 0.13, 0.24, 7.21]
            })
            
            fig4 = px.bar(contrast_df, x='항목', y=['안전지역', '위험지역'],
                          barmode='group',
                          color_discrete_map={'안전지역': '#10b981',
                                              '위험지역': '#ef4444'})
            fig4.update_layout(height=400)
            st.plotly_chart(fig4, use_container_width=True)
        
        st.markdown("---")
        st.subheader("가장 안전한 6개 지역의 양상")
        
        pattern_col1, pattern_col2, pattern_col3 = st.columns(3)
        
        with pattern_col1:
            st.success("**적정한 인구밀도**")
            st.write("평균의 **31%** 수준")
            st.caption("과밀하지 않아 범죄 기회 적음")
            st.markdown("---")
            
            st.info("**풍부한 치안기관**")
            st.write("평균의 **2.7배** 수준")
            st.caption("즉시 대응 가능한 경찰력")
        
        with pattern_col2:
            st.info("**충분한 CCTV**")
            st.write("평균의 **5.6배** 수준")
            st.caption("촘촘한 감시 네트워크")
            st.markdown("---")
            
            st.warning("**밝은 밤길 조성**")
            st.write("가로등/보안등 **2.5배**")
            st.caption("야간 통행 안전성 확보")
        
        with pattern_col3:
            st.error("**비상대응 우수**")
            st.write("안전비상벨 **3.4배**")
            st.caption("긴급상황 즉시 대응")
            st.markdown("---")

            st.warning("**아동보호 우수**")
            st.write("어린이CCTV **5.5배**")
            st.caption("아이들이 안전한 환경")

        st.markdown("---")
        st.subheader("개별 안전지역 분석")
        
        st.markdown("""
        <style>
        .safe-card { padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; min-height: 240px; display: flex; flex-direction: column; justify-content: space-between; }
        .safe-green-card { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #059669; }
        .safe-blue-card { background: linear-gradient(135deg, #dbeafe, #bfdbfe); border-left: 4px solid #2563eb; }
        .safe-purple-card { background: linear-gradient(135deg, #f3e8ff, #e9d5ff); border-left: 4px solid #7c3aed; }
        .safe-yellow-card { background: linear-gradient(135deg, #fef3c7, #fed7aa); border-left: 4px solid #ca8a04; }
        .safe-indigo-card { background: linear-gradient(135deg, #e0e7ff, #c7d2fe); border-left: 4px solid #4f46e5; }
        .safe-teal-card { background: linear-gradient(135deg, #ccfbf1, #99f6e4); border-left: 4px solid #0d9488; }
        .badge { background: #059669; color: white; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: bold; display: inline-block; margin-bottom: 0.5rem; }
        .badge-blue { background: #2563eb; } .badge-purple { background: #7c3aed; } .badge-yellow { background: #ca8a04; } .badge-indigo { background: #4f46e5; } .badge-teal { background: #0d9488; }
        </style>
        """, unsafe_allow_html=True)
        
        area_col1, area_col2, area_col3 = st.columns(3)
        
        with area_col1:
            st.markdown("""
            <div class="safe-card safe-green-card">
                <div>
                    <div class="card-title"> 평리5동</div>
                    <div class="badge">범죄ZERO</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 0.00</div>
                    <div class="stat-item"><strong>인구밀도:</strong> 0.48 (초저밀도)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 10.32 (초우수)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 2.72 (충분)</div>
                </div>
                <div class="card-subtitle">완벽한 안전지역 - 모든 지표 우수</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="safe-card safe-teal-card">
                <div>
                    <div class="card-title">성내2동</div>
                    <div class="badge badge-teal">중심가형</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 3.01</div>
                    <div class="stat-item"><strong>치안기관:</strong> 3.69 (최우수)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 4.66 (우수)</div>
                </div>
                <div class="card-subtitle">중심가지만 안전시설 충분</div>
            </div>
            """, unsafe_allow_html=True)
            
        
        with area_col2:
            st.markdown("""
            <div class="safe-card safe-purple-card">
                <div>
                    <div class="card-title">비산6동</div>
                    <div class="badge badge-purple">CCTV풍부</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 1.64</div>
                    <div class="stat-item"><strong>인구밀도:</strong> 0.74 (저밀도)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 5.37 (우수)</div>
                    <div class="stat-item"><strong>조명시설:</strong> 우수</div>
                </div>
                <div class="card-subtitle">CCTV와 밝은 밤길의 시너지</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="safe-card safe-yellow-card">
                <div>
                    <div class="card-title">평리1동</div>
                    <div class="badge badge-yellow">균형형</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 1.70</div>
                    <div class="stat-item"><strong>인구밀도:</strong> 0.90 (적정)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 3.31 (충분)</div>
                </div>
                <div class="card-subtitle">모든 지표가 균형있게 우수</div>
            </div>
            """, unsafe_allow_html=True)
        
        with area_col3:
            st.markdown("""
            <div class="safe-card safe-indigo-card">
                <div>
                    <div class="card-title">평리2동</div>
                    <div class="badge badge-indigo">비상벨우수</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 1.73</div>
                    <div class="stat-item"><strong>인구밀도:</strong> 1.23 (적정)</div>
                    <div class="stat-item"><strong>비상벨:</strong> 우수</div>
                </div>
                <div class="card-subtitle">비상대응체계 특히 우수</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="safe-card safe-blue-card">
                <div>
                    <div class="card-title">원대동</div>
                    <div class="badge badge-blue">치안우수</div>
                    <div class="stat-item"><strong>범죄발생:</strong> 1.64</div>
                    <div class="stat-item"><strong>인구밀도:</strong> 0.88 (저밀도)</div>
                    <div class="stat-item"><strong>치안기관:</strong> 3.69 (최우수)</div>
                    <div class="stat-item"><strong>CCTV:</strong> 6.20 (우수)</div>
                </div>
                <div class="card-subtitle">치안기관이 가장 많은 모범지역</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.success("""
        ### 결론
        **적정 인구밀도** + **충분한 치안시설** 
        
        안전한 지역들은 **사람이 적당히 살면서 안전시설이 충분한** 이상적인 주거환경을 보입니다.
        
        위험지역과 정반대로, 안전지역은 인구밀도가 낮으면서도 치안시설이 풍부하고, 
        안정적 주거지의 특성을 보입니다. 특히 범죄율이 가장 낮은 평리5동은 이상적인 안전지역 모델로 작용할 수 있습니다.
        """)

else:
    st.error("대시보드 데이터를 불러올 수 없습니다. CSV와 GeoJSON 파일이 올바른 경로에 있는지 확인해주세요.")

# ========================= # 분석 개요 탭 =========================
with tab_overview:
    st.header("대구광역시 범죄율 동향 분석")
    st.markdown("""
    최근 대구광역시의 범죄 관련 데이터를 살펴보면, 
    범죄 발생 건수는 전년 동분기 대비 **지속적으로 증가하는 추세**를 보이는 반면, **검거율은 하락**하고 있어 시민들의 불안감이 커질 수 있는 상황입니다. 
    때문에, 현재의 상황을 개선할 수 있는 방안의 필요성을 느꼈습니다.
    """)
    st.markdown("---")

    if trend_df is not None:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("전년 동분기 대비 발생 건수 증감 추이")
            fig_crime_trend = px.line(
                trend_df,
                x='분기',
                y='전년동분기 대비 발생건수 증감(건)',
                markers=True,
                labels={'분기': '분기', '전년동분기 대비 발생건수 증감(건)': '발생 건수 증감'},
                title='전년 동분기 대비 발생 건수 증감'
            )
            fig_crime_trend.update_traces(line=dict(color='#ef4444', width=3))
            st.plotly_chart(fig_crime_trend, use_container_width=True)
            st.info("**증가하는 범죄 발생 건수**\n\n그래프에서 볼 수 있듯이, 2024년 3분기를 제외하고 전년 동분기 대비 범죄 발생 건수가 꾸준히 증가하고 있습니다. 이는 치안 수요가 계속해서 늘어나고 있음을 의미합니다.")


        with col2:
            st.subheader("분기별 범죄 검거율 추이")
            # 2024년 2분기부터 데이터 필터링
            trend_df_filtered = trend_df[trend_df['분기'] >= '2024 2분기'].copy()

            fig_arrest_rate = px.line(
                trend_df_filtered,
                x='분기',
                y='발생건수대비 검거건수(%)',
                markers=True,
                labels={'분기': '분기', '발생건수대비 검거건수(%)': '검거율 (%)'},
                title='범죄 검거율'
            )
            fig_arrest_rate.update_traces(line=dict(color='#3b82f6', width=3))
            st.plotly_chart(fig_arrest_rate, use_container_width=True)
            st.warning("**감소하는 검거율**\n\n범죄 발생이 늘어나는 상황 속에서 검거율은 오히려 하락하는 추세를 보입니다. 특히 2025년 1분기에는 70.3%까지 떨어지며, 이는 범죄 대응 역량에 대한 점검이 필요함을 시사합니다.")

        st.markdown("---")
        st.success("""
        따라서, **데이터에 기반하여 범죄가 발생하기 쉬운 '취약 지역'을 식별**하고, 해당 지역의 특성을 분석하여 **안전도를 높이는** 과정이 필요합니다.
        
        """)

    else:
        st.error("범죄 동향 데이터를 불러올 수 없습니다")

# ========================= # 참고 탭 =========================
with tab_corr:
    st.header("참고: 인구수와 범죄발생수의 상관관계")
    st.markdown("---")

    # --- 데이터 로딩 및 전처리 ---
    @st.cache_data
    def load_correlation_data():
        try:
            # CSV 파일 로드
            df = pd.read_csv("인구수범죄수상관관계.csv", encoding='utf-8')
            
            # 데이터 분리 및 병합
            crime_df = df.iloc[:, [0, 1]].dropna().rename(columns={"지역": "지역", "범죄발생수": "범죄발생수"})
            pop_df = df.iloc[:, [3, 4]].dropna().rename(columns={"지역.1": "지역", "인구수": "인구수"})
            
            # 데이터 타입 변환
            crime_df['범죄발생수'] = pd.to_numeric(crime_df['범죄발생수'])
            pop_df['인구수'] = pd.to_numeric(pop_df['인구수'])

            # '지역'을 기준으로 데이터 병합
            merged_df = pd.merge(crime_df, pop_df, on="지역")
            
            # 각 지표별 순위 계산
            merged_df['범죄발생수 순위'] = merged_df['범죄발생수'].rank(method='min', ascending=False).astype(int)
            merged_df['인구수 순위'] = merged_df['인구수'].rank(method='min', ascending=False).astype(int)
            
            return merged_df
        except FileNotFoundError:
            st.error("'인구수범죄수상관관계.csv' 파일을 찾을 수 없습니다.")
            return pd.DataFrame() # Return empty dataframe on error


    corr_df = load_correlation_data()
    
    if not corr_df.empty:
        # --- 화면 구성 ---
        col1, col2 = st.columns([0.4, 0.6])

        with col1:
            st.subheader("지역별 인구수 및 범죄발생수 순위")
            
            # 사용자가 정렬 기준을 선택할 수 있도록 함
            sort_by = st.selectbox("정렬 기준 선택:", ["범죄발생수 순위", "인구수 순위"], key="sort_corr")
            
            # 선택된 기준으로 데이터프레임 정렬
            display_df = corr_df[['지역', '인구수', '인구수 순위', '범죄발생수', '범죄발생수 순위']].sort_values(by=sort_by).reset_index(drop=True)
            
            st.dataframe(display_df, use_container_width=True, height=600)

        with col2:
            st.subheader("인구수와 범죄발생수의 관계 시각화")

            # 인구수 순위 기준으로 데이터 정렬
            chart_df = corr_df.sort_values(by='인구수', ascending=False)
            
            # 이중 축 그래프 생성
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # 인구수 막대 그래프 추가
            fig.add_trace(
                go.Bar(x=chart_df['지역'], y=chart_df['인구수'], name='인구수', marker_color='lightskyblue'),
                secondary_y=False,
            )

            # 범죄발생수 꺾은선 그래프 추가
            fig.add_trace(
                go.Scatter(x=chart_df['지역'], y=chart_df['범죄발생수'], name='범죄발생수', mode='lines+markers', line=dict(color='royalblue', width=3)),
                secondary_y=True,
            )

            # 그래프 레이아웃 설정
            fig.update_layout(
                title_text="지역별 인구수와 범죄발생수 비교",
                xaxis_title="지역",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            # Y축 제목 설정
            fig.update_yaxes(title_text="<b>인구수 (명)</b>", secondary_y=False)
            fig.update_yaxes(title_text="<b>범죄발생수 (건)</b>", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)
            
            # 상관관계 분석 결과 추가
            correlation = corr_df['인구수'].corr(corr_df['범죄발생수'])
            st.info(f"인구수와 범죄발생수 사이의 **상관계수는 {correlation:.3f}**로, 매우 강한 양의 상관관계, 즉 **인구가 많은 지역일수록 범죄 발생 건수가 많은 경향**이 뚜렷하게 나타납니다.")