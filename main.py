import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="일일 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# KOBIS 일일 박스오피스 API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 한국 시간대
KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------
# 함수 1: 한국 시간 기준 '어제' 날짜 구하기
# ---------------------------------------------------------

def get_yesterday():
    """한국 시간 기준으로 어제 날짜를 반환합니다."""
    now_kst = datetime.now(KST)
    return now_kst.date() - timedelta(days=1)


# ---------------------------------------------------------
# 함수 2: KOBIS API에서 박스오피스 가져오기
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    """
    선택한 날짜의 일일 박스오피스를 가져옵니다.

    @st.cache_data(ttl=3600)
    → 같은 날짜를 다시 조회하면 약 1시간 동안
      API를 다시 호출하지 않습니다.
    """

    # 날짜를 KOBIS가 요구하는 YYYYMMDD 형식으로 변환
    target_dt = target_date.strftime("%Y%m%d")

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외 발생
        response.raise_for_status()

        # JSON으로 변환
        data = response.json()

    except requests.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "- 인터넷 연결 상태\n"
                "- KOBIS API 주소\n"
                "- KOBIS 서버 상태\n"
                "- 잠시 후 다시 시도"
            ),
            "error": str(e),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS에서 올바른 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버 상태를 확인한 뒤 다시 시도해 주세요."
            ),
            "error": "JSON 파싱 실패",
        }

    # -----------------------------------------------------
    # 인증키 오류 등으로 faultInfo가 오는 경우
    # HTTP 상태코드는 200일 수도 있으므로 따로 확인해야 합니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # faultInfo 안의 내용을 최대한 사용자에게 보여줌
        fault_message = fault_info.get(
            "message",
            "KOBIS API에서 오류가 반환되었습니다."
        )

        return {
            "success": False,
            "message": (
                f"KOBIS API 오류가 발생했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "다음 내용을 확인해 주세요.\n"
                "- Streamlit secrets에 KOBIS_KEY가 있는지\n"
                "- KOBIS_KEY 값이 정확한지\n"
                "- KOBIS Open API 사용 권한이 있는지"
            ),
            "error": fault_info,
        }

    # boxOfficeResult가 없는 경우
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS에서 박스오피스 결과를 받지 못했습니다.\n\n"
                "조회 날짜와 KOBIS API 상태를 확인해 주세요."
            ),
            "error": data,
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": (
                "그날은 아직 집계 전입니다.\n\n"
                "다른 날짜를 선택해 보세요."
            ),
            "error": None,
        }

    # -----------------------------------------------------
    # API에서 숫자가 문자열로 오므로 숫자로 변환
    # -----------------------------------------------------

    numeric_fields = [
        "rank",
        "rankInten",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "showCnt",
    ]

    for movie in movie_list:
        for field in numeric_fields:
            try:
                movie[field] = int(movie.get(field, 0))
            except (ValueError, TypeError):
                movie[field] = 0

    return {
        "success": True,
        "empty": False,
        "data": movie_list,
    }


# ---------------------------------------------------------
# 함수 3: 숫자를 보기 좋게 표시
# ---------------------------------------------------------

def format_number(number):
    """숫자에 천 단위 쉼표를 붙입니다."""
    return f"{number:,}"


# ---------------------------------------------------------
# 제목
# ---------------------------------------------------------

st.title("🎬 일일 박스오피스")
st.caption("KOBIS 공식 일일 박스오피스 API를 이용합니다.")


# ---------------------------------------------------------
# API 인증키 가져오기
# ---------------------------------------------------------

# 실제 인증키는 코드에 작성하지 않고
# Streamlit Secrets에서 가져옵니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 날짜 선택
# ---------------------------------------------------------

yesterday = get_yesterday()

st.subheader("조회 날짜")

selected_date = st.date_input(
    "박스오피스를 조회할 날짜",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday,
    help="오늘은 아직 집계 전이므로 어제까지 선택할 수 있습니다.",
)


# ---------------------------------------------------------
# 선택한 날짜의 데이터 가져오기
# ---------------------------------------------------------

result = get_boxoffice(selected_date, api_key)


# ---------------------------------------------------------
# API 오류 또는 빈 결과 처리
# ---------------------------------------------------------

if not result["success"]:

    if result.get("empty"):
        st.warning(result["message"])
    else:
        st.error(result["message"])

    st.stop()


movies = result["data"]


# ---------------------------------------------------------
# 조회 날짜 표시
# ---------------------------------------------------------

st.caption(
    f"📅 {selected_date.strftime('%Y년 %m월 %d일')} 박스오피스"
)


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="관객수",
        value=f"{format_number(first_movie['audiCnt'])}명",
    )

with col2:
    st.metric(
        label="누적관객",
        value=f"{format_number(first_movie['audiAcc'])}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{format_number(first_movie['scrnCnt'])}개",
    )

st.markdown(
    f"### 1위 · {first_movie['movieNm']}"
)


# ---------------------------------------------------------
# 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = movies[:5]

# Streamlit 차트용 데이터 만들기
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 전체 영화 목록 표 만들기
# ---------------------------------------------------------

st.subheader("🎥 전체 박스오피스")

table_data = []

for movie in movies:

    # 순위 증감 표시
    rank_inten = movie["rankInten"]

    if rank_inten > 0:
        # 양수 = 전날보다 순위 상승
        rank_change = f"🔺 +{rank_inten}"
    elif rank_inten < 0:
        # 음수 = 전날보다 순위 하락
        rank_change = f"🔽 {rank_inten}"
    else:
        # 변화 없음
        rank_change = "—"

    # 누적관객이 100만 명을 넘으면 트로피 표시
    movie_name = movie["movieNm"]

    if movie["audiAcc"] >= 1_000_000:
        movie_name += " 🏆"

    table_data.append(
        {
            "순위": movie["rank"],
            "증감": rank_change,
            "영화명": movie_name,
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )


# ---------------------------------------------------------
# 숫자에 천 단위 쉼표를 붙여서 표시
# ---------------------------------------------------------

display_data = []

for row in table_data:
    display_data.append(
        {
            "순위": row["순위"],
            "증감": row["증감"],
            "영화명": row["영화명"],
            "개봉일": row["개봉일"],
            "관객수": format_number(row["관객수"]),
            "누적관객": format_number(row["누적관객"]),
            "스크린수": format_number(row["스크린수"]),
        }
    )


st.dataframe(
    display_data,
    use_container_width=True,
    hide_index=True,
)
