import pandas as pd
import folium
import geopandas as gpd
from shiny import App, render, ui
from pathlib import Path # Import the Path object

# --------------------------------------------------------------------------------
# 1. 데이터 준비 (앱이 시작될 때 한 번만 실행)
# --------------------------------------------------------------------------------

# Get the directory where this script is located
# 이 스크립트 파일이 있는 디렉토리의 절대 경로를 찾습니다.
APP_DIR = Path(__file__).parent

# Load CSV and GeoJSON files using the absolute path
# 절대 경로를 사용하여 CSV 및 GeoJSON 파일을 로드합니다.
try:
    safety_df = pd.read_csv(APP_DIR / "최종안전점수데이터.csv")
    risk_df = pd.read_csv(APP_DIR / "최종위험도측정데이터.csv")
    daegu_gdf = gpd.read_file(APP_DIR / 'daegu_map.geojson')
except FileNotFoundError as e:
    # If a file is not found, raise an error with a helpful message
    # 파일을 찾을 수 없는 경우, 어떤 파일이 없는지 알려주는 에러 메시지를 표시합니다.
    raise FileNotFoundError(
        f"Error loading data file: {e}. Make sure the following files are in the same directory as the app.py script: "
        "'최종안전점수데이터.csv', '최종위험도측정데이터.csv', 'daegu_map.geojson'"
    )

# ✨ 수정된 부분: CCTV 데이터 세분화 ✨
# '설치목적'에 따라 '구분'을 '생활방범 CCTV', '어린이보호 CCTV'로 변경합니다.
safety_df.loc[(safety_df['구분'] == 'CCTV') & (safety_df['설치목적'] == '생활방범'), '구분'] = '생활방범 CCTV'
safety_df.loc[(safety_df['구분'] == 'CCTV') & (safety_df['설치목적'] == '어린이보호'), '구분'] = '어린이보호 CCTV'
# 나머지 일반 'CCTV' 항목은 분석에서 제외합니다.
safety_df = safety_df[safety_df['구분'] != 'CCTV']


# '진천동' 데이터만 필터링하고, 위도/경도 값이 없는 데이터는 제거합니다.
jicheon_safety = safety_df[safety_df['행정동'] == '진천동'].dropna(subset=['위도', '경도'])
jicheon_risk = risk_df[risk_df['행정동'] == '진천동'].dropna(subset=['위도', '경도'])

# GeoJSON에서 '진천동' 경계 데이터만 추출합니다.
jicheon_boundary = daegu_gdf[daegu_gdf['adm_nm'].str.contains('진천동', na=False)]

# 체크박스에 표시할 선택지 목록을 만듭니다. (세분화된 CCTV 포함)
safety_choices = jicheon_safety['구분'].unique().tolist()
risk_choices = jicheon_risk['구분'].unique().tolist()
all_choices = sorted(list(set(safety_choices + risk_choices)))

# ✨ 수정된 부분: 가시성 좋은 색상 팔레트로 변경 ✨
colors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78',
    '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7'
]

# 각 '구분' 값에 색상을 매핑하는 딕셔너리(color_map)를 만듭니다.
color_map = {choice: colors[i % len(colors)] for i, choice in enumerate(all_choices)}


# --------------------------------------------------------------------------------
# 2. UI (사용자 인터페이스) 정의
# --------------------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.h2("진천동 안전 및 위험 요소 시각화 대시보드"),
    
    ui.layout_sidebar(
        # 사이드바에 들어갈 내용을 ui.sidebar() 안에 넣습니다.
        ui.sidebar(
            ui.h4("표시할 요소 선택"),
            ui.input_checkbox_group(
                "selected_elements",
                "요소를 선택하세요:",
                choices=all_choices,
                selected=all_choices
            ),
        ),
        # 메인 패널에 들어갈 내용은 바로 배치합니다.
        ui.output_ui("map_ui")
    )
)

# --------------------------------------------------------------------------------
# 3. 서버 (로직) 정의
# --------------------------------------------------------------------------------
def server(input, output, session):
    
    @output
    @render.ui
    def map_ui():
        # 1. 지도의 중심점 계산
        if not jicheon_safety.empty:
            center_lat = jicheon_safety['위도'].mean()
            center_lon = jicheon_safety['경도'].mean()
        else:
            center_lat, center_lon = 35.817, 128.522
        
        # 2. 기본 지도 생성
        m = folium.Map(location=[center_lat, center_lon], zoom_start=15)
        
        # 3. 진천동 행정 경계선을 지도에 추가
        if not jicheon_boundary.empty:
            folium.GeoJson(
                jicheon_boundary,
                name='진천동 경계',
                style_function=lambda x: {'color': 'black', 'weight': 2.5, 'fillOpacity': 0.1}
            ).add_to(m)

        # 4. 사용자가 선택한 요소들만 필터링
        selected = input.selected_elements()
        
        filtered_safety = jicheon_safety[jicheon_safety['구분'].isin(selected)]
        filtered_risk = jicheon_risk[jicheon_risk['구분'].isin(selected)]
        
        # 5. 필터링된 데이터를 지도에 점으로 표시 (개별 색상 적용)
        # 안전 시설물
        for _, row in filtered_safety.iterrows():
            element_type = row['구분']
            marker_color = color_map.get(element_type, '#808080')
            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=5, 
                color=marker_color, 
                fill=True, 
                fill_color=marker_color, 
                fill_opacity=0.8,
                popup=f"<b>종류:</b> {element_type}<br><b>목적:</b> {row.get('설치목적', 'N/A')}"
            ).add_to(m)
            
        # 위험 요소
        for _, row in filtered_risk.iterrows():
            element_type = row['구분']
            marker_color = color_map.get(element_type, '#808080')
            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=5, 
                color=marker_color, 
                fill=True, 
                fill_color=marker_color, 
                fill_opacity=0.8,
                popup=f"<b>이름:</b> {row['이름']}<br><b>업종:</b> {element_type}"
            ).add_to(m)

        # ✨ 수정된 부분: 지도에 범례(Legend) 추가 ✨
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 150px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 10px;
                    box-shadow: 3px 3px 5px rgba(0,0,0,0.3);">
        <b>범례</b><br>
        '''
        
        # 선택된 요소들만 범례에 표시
        for item in sorted(selected):
            color = color_map.get(item, '#808080')
            legend_html += f'<i style="background:{color}; width:15px; height:15px; display:inline-block; margin-right:5px; border-radius: 50%;"></i>{item}<br>'
        
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))
            
        # 6. Folium 지도를 HTML로 변환하여 UI에 전달
        return ui.HTML(m._repr_html_())

# --------------------------------------------------------------------------------
# 4. 앱 실행
# --------------------------------------------------------------------------------
app = App(app_ui, server)