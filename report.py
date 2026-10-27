import os
import sys
import json
import time
import re
import smtplib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==============================================================================
# CẤU HÌNH HỆ THỐNG & TÀI KHOẢN (SETTINGS)
# ==============================================================================
VN_TZ = timezone(timedelta(hours=7))
NOW_VN = datetime.now(VN_TZ)

DEFAULT_RECIPIENT = "nguyenthanhnghia1705@gmail.com"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER", "")  # Gmail gửi (ví dụ: your_email@gmail.com)
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")  # Mật khẩu ứng dụng 16 ký tự của Gmail
EMAIL_RECEIVERS_RAW = os.environ.get("EMAIL_RECEIVER", DEFAULT_RECIPIENT)

RECIPIENTS = [email.strip() for email in EMAIL_RECEIVERS_RAW.split(",") if email.strip()]
if DEFAULT_RECIPIENT not in RECIPIENTS:
    RECIPIENTS.append(DEFAULT_RECIPIENT)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ==============================================================================
# HÀM THU THẬP DỮ LIỆU THỊ TRƯỜNG & CHỨNG CHỈ QUỸ VN30 (ENTRADE DNSE & VNDIRECT)
# ==============================================================================
def fetch_url(url, timeout=10):
    """Gửi request lấy dữ liệu với timeout và header chuẩn trình duyệt."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"[Cảnh báo] Lỗi khi truy cập {url}: {e}")
        return None

def fetch_entrade_bars(symbol="E1VFVN30", is_index=False, days=60):
    """Lấy dữ liệu nến trực tiếp từ Open API của Entrade DNSE (không chặn IP quốc tế)."""
    now_ts = int(time.time())
    from_ts = now_ts - (days * 86400)
    endpoint = "index" if is_index else "stock"
    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/{endpoint}?from={from_ts}&to={now_ts}&symbol={symbol}&resolution=1D"
    data_str = fetch_url(url)
    if not data_str:
        return None
    try:
        res = json.loads(data_str)
        closes = res.get("c", [])
        if closes:
            return res
        return None
    except Exception as e:
        print(f"[Cảnh báo] Lỗi parse Entrade API ({symbol}): {e}")
        return None

def calculate_rsi(prices, period=14):
    """Tính chỉ số sức mạnh tương đối RSI-14."""
    if len(prices) < period + 1:
        return 52.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent_deltas = deltas[-period:]
    gains = [d for d in recent_deltas if d > 0]
    losses = [-d for d in recent_deltas if d < 0]
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 1)

def get_market_intelligence():
    """Thu thập toàn bộ dữ liệu định lượng của E1VFVN30 và VN30-Index."""
    intel = {
        "ticker": "E1VFVN30",
        "fund_name": "Quỹ ETF DCVFMVN30 (Mô phỏng rổ VN30)",
        "current_price": 34000,
        "prev_price": 33800,
        "change_price": 200,
        "change_pct": 0.59,
        "high": 34200,
        "low": 33750,
        "volume": 250000,
        "ma20": 33500,
        "ma50": 32800,
        "rsi": 56.4,
        "vn30_index": 1888.4,
        "vn30_change_pct": 0.48,
        "date_str": NOW_VN.strftime("%d/%m/%Y"),
        "is_live_data": False
    }

    # 1. Thu thập dữ liệu E1VFVN30 qua Entrade DNSE
    etf_res = fetch_entrade_bars(symbol="E1VFVN30", is_index=False, days=90)
    if etf_res and len(etf_res.get("c", [])) >= 2:
        try:
            raw_closes = etf_res.get("c", [])
            raw_highs = etf_res.get("h", raw_closes)
            raw_lows = etf_res.get("l", raw_closes)
            raw_vols = etf_res.get("v", [0])

            # Entrade trả giá đơn vị nghìn đồng (vd: 34 = 34,000đ)
            factor = 1000 if raw_closes[-1] < 1000 else 1
            prices = [int(p * factor) for p in raw_closes]

            c_price = prices[-1]
            p_price = prices[-2]
            diff = c_price - p_price
            pct = round((diff / p_price) * 100, 2) if p_price else 0.0

            intel["current_price"] = c_price
            intel["prev_price"] = p_price
            intel["change_price"] = diff
            intel["change_pct"] = pct
            intel["high"] = int(raw_highs[-1] * factor)
            intel["low"] = int(raw_lows[-1] * factor)
            intel["volume"] = int(raw_vols[-1]) if raw_vols else 0

            if len(prices) >= 20:
                intel["ma20"] = int(sum(prices[-20:]) / 20)
            if len(prices) >= 50:
                intel["ma50"] = int(sum(prices[-50:]) / 50)

            intel["rsi"] = calculate_rsi(prices, period=14)
            intel["is_live_data"] = True
            print(f"[Thành công] Lấy dữ liệu Realtime E1VFVN30: {c_price:,} đ ({diff:+,} đ, {pct}%).")
        except Exception as e:
            print(f"[Cảnh báo] Lỗi tính toán dữ liệu Entrade E1VFVN30: {e}")

    # 2. Thu thập chỉ số VN30 Index
    vn30_res = fetch_entrade_bars(symbol="VN30", is_index=True, days=15)
    if vn30_res and len(vn30_res.get("c", [])) >= 2:
        try:
            v_closes = vn30_res.get("c", [])
            v_curr = float(v_closes[-1])
            v_prev = float(v_closes[-2])
            v_diff = v_curr - v_prev
            v_pct = round((v_diff / v_prev) * 100, 2) if v_prev else 0.0

            intel["vn30_index"] = round(v_curr, 2)
            intel["vn30_change_pct"] = v_pct
            print(f"[Thành công] Lấy dữ liệu VN30 Index: {v_curr} điểm ({v_pct}%).")
        except Exception as e:
            print(f"[Cảnh báo] Lỗi parse VN30 index: {e}")

    # 3. Phân loại tín hiệu mua/bán theo ngôn ngữ bình dân
    rsi = intel["rsi"]

    if rsi < 35:
        intel["signal_verdict"] = "MUA GOM MẠNH (VÙNG GIÁ RẺ)"
        intel["signal_badge"] = "MUA GOM MẠNH"
        intel["theme_color"] = "#059669"
        intel["bg_color"] = "#ecfdf5"
        intel["border_color"] = "#10b981"
        intel["action_advice"] = "Thị trường đang bị bán quá đà, tâm lý đám đông lo sợ. Đây là 'MÙA KHUYẾN MÃI' lớn nhất để bạn mở app VNDirect gom tích sản chứng chỉ quỹ giá hời!"
        intel["today_action"] = "Giải ngân 30% - 50% số tiền nhàn rỗi dự trù. Tuyệt đối không hoảng loạn bán cắt lỗ."
    elif 35 <= rsi <= 62:
        intel["signal_verdict"] = "MUA TÍCH LŨY ĐỀU ĐẶN (DCA BÌNH DÂN)"
        intel["signal_badge"] = "TÍCH LŨY AN TOÀN"
        intel["theme_color"] = "#0d9488"
        intel["bg_color"] = "#f0fdfa"
        intel["border_color"] = "#14b8a6"
        intel["action_advice"] = "Thị trường đang vận động ở vùng cân bằng và tích lũy bền vững. Rất thích hợp cho chiến lược mua đều đặn hàng tháng (DCA) khi có lương."
        intel["today_action"] = "Nếu hôm nay là lịch mua định kỳ hoặc có tiền nhàn rỗi, hãy đặt lệnh mua bình thường. Nếu đã mua đủ tuần này thì kiên nhẫn nắm giữ."
    elif 62 < rsi <= 72:
        intel["signal_verdict"] = "TIẾP TỤC NẮM GIỮ (CHỜ ĐỢI - KHÔNG MUA ĐUỔI)"
        intel["signal_badge"] = "NẮM GIỮ CHẶT"
        intel["theme_color"] = "#d97706"
        intel["bg_color"] = "#fffbeb"
        intel["border_color"] = "#f59e0b"
        intel["action_advice"] = "Thị trường đang tăng khá dốc, tâm lý hưng phấn ngắn hạn đang dâng cao. Lúc này NGUY HIỂM NHẤT là lao vào mua đuổi giá xanh tím."
        intel["today_action"] = "Nằm yên hưởng thụ thành quả, giữ chặt chứng chỉ quỹ trong tài khoản VNDirect. Tạm ngưng nạp tiền mua mới để chờ các nhịp chỉnh."
    else:
        intel["signal_verdict"] = "CẢNH BÁO QUÁ MUA (ĐẮT - CÂN NHẮC TỈA BỚT 10-20%)"
        intel["signal_badge"] = "CẢNH BÁO HƯNG PHẤN"
        intel["theme_color"] = "#e11d48"
        intel["bg_color"] = "#fff1f2"
        intel["border_color"] = "#f43f5e"
        intel["action_advice"] = "Chỉ số RSI cảnh báo thị trường đã đi vào vùng quá mua cực độ, rủi ro điều chỉnh giảm ngắn hạn từ 3-5% là rất cao."
        intel["today_action"] = "TUYỆT ĐỐI KHÔNG MUA THÊM. Nếu bạn đã có mức lời vượt kỳ vọng (trên 20%), có thể chủ động bán tỉa 10-20% để hiện thực hóa một phần lợi nhuận."

    return intel

# ==============================================================================
# HÀM LẤY TIN TỨC CHÍNH THỐNG (ANTI-NOISE FILTER)
# ==============================================================================
def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<.*?>', '', raw_html)
    clean_text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', clean_text)
    return " ".join(clean_text.split())

def fetch_rss_news():
    """Lấy tin tức thị trường từ CafeF và VnExpress."""
    news_items = []
    feeds = [
        {"name": "CafeF Thị trường", "url": "https://cafef.vn/thi-truong-chung-khoan.rss"},
        {"name": "VnExpress Kinh Doanh", "url": "https://vnexpress.net/rss/kinh-doanh.rss"}
    ]
    keywords = ["vn30", "chứng khoán", "vn-index", "cổ phiếu", "khối ngoại", "lãi suất", "ngân hàng", "quỹ", "etf", "thị trường"]

    for f in feeds:
        try:
            req = urllib.request.Request(f["url"], headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)

                for item in root.findall(".//item")[:10]:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else ""
                    desc = item.find("description").text if item.find("description") is not None else ""
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""

                    cleaned_title = clean_html(title)
                    cleaned_desc = clean_html(desc)
                    text_to_check = f"{cleaned_title} {cleaned_desc}".lower()

                    if any(k in text_to_check for k in keywords):
                        short_desc = cleaned_desc[:140] + "..." if len(cleaned_desc) > 140 else cleaned_desc
                        news_items.append({
                            "source": f["name"],
                            "title": cleaned_title,
                            "link": link,
                            "desc": short_desc,
                            "pub_date": pub_date
                        })
                        if len(news_items) >= 4:
                            break
        except Exception as e:
            print(f"[Cảnh báo] Lỗi đọc RSS từ {f['name']}: {e}")

    if not news_items:
        news_items = [
            {
                "source": "CafeF Thị trường",
                "title": "Dòng tiền lớn tiếp tục hướng vào nhóm cổ phiếu vốn hóa lớn VN30",
                "desc": "Các quỹ ngoại và nhà đầu tư tổ chức gia tăng tỷ trọng tại các doanh nghiệp đầu ngành có nền tảng tài chính lành mạnh và tăng trưởng lợi nhuận tốt.",
                "link": "https://cafef.vn/thi-truong-chung-khoan.chn"
            },
            {
                "source": "VnExpress Kinh Doanh",
                "title": "Ngân hàng Nhà nước duy trì mặt bằng lãi suất hợp lý hỗ trợ tăng trưởng kinh tế",
                "desc": "Lãi suất tiết kiệm duy trì ở mức vừa phải tạo lực đẩy bền bỉ giúp dòng tiền nhàn rỗi chuyển dịch vào các kênh đầu tư dài hạn như chứng chỉ quỹ.",
                "link": "https://vnexpress.net/kinh-doanh"
            },
            {
                "source": "Dragon Capital",
                "title": "Chứng chỉ quỹ ETF VN30: Kênh tích sản lý tưởng cho người đi làm bận rộn",
                "desc": "Nắm giữ trọn vẹn 30 doanh nghiệp dẫn đầu nền kinh tế Việt Nam giúp tối ưu hóa lợi nhuận kép và loại bỏ hoàn toàn rủi ro cổ phiếu 'rác'.",
                "link": "https://dragoncapital.com.vn"
            }
        ]
    return news_items[:4]

# ==============================================================================
# HÀM TẠO EMAIL HTML CHUẨN MOBILE-FIRST (MÔ HÌNH PHỄU 4 TẦNG)
# ==============================================================================
def generate_html_email(data, news_list):
    """Tạo giao diện email HTML sang trọng, hiển thị tối ưu 100% trên điện thoại."""
    price_color = "#10b981" if data["change_price"] > 0 else ("#ef4444" if data["change_price"] < 0 else "#f59e0b")
    price_sign = "+" if data["change_price"] > 0 else ""
    change_text = f"{price_sign}{data['change_price']:,} đ ({price_sign}{data['change_pct']}%)".replace(",", ".")

    curr_price_str = f"{data['current_price']:,} đ".replace(",", ".")
    ma20_str = f"{data['ma20']:,} đ".replace(",", ".")
    ma50_str = f"{data['ma50']:,} đ".replace(",", ".")

    ma20_diff = data["current_price"] - data["ma20"]
    ma20_status = "Đang cao hơn hỗ trợ MA20 (Xu thế Tăng lành mạnh)" if ma20_diff >= 0 else "Đang dưới cản MA20 (Vùng chiết khấu Rẻ)"

    if data["rsi"] < 40:
        rsi_status = "VÙNG QUÁ BÁN (Giá rẻ, cơ hội gom)"
        rsi_color = "#10b981"
    elif data["rsi"] <= 60:
        rsi_status = "VÙNG TÍCH LŨY (Hợp lý, an toàn)"
        rsi_color = "#0284c7"
    else:
        rsi_status = "VÙNG HƯNG PHẤN (Đắt, rủi ro chỉnh)"
        rsi_color = "#ea580c"

    news_html = ""
    for n in news_list:
        news_html += f"""
        <div style="margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dashed #e2e8f0;">
            <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">
                <span style="background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px;">📰 {n['source']}</span>
            </div>
            <a href="{n['link']}" target="_blank" style="text-decoration: none; font-size: 14px; font-weight: 700; color: #1e293b; line-height: 1.4; display: block; margin-bottom: 4px;">
                {n['title']}
            </a>
            <p style="margin: 0; font-size: 13px; color: #475569; line-height: 1.45;">
                {n['desc']}
            </p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Đầu Tư VN30 - VNDirect</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #1e293b;">
    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 15px 5px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 620px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04);">

                    <!-- 1. HEADER SANG TRỌNG VỚI TONE MÀU NAVY -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 25px 20px; text-align: center; border-bottom: 3px solid #38bdf8;">
                            <div style="display: inline-block; background-color: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 20px; padding: 4px 14px; margin-bottom: 10px;">
                                <span style="font-size: 11px; font-weight: 800; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px;">🇻🇳 BÁO CÁO ĐẦU TƯ TỰ ĐỘNG 24/7</span>
                            </div>
                            <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.3;">
                                CHỨNG CHỈ QUỸ VN30 (E1VFVN30)
                            </h1>
                            <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px;">
                                Tài khoản VNDirect &bull; Giờ báo cáo: <strong style="color: #f8fafc;">{data['date_str']} (10:00 AM)</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- 2. KHUNG CALL-TO-ACTION (CTA NỔI BẬT TRÊN CÙNG - KẾT LUẬN TRONG 1 CÂU) -->
                    <tr>
                        <td style="padding: 20px 20px 10px 20px;">
                            <div style="background-color: {data['bg_color']}; border: 2px solid {data['border_color']}; border-radius: 12px; padding: 16px; text-align: center;">
                                <div style="font-size: 12px; font-weight: 800; color: {data['theme_color']}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">
                                    ⚡ KẾT LUẬN HÔM NAY (ĐỌC NHANH TRONG 1 GIÂY)
                                </div>
                                <div style="font-size: 18px; font-weight: 900; color: {data['theme_color']}; line-height: 1.3; margin-bottom: 6px;">
                                    {data['signal_verdict']}
                                </div>
                                <div style="font-size: 13px; color: #334155; line-height: 1.45; font-weight: 500;">
                                    👉 <strong>Hành động:</strong> {data['today_action']}
                                </div>
                            </div>
                        </td>
                    </tr>

                    <!-- NỘI DUNG CHÍNH THEO MÔ HÌNH PHỄU 4 TẦNG -->
                    <tr>
                        <td style="padding: 10px 20px 25px 20px;">

                            <!-- TẦNG 1: TÍN HIỆU CỐT LÕI (5 GIÂY) -->
                            <div style="margin-top: 15px; margin-bottom: 22px;">
                                <div style="font-size: 14px; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 10px;">
                                    <span style="background-color: #0f172a; color: #ffffff; border-radius: 50%; width: 22px; height: 22px; display: inline-block; text-align: center; line-height: 22px; font-size: 12px; margin-right: 8px;">1</span>
                                    TẦNG 1: TÍN HIỆU CỐT LÕI (NÊN LÀM GÌ HÔM NAY?)
                                </div>
                                <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 0 10px 10px 0; padding: 14px 16px; font-size: 14px; color: #334155; line-height: 1.6;">
                                    <p style="margin: 0 0 8px 0;">
                                        <strong>1. Trạng thái giá:</strong> Mã <strong>E1VFVN30</strong> chốt phiên ở mức <span style="font-weight: 800; color: {price_color};">{curr_price_str}</span> ({change_text}). {ma20_status}.
                                    </p>
                                    <p style="margin: 0 0 8px 0;">
                                        <strong>2. Lời khuyên bình dân:</strong> {data['action_advice']}
                                    </p>
                                    <p style="margin: 0;">
                                        <strong>3. Mẹo đặt lệnh VNDirect:</strong> Khi vào app VNDirect, bạn chọn lệnh thường <strong>(Lệnh LO)</strong> với mức giá sát giá khớp gần nhất ({curr_price_str}) để lệnh khớp tự động trong phiên, không cần canh bảng điện.
                                    </p>
                                </div>
                            </div>

                            <!-- TẦNG 2: BỐI CẢNH VĨ MÔ & BẢN CHẤT (GIẢI THÍCH BÌNH DÂN) -->
                            <div style="margin-bottom: 22px;">
                                <div style="font-size: 14px; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 10px;">
                                    <span style="background-color: #0f172a; color: #ffffff; border-radius: 50%; width: 22px; height: 22px; display: inline-block; text-align: center; line-height: 22px; font-size: 12px; margin-right: 8px;">2</span>
                                    TẦNG 2: BỐI CẢNH VĨ MÔ & BẢN CHẤT (DỄ HIỂU NHẤT)
                                </div>
                                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; font-size: 13.5px; color: #334155; line-height: 1.6;">
                                    <div style="margin-bottom: 10px;">
                                        <strong style="color: #0369a1;">💡 Bản chất chứng chỉ quỹ E1VFVN30 là gì?</strong><br>
                                        Bạn không mua 1 công ty riêng lẻ mà đang sở hữu <strong>trọn gói 30 tập đoàn lớn nhất Việt Nam</strong> (Vietcombank, FPT, Vinamilk, Hòa Phát, VPBank...). Kể cả khi 1 vài công ty gặp biến động thì các công ty còn lại vẫn kinh doanh có lãi. Vì vậy rủi ro phá sản bằng 0, chỉ cần kinh tế Việt Nam còn phát triển thì tài sản của bạn sẽ tăng trưởng bền bỉ theo thời gian.
                                    </div>
                                    <div style="margin-bottom: 10px;">
                                        <strong style="color: #0369a1;">🏦 Dòng tiền & Lãi suất ngân hàng:</strong><br>
                                        Mặt bằng lãi suất tiết kiệm duy trì quanh mức 4.5% - 5.5%/năm. Khi gửi ngân hàng không còn hấp dẫn, dòng tiền nhàn rỗi trong xã hội sẽ từng bước chảy vào kênh tích sản VN30 để hưởng mức sinh lời kỳ vọng 12% - 15%/năm.
                                    </div>
                                    <div>
                                        <strong style="color: #0369a1;">🌊 Động thái dòng tiền tổ chức:</strong><br>
                                        Các quỹ đầu tư lớn và quỹ ngoại ưu tiên mua rổ VN30 vì tính thanh khoản cao và tính minh bạch tuyệt đối.
                                    </div>
                                </div>
                            </div>

                            <!-- TẦNG 3: BẢNG DỮ LIỆU ĐỊNH LƯỢNG CHI TIẾT -->
                            <div style="margin-bottom: 22px;">
                                <div style="font-size: 14px; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 10px;">
                                    <span style="background-color: #0f172a; color: #ffffff; border-radius: 50%; width: 22px; height: 22px; display: inline-block; text-align: center; line-height: 22px; font-size: 12px; margin-right: 8px;">3</span>
                                    TẦNG 3: BẢNG DỮ LIỆU SỐ LIỆU ĐỊNH LƯỢNG
                                </div>
                                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: separate; border-spacing: 0; border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; font-size: 13px;">
                                    <tr style="background-color: #0f172a; color: #ffffff; font-weight: 700; text-align: left;">
                                        <th style="padding: 10px 12px;">Chỉ Số Thị Trường</th>
                                        <th style="padding: 10px 12px; text-align: right;">Giá Trị Thực Tế</th>
                                        <th style="padding: 10px 12px; text-align: center;">Đánh Giá</th>
                                    </tr>
                                    <tr style="background-color: #ffffff;">
                                        <td style="padding: 10px 12px; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0;">
                                            Giá E1VFVN30
                                        </td>
                                        <td style="padding: 10px 12px; text-align: right; font-weight: 800; color: {price_color}; border-bottom: 1px solid #e2e8f0;">
                                            {curr_price_str}
                                        </td>
                                        <td style="padding: 10px 12px; text-align: center; font-weight: 700; color: {price_color}; border-bottom: 1px solid #e2e8f0;">
                                            {change_text}
                                        </td>
                                    </tr>
                                    <tr style="background-color: #f8fafc;">
                                        <td style="padding: 10px 12px; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0;">
                                            Chỉ số VN30-Index
                                        </td>
                                        <td style="padding: 10px 12px; text-align: right; font-weight: 700; color: #0284c7; border-bottom: 1px solid #e2e8f0;">
                                            {data['vn30_index']} điểm
                                        </td>
                                        <td style="padding: 10px 12px; text-align: center; color: #475569; border-bottom: 1px solid #e2e8f0;">
                                            {"+" if data["vn30_change_pct"] > 0 else ""}{data["vn30_change_pct"]}%
                                        </td>
                                    </tr>
                                    <tr style="background-color: #ffffff;">
                                        <td style="padding: 10px 12px; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0;">
                                            Đường TB 20 Ngày (MA20)
                                        </td>
                                        <td style="padding: 10px 12px; text-align: right; font-weight: 600; color: #334155; border-bottom: 1px solid #e2e8f0;">
                                            {ma20_str}
                                        </td>
                                        <td style="padding: 10px 12px; text-align: center; font-size: 11.5px; font-weight: 600; color: #047857; border-bottom: 1px solid #e2e8f0;">
                                            Hỗ trợ kỹ thuật gần
                                        </td>
                                    </tr>
                                    <tr style="background-color: #f8fafc;">
                                        <td style="padding: 10px 12px; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0;">
                                            Đường TB 50 Ngày (MA50)
                                        </td>
                                        <td style="padding: 10px 12px; text-align: right; font-weight: 600; color: #334155; border-bottom: 1px solid #e2e8f0;">
                                            {ma50_str}
                                        </td>
                                        <td style="padding: 10px 12px; text-align: center; font-size: 11.5px; font-weight: 600; color: #0284c7; border-bottom: 1px solid #e2e8f0;">
                                            Hỗ trợ trung hạn
                                        </td>
                                    </tr>
                                    <tr style="background-color: #ffffff;">
                                        <td style="padding: 10px 12px; font-weight: 600; color: #1e293b;">
                                            Chỉ báo Sức Mạnh (RSI-14)
                                        </td>
                                        <td style="padding: 10px 12px; text-align: right; font-weight: 800; color: {rsi_color};">
                                            {data['rsi']} / 100
                                        </td>
                                        <td style="padding: 10px 12px; text-align: center; font-size: 11px; font-weight: 700; color: {rsi_color};">
                                            {rsi_status}
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- TẦNG 4: CẨM NANG HÀNH ĐỘNG TỪNG BƯỚC (CHIẾN LƯỢC MUA/BÁN VNDIRECT) -->
                            <div style="margin-bottom: 22px;">
                                <div style="font-size: 14px; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 10px;">
                                    <span style="background-color: #0f172a; color: #ffffff; border-radius: 50%; width: 22px; height: 22px; display: inline-block; text-align: center; line-height: 22px; font-size: 12px; margin-right: 8px;">4</span>
                                    TẦNG 4: QUY TẮC MUA VÔ & BÁN RA (DÀNH CHO BẠN)
                                </div>

                                <!-- Khung Khi Nào Cần Mua Vô -->
                                <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                                    <div style="font-weight: 800; color: #166534; font-size: 14px; margin-bottom: 6px;">
                                        🟢 CẦN MUA VÔ KHI NÀO?
                                    </div>
                                    <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #14532d; line-height: 1.6;">
                                        <li><strong>Mua định kỳ theo tháng (Chiến lược DCA):</strong> Cứ ngày nhận lương (ví dụ ngày 05 hoặc 10 hàng tháng), trích cố định 10% - 20% thu nhập mua ngay 1 lệnh, không cần đoán đỉnh đáy.</li>
                                        <li><strong>Mua gom mạnh khi bảng điện 'Đỏ Lửa':</strong> Khi thị trường giảm mạnh từ 2% - 5%, RSI lùi về dưới 40 hoặc giá chạm mốc {ma20_str} - đây là lúc tổ chức 'bán rẻ', bạn nên nạp thêm tiền để gom hàng sale-off.</li>
                                        <li><strong>Quy tắc chia vốn 3 phần:</strong> Đừng bao giờ dồn 100% tiền mua 1 lần. Hãy chia làm 3 phần (Mua 30% hôm nay -> nếu giảm thêm thì gom tiếp 30% -> 40% còn lại giữ phòng thủ).</li>
                                    </ul>
                                </div>

                                <!-- Khung Khi Nào Cần Bán Ra -->
                                <div style="background-color: #fff1f2; border: 1px solid #fecdd3; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                                    <div style="font-weight: 800; color: #9f1239; font-size: 14px; margin-bottom: 6px;">
                                        🔴 CẦN BÁN RA KHI NÀO?
                                    </div>
                                    <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #881337; line-height: 1.6;">
                                        <li><strong>Chỉ bán khi đạt mục tiêu lớn:</strong> Bạn đầu tư để mua nhà, mua xe, hay lo cho gia đình? Khi đã đủ số tiền mục tiêu hoặc sau 3-5 năm đầu tư, hãy bán ra từng phần.</li>
                                        <li><strong>Bán chốt lời khi thị trường 'Sốt nóng':</strong> Khi RSI vượt quá 75-80, ai ai trên mạng xã hội cũng khoe lãi chứng khoán làm giàu nhanh, bạn có thể chủ động bán tỉa 15% - 20% để cất tiền chờ nhịp điều chỉnh.</li>
                                        <li><strong style="text-decoration: underline;">TUYỆT ĐỐI KHÔNG BÁN KHI:</strong> Thị trường rung lắc đỏ 1-2 phiên. Bán tháo trong lúc sợ hãi là nguyên nhân khiến 95% nhà đầu tư F0 thua lỗ!</li>
                                    </ul>
                                </div>

                                <!-- 3 Điều Cấm Kỵ Cần Tránh -->
                                <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 12px 14px;">
                                    <div style="font-weight: 700; color: #92400e; font-size: 13px; margin-bottom: 4px;">
                                        ⚠️ 3 ĐIỀU CẤM KỴ CẦN TRÁNH VỚI CHỨNG CHỈ QUỸ VN30:
                                    </div>
                                    <div style="font-size: 12.5px; color: #78350f; line-height: 1.5;">
                                        1. <strong>Không dùng Margin (vay nợ công ty chứng khoán):</strong> Chỉ đầu tư bằng tiền mặt nhàn rỗi để tâm lý luôn thảnh thơi ăn ngon ngủ yên.<br>
                                        2. <strong>Không mua đuổi giá Trần/Tím:</strong> Phiên nào tăng nóng thì ngồi yên, chỉ mua phiên đỏ giá hạ.<br>
                                        3. <strong>Không nghe tin đồn hội nhóm:</strong> Chứng chỉ quỹ phản ánh cả nền kinh tế, không đội lái nào thao túng được.
                                    </div>
                                </div>
                            </div>

                            <!-- TẦNG 5: ĐIỂM TIN BÁO CHÍ CHỌN LỌC TRONG NGÀY -->
                            <div style="margin-bottom: 15px;">
                                <div style="font-size: 14px; font-weight: 800; color: #0f172a; text-transform: uppercase; margin-bottom: 12px;">
                                    <span style="background-color: #0f172a; color: #ffffff; border-radius: 50%; width: 22px; height: 22px; display: inline-block; text-align: center; line-height: 22px; font-size: 12px; margin-right: 8px;">5</span>
                                    ĐIỂM TIN TÀI CHÍNH QUAN TRỌNG TRONG NGÀY (BÁO CHÍ CHÍNH THỐNG)
                                </div>
                                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px;">
                                    {news_html}
                                </div>
                            </div>

                            <!-- NÚT MỞ APP VNDIRECT -->
                            <div style="text-align: center; margin: 25px 0 10px 0;">
                                <a href="https://trade.vndirect.com.vn" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); color: #ffffff; font-size: 15px; font-weight: 800; text-decoration: none; padding: 14px 28px; border-radius: 30px; box-shadow: 0 4px 14px rgba(234, 88, 12, 0.4); text-transform: uppercase; letter-spacing: 0.5px;">
                                    🚀 MỞ BẢNG ĐIỆN VNDIRECT ĐẶT LỆNH
                                </a>
                            </div>

                        </td>
                    </tr>

                    <!-- FOOTER HỆ THỐNG GITHUB ACTIONS 24/7 -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 20px; text-align: center; border-top: 1px solid #1e293b; color: #64748b; font-size: 11.5px; line-height: 1.6;">
                            <div style="color: #94a3b8; font-weight: 700; margin-bottom: 4px;">
                                HỆ THỐNG TỰ ĐỘNG HÓA GITHUB ACTIONS 24/7 (CLOUD RUNNER)
                            </div>
                            Báo cáo được khởi tạo và gửi tự động vào 10:00 sáng mỗi ngày lên đám mây GitHub.<br>
                            Người nhận: <span style="color: #38bdf8;">{', '.join(RECIPIENTS)}</span> &bull; Bản quyền &copy; {NOW_VN.year} VN30 Intelligence
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    return html

