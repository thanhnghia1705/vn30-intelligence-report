# 📈 Hệ Thống Báo Cáo Tự Động Đầu Tư Chứng Chỉ Quỹ VN30 (E1VFVN30 / VNDirect)

Hệ thống tự động chạy trên đám mây **GitHub Actions 24/7** (hoàn toàn miễn phí, không cần mở máy tính).
Hàng ngày vào lúc **10:00 sáng (giờ Việt Nam)**, hệ thống sẽ:
1. Thu thập dữ liệu khớp lệnh, xu hướng nến ngày, MA20, MA50, RSI-14 của mã quỹ **E1VFVN30** và chỉ số **VN30-Index**.
2. Quét tin tức vĩ mô và thị trường từ các nguồn chính thống (**CafeF**, **VnExpress**).
3. Đánh giá tín hiệu hành động: **Mua gom / Tích lũy đều (DCA) / Nắm giữ / Tỉa bớt**.
4. Xuất bản email HTML chuẩn Mobile-First gửi thẳng vào hộp thư **nguyenthanhnghia1705@gmail.com**.

---

## 📁 Cấu Trúc Thư Mục

```text
.
├── .github/
│   └── workflows/
│       └── daily.yml      # Cấu hình GitHub Actions chạy tự động lúc 10h15 sáng hàng ngày
├── report.py              # Bộ mã nguồn Python cào dữ liệu, phân tích & gửi mail
├── requirements.txt       # Danh sách thư viện Python
└── preview_email.html     # Bản xem trước giao diện email trên trình duyệt
```

---

## 🚀 Các Bước Cài Đặt Trong 3 Phút

### Bước 1: Tạo Mật khẩu ứng dụng Gmail (App Password)
1. Đăng nhập tài khoản Google của bạn -> [Bảo mật tài khoản Google](https://myaccount.google.com/security).
2. Đảm bảo đã bật **Xác minh 2 bước** (2-Step Verification).
3. Gõ tìm kiếm mục **"Mật khẩu ứng dụng"** (App Passwords) hoặc truy cập trực tiếp: `https://myaccount.google.com/apppasswords`.
4. Tạo một tên ứng dụng (ví dụ: `GitHub Report`), Google sẽ hiển thị chuỗi 16 chữ cái (dạng `abcd efgh ijkl mnop`). Lưu lại chuỗi này.

### Bước 2: Đẩy Code lên GitHub Repo
1. Đăng nhập [GitHub.com](https://github.com), bấm **New repository** (đặt tên: `vn30-reporter`, chọn chế độ **Private** để bảo mật thông tin).
2. Tải toàn bộ các file trong thư mục này lên Repo.

### Bước 3: Cài đặt GitHub Secrets (Bảo mật tài khoản)
Tại trang Repo trên GitHub:
1. Vào tab **Settings** -> Mục **Secrets and variables** (cột trái) -> Chọn **Actions**.
2. Bấm nút xanh **New repository secret**:
   - `EMAIL_USER`: Nhập địa chỉ Gmail của bạn (dùng để gửi thư, ví dụ: `your_email@gmail.com`).
   - `EMAIL_PASS`: Nhập chuỗi 16 chữ cái mật khẩu ứng dụng vừa tạo ở Bước 1.
   - `EMAIL_RECEIVER`: (Tùy chọn) `nguyenthanhnghia1705@gmail.com` (Hệ thống đã mặc định sẵn).

### Bước 4: Chạy thử ngay lập tức (Test 1 Click)
1. Vào tab **Actions** trên GitHub.
2. Bấm vào tên workflow: **VN30 Daily Intelligence Email Report**.
3. Nhìn sang bên phải thấy nút **Run workflow** -> Bấm nút xanh **Run workflow**.
4. Chờ 30 giây -> Mở hòm thư Gmail của bạn để chiêm ngưỡng bản báo cáo đầu tiên!
