"""내 PC의 Chrome으로 코레일 예매 화면까지 열어주는 로컬 보조 스크립트.

흐름
  1. Chrome 창을 열고 코레일 로그인 페이지로 이동한다.
  2. 아이디/비밀번호 입력과 Enter는 사용자가 직접 한다. (스크립트는 입력값을 다루지 않는다)
  3. 로그인이 끝난 것이 감지되면 예매 화면으로 이동해 출발/도착/날짜/시간을 미리 채운다.
  4. 조회, 좌석 선택, 예약 확정, 결제는 사용자가 직접 한다. 창은 사용자가 닫을 때까지 유지된다.

사용 예
  pip install -r tools/requirements-local.txt
  python tools/open_booking.py --src 서울 --dst 부산 --date 20261015 --time 0900

주의: 코레일 사이트 구조가 바뀌면 아래 URL/셀렉터 상수를 수정해야 한다.
미리 채우기에 실패해도 예매 화면 자체는 열려 있으므로 직접 입력하면 된다.
"""
import argparse
import sys
from datetime import datetime

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://www.letskorail.com/korail/com/login.do"
BOOKING_URL = "https://www.letskorail.com/ebizprd/EbizPrdTicketpr21100W_pr21101.do"

# 예매 폼 필드 이름 (사이트 변경 시 여기만 고치면 된다)
FIELD_SRC = "txtGoStart"
FIELD_DST = "txtGoEnd"
FIELD_YEAR = "selGoYear"
FIELD_MONTH = "selGoMonth"
FIELD_DAY = "selGoDay"
FIELD_HOUR = "selGoHour"

LOGIN_WAIT_MS = 10 * 60 * 1000  # 로그인 대기 최대 10분


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", required=True, help="출발역 (예: 서울)")
    p.add_argument("--dst", required=True, help="도착역 (예: 부산)")
    p.add_argument("--date", required=True, help="출발 날짜 YYYYMMDD")
    p.add_argument("--time", default="0000", help="출발 시각 HHMM (기본 0000)")
    args = p.parse_args()
    try:
        args.dt = datetime.strptime(args.date + args.time, "%Y%m%d%H%M")
    except ValueError:
        p.error("--date는 YYYYMMDD, --time은 HHMM 형식이어야 합니다.")
    return args


def wait_for_login(page) -> None:
    """사용자가 로그인을 마칠 때까지 대기한다 (로그인 후에는 '로그아웃' 링크가 보인다)."""
    print("열린 Chrome 창에서 직접 로그인하세요. (아이디/비밀번호 입력 후 Enter)")
    page.wait_for_selector("text=로그아웃", state="attached", timeout=LOGIN_WAIT_MS)
    print("로그인 확인됨. 예매 화면으로 이동합니다.")


def set_field(page, name: str, value: str) -> bool:
    """name 속성으로 필드를 찾아 값을 채운다. select/input 모두 지원."""
    loc = page.locator(f'[name="{name}"]').first
    try:
        if loc.count() == 0:
            return False
        if loc.evaluate("el => el.tagName") == "SELECT":
            loc.select_option(value, timeout=3000)
        else:
            # 역 입력칸은 readonly인 경우가 있어 값을 직접 지정한다
            loc.evaluate(
                "(el, v) => { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); }",
                value,
            )
        return True
    except PlaywrightError:
        return False


def prefill(page, args) -> None:
    dt = args.dt
    fields = {
        FIELD_SRC: args.src,
        FIELD_DST: args.dst,
        FIELD_YEAR: str(dt.year),
        FIELD_MONTH: f"{dt.month:02d}",
        FIELD_DAY: f"{dt.day:02d}",
        FIELD_HOUR: f"{dt.hour:02d}",
    }
    failed = [n for n, v in fields.items() if not set_field(page, n, v)]
    if failed:
        print(f"일부 항목({', '.join(failed)})은 자동으로 채우지 못했습니다. 화면에서 직접 입력하세요.")
    else:
        print("출발/도착/날짜/시간을 채웠습니다. 조회 이후는 직접 진행하세요.")


def main() -> int:
    args = parse_args()
    with sync_playwright() as pw:
        # 설치된 Chrome 사용 (없으면 `playwright install chromium` 후 channel 줄 제거)
        browser = pw.chromium.launch(channel="chrome", headless=False)
        page = browser.new_context().new_page()
        page.goto(LOGIN_URL)
        try:
            wait_for_login(page)
        except PlaywrightError:
            print("로그인 대기 시간이 초과되었습니다.")
            browser.close()
            return 1
        page.goto(BOOKING_URL)
        prefill(page, args)
        print("창을 닫으면 종료됩니다.")
        try:
            page.wait_for_event("close", timeout=0)
        except PlaywrightError:
            pass
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