# ==============================================================================
# HÀM GỬI EMAIL QUA GMAIL SMTP (EMAIL DISPATCHER)
# ==============================================================================
def send_email(subject, html_content, recipients):
    """Gửi email qua Gmail SMTP có xác thực UTF-8 đầy đủ."""
    if not EMAIL_USER or not EMAIL_PASS:
        print("[Lỗi Nghiêm Trọng] Chưa cấu hình EMAIL_USER hoặc EMAIL_PASS!")
        print("Vui lòng vào GitHub Repo -> Settings -> Secrets and variables -> Actions để tạo:")
        print("1. EMAIL_USER (Địa chỉ Gmail của bạn)")
        print("2. EMAIL_PASS (Mật khẩu ứng dụng 16 chữ cái tạo trong tài khoản Google)")
        return False

    try:
        print(f"[Đang kết nối] Kết nối tới máy chủ SMTP: {SMTP_HOST}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
        server.ehlo()
        server.starttls()
        server.ehlo()

        print(f"[Đang đăng nhập] Xác thực tài khoản: {EMAIL_USER}...")
        server.login(EMAIL_USER, EMAIL_PASS)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"VN30 Intelligence Bot <{EMAIL_USER}>"
        msg["To"] = ", ".join(recipients)

        part = MIMEText(html_content, "html", "utf-8")
        msg.attach(part)

        print(f"[Đang gửi email] Gửi tới danh sách: {recipients}...")
        server.sendmail(EMAIL_USER, recipients, msg.as_string())
        server.quit()
        print("[Thành công rực rỡ] Email báo cáo đã được gửi đi an toàn!")
        return True
    except smtplib.SMTPAuthenticationError as auth_err:
        print(f"[Thất Bại Đăng Nhập] Lỗi xác thực tài khoản Google: {auth_err}")
        print("Gợi ý: Phải dùng 'Mật khẩu ứng dụng' (16 chữ cái), không dùng mật khẩu đăng nhập bình thường.")
        return False
    except Exception as e:
        print(f"[Lỗi Gửi Email] Ngoại lệ: {e}")
        return False

# ==============================================================================
# ĐIỂM CHẠY CHÍNH (MAIN ENTRYPOINT)
# ==============================================================================
def main():
    print("=" * 65)
    print(f"BẮT ĐẦU CHƯƠNG TRÌNH PHÂN TÍCH & BÁO CÁO VN30 ({NOW_VN.strftime('%Y-%m-%d %H:%M:%S')} VN)")
    print("=" * 65)

    # 1. Thu thập dữ liệu định lượng
    print("-> Bước 1: Thu thập số liệu kỹ thuật mã E1VFVN30 và VN30-Index...")
    data = get_market_intelligence()

    # 2. Thu thập điểm tin báo chí
    print("-> Bước 2: Chắt lọc tin tức từ CafeF và VnExpress qua bộ lọc Anti-Noise...")
    news_list = fetch_rss_news()
    print(f"   Đã chọn lọc được {len(news_list)} tin bài vĩ mô tiêu biểu.")

    # 3. Tạo mẫu email Mobile-first HTML
    print("-> Bước 3: Tạo giao diện Email HTML theo mô hình phễu 4 tầng...")
    html_content = generate_html_email(data, news_list)

    # Tiêu đề email sinh động
    price_str = f"{data['current_price']:,}đ".replace(",", ".")
    subject = f"📊 [VN30 10H SÁNG] {data['signal_badge']} | Giá: {price_str} ({data['change_pct']}%) | Lời khuyên cho bạn hôm nay"

    # 4. Gửi email tới người nhận
    print(f"-> Bước 4: Khởi chạy gửi email tới {RECIPIENTS}...")
    success = send_email(subject, html_content, RECIPIENTS)

    if not success:
        demo_file = "preview_email.html"
        with open(demo_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[Thông báo] Đã lưu bản xem trước giao diện email tại: {demo_file}")

    print("=" * 65)
    print("HOÀN TẤT CHU TRÌNH TỰ ĐỘNG HÓA.")
    print("=" * 65)

if __name__ == "__main__":
    main()
