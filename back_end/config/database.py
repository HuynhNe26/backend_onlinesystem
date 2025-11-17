import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="Huynh@2608"
)
cursor = db.cursor()
cursor.execute("DROP DATABASE IF EXISTS online_testing")
cursor.execute("CREATE DATABASE IF NOT EXISTS online_testing")
cursor.execute("USE online_testing")
sql_script = """
-- 1. Package
CREATE TABLE IF NOT EXISTS package (
    id_package INT PRIMARY KEY AUTO_INCREMENT,
    name_package VARCHAR(250) NOT NULL,
    price_month INT NOT NULL,
    description_package TEXT NOT NULL
);

INSERT INTO package (name_package, price_month, description_package) VALUES
('Miễn phí', 0, 'Gói cơ bản với quyền truy cập giới hạn vào các bài kiểm tra'),
('Cơ bản', 99000, 'Gói cơ bản với đầy đủ quyền truy cập và phân tích'),
('Nâng cao', 229000, 'Gói nâng cao với các tính năng nâng cao và hỗ trợ');

-- 2. Classroom
CREATE TABLE IF NOT EXISTS classroom (
    id_class INT PRIMARY KEY AUTO_INCREMENT,
    class_name VARCHAR(100) NOT NULL,
    id_user INT,
    id_department INT
);

INSERT INTO classroom (class_name, id_user, id_department) VALUES
('Toán lớp 1', NULL, 1),
('Toán lớp 2', NULL, 1),
('Vật lý lớp 11', NULL, 2);

-- 3. Users
CREATE TABLE IF NOT EXISTS users (
    id_user INT PRIMARY KEY AUTO_INCREMENT,       
    username VARCHAR(50) NOT NULL UNIQUE,         
    password VARCHAR(255) NOT NULL,              
    fullName VARCHAR(100) NOT NULL,             
    dateOfBirth DATE,                             
    email VARCHAR(100) UNIQUE,                    
    role VARCHAR(20),
    login_time DATETIME,                          
    logout_time DATETIME,                       
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
    status VARCHAR(20),                           
    id_class INT,                                 
    gender VARCHAR(10),                       
    avatar VARCHAR(255),             
    id_package INT,                               
    start_package DATETIME,                       
    end_package DATETIME,                        
    level INT,
    FOREIGN KEY (id_class) REFERENCES classroom(id_class),
    FOREIGN KEY (id_package) REFERENCES package(id_package)
);

ALTER TABLE users MODIFY COLUMN role VARCHAR(20);

INSERT INTO users (username, password, fullName, dateOfBirth, email, role, status, id_class, gender, id_package, start_package, end_package, level) VALUES
('hocsinh1', 'matkhau1', 'Nguyễn Văn An', '2007-01-01', 'an.nguyen@example.com', 'học sinh', 'Đang hoạt động', 1, 'Nam', 1, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 1),
('huynhnguyen', '1234', 'Nguyễn Hoàng Huynh', '2005-08-26', 'huynhnguyen@gmail.com', 'quản trị viên', 'Đang hoạt động', NULL, 'Nam', 2, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 2),
('baouyen', '1234', 'Lê Phạm Bảo Uyên', '2005-09-04', 'baouyen@gmail.com', 'quản trị viên', 'Đang hoạt động', NULL, 'Nữ', 2, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 2),
('kiettran', '1234', 'Trần Diệp Anh Kiệt', '2005-08-23', 'kietran@gmail.com', 'quản trị viên', 'Đang hoạt động', NULL, 'Nam', 2, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 2),
('huukien', '1234', 'Phạm Hữu Kiên', '2005-06-01 ', 'huukien@gmail.com', 'quản trị viên', 'Đang hoạt động', NULL, 'Nam', 2, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 2),
('minhvu', '1234', 'Phùng Minh Vũ', '2005-08-01', 'minhvu@gmail.com', 'quản trị viên', 'Đang hoạt động', NULL, 'Nam', 2, '2025-10-01 00:00:00', '2026-10-01 00:00:00', 2);

-- 4. Department
CREATE TABLE IF NOT EXISTS department (
    id_department INT PRIMARY KEY AUTO_INCREMENT, 
    name_department VARCHAR(100) NOT NULL,        
    id_user INT,                                  
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
    status VARCHAR(20),
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

INSERT INTO department (name_department, id_user, status) VALUES
('Toán học', 2, 'Đang hoạt động'),
('Vật lý', 2, 'Đang hoạt động');

-- 5. Categories
CREATE TABLE IF NOT EXISTS categories (
    id_category INT PRIMARY KEY AUTO_INCREMENT,
    name_category VARCHAR(100) NOT NULL,
    id_user INT NOT NULL,
    id_classroom INT NOT NULL,
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

INSERT INTO categories (name_category, id_user, id_classroom) VALUES
('Toán', 2, 1),
('Vật Lý', 2, 1),
('Tiếng Anh', 2, 1);

-- 6. Difficulty
CREATE TABLE IF NOT EXISTS difficulty (
    id_diff INT PRIMARY KEY AUTO_INCREMENT,
    difficulty VARCHAR(100)
);

INSERT INTO difficulty (difficulty) VALUES
('Dễ'),
('Trung bình'),
('Khó');

-- 7. Questions
CREATE TABLE IF NOT EXISTS questions (
    id_ques INT PRIMARY KEY AUTO_INCREMENT,
    id_category INT NOT NULL,
    ques_text VARCHAR(255),
    ans_a VARCHAR(100) NOT NULL,
    ans_b VARCHAR(100) NOT NULL,
    ans_c VARCHAR(100),
    ans_d VARCHAR(100),
    correct_ans VARCHAR(100),
    point FLOAT NOT NULL,
    explanation TEXT NOT NULL,
    id_diff INT NOT NULL,
    id_user INT NOT NULL,
    FOREIGN KEY (id_category) REFERENCES categories(id_category),
    FOREIGN KEY (id_diff) REFERENCES difficulty(id_diff),
    FOREIGN KEY (id_user) REFERENCES users(id_user)
);

INSERT INTO questions (id_category, ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation, id_diff, id_user) VALUES
(1, 'Giải phương trình: x + 5 = 12', '7', '6', '17', '8', '7', 1.0, 'Trừ 5 hai vế: x = 12 - 5 = 7.', 1, 2),
(1, 'Giải bất phương trình: x - 3 > 4', 'x > 7', 'x < 7', 'x > 1', 'x < 1', 'x > 7', 1.0, 'Cộng 3 hai vế: x > 4 + 3 = 7.', 1, 2),
(1, 'Tính giá trị biểu thức: 2x + 3 khi x=4', '11', '10', '14', '8', '11', 1.0, 'Thay x=4: 24 + 3 = 8 + 3 = 11.', 1, 2),
(1, 'Phân tích đa thức: x^2 - 4', '(x-2)(x+2)', '(x-4)(x+1)', '(x-1)(x+4)', '(x^2-2)', '(x-2)(x+2)', 1.0, 'Là hiệu hai bình phương: x^2 - 2^2 = (x-2)(x+2).', 1, 2),
(1, 'Giải phương trình: 2x = 10', '5', '20', '2', '0', '5', 1.0, 'Chia hai vế cho 2: x = 10/2 = 5.', 1, 2),
(1, 'Tìm nghiệm của: x - 7 = 0', '7', '0', '-7', '1', '7', 1.0, 'Cộng 7: x = 7.', 1, 2),
(1, 'Biểu thức nào tương đương với 3(x + 2)?', '3x + 6', '3x + 2', 'x + 6', '3x', '3x + 6', 1.0, 'Phân phối: 3x + 32 = 3x + 6.', 1, 2),
(1, 'Giải: 4x + 2 = 18', '4', '5', '3', '20', '4', 1.0, 'Trừ 2: 4x=16, chia 4: x=4.', 1, 2),
(1, 'Tính: -2x khi x=-3', '6', '-6', '1', '-1', '6', 1.0, '-2(-3) = 6.', 1, 2),
(1, 'Phương trình tuyến tính là gì?', 'ax + b = 0', 'ax^2 + b = 0', 'a/x = b', 'ax^3 = 0', 'ax + b = 0', 1.0, 'Phương trình bậc nhất dạng ax + b = 0.', 1, 2),
(1, 'Giải phương trình: x^2 - 5x + 6 = 0', 'x=2, x=3', 'x=1, x=6', 'x=0, x=5', 'x=-2, x=-3', 'x=2, x=3', 1.0, 'Phân tích: (x-2)(x-3)=0, nghiệm x=2 hoặc x=3.', 2, 2),
(1, 'Tìm delta của x^2 + 4x + 4 = 0', '0', '16', '8', '4', '0', 1.0, 'Delta = b^2 - 4ac = 16 - 16 = 0.', 2, 2),
(1, 'Giải hệ: x + y = 5, x - y = 1', 'x=3, y=2', 'x=4, y=1', 'x=2, y=3', 'x=5, y=0', 'x=3, y=2', 1.0, 'Cộng hai phương trình: 2x=6 => x=3, thay y=2.', 2, 2),
(1, 'Căn bậc hai của 25 là?', '5', '25', '10', '-5', '5', 1.0, 'sqrt(25)=5 (chính).', 2, 2),
(1, 'Tính (a+b)^2 khi a=2, b=3', '25', '10', '13', '5', '25', 1.0, '(2+3)^2 = 5^2 = 25.', 2, 2),
(1, 'Giải: x^2 = 9', 'x=3 hoặc x=-3', 'x=3', 'x=9', 'x=0', 'x=3 hoặc x=-3', 1.0, 'x = ±3.', 2, 2),
(1, 'Phân tích x^2 + 5x + 6', '(x+2)(x+3)', '(x+1)(x+6)', '(x+5)(x+1)', '(x+4)(x+1.5)', '(x+2)(x+3)', 1.0, 'Tìm hai số cộng 5 nhân 6: 2 và 3.', 2, 2),
(1, 'Tìm nghiệm: 2x^2 - 8 = 0', 'x=2 hoặc x=-2', 'x=4', 'x=0', 'x=8', 'x=2 hoặc x=-2', 1.0, '2x^2=8 => x^2=4 => x=±2.', 2, 2),
(1, 'Hệ phương trình: 2x + y = 7, x + y = 4', 'x=3, y=1', 'x=2, y=3', 'x=1, y=5', 'x=4, y=-1', 'x=3, y=1', 1.0, 'Trừ: x=3, thay y=1.', 2, 2),
(1, 'Delta của x^2 - 2x - 3 =0', '16', '4', '-12', '1', '16', 1.0, '4 + 12 =16.', 2, 2),
(1, 'Sin 30° bằng bao nhiêu?', '1/2', '√3/2', '1', '0', '1/2', 1.0, 'Sin 30° = 0.5 = 1/2.', 3, 2),
(1, 'Cos 60° = ?', '1/2', '√3/2', '1', '0', '1/2', 1.0, 'Cos 60° = 0.5.', 3, 2),
(1, 'Định lý Pythagoras: a^2 + b^2 = ?', 'c^2', 'a^2', 'b^2', 'ab', 'c^2', 1.0, 'Trong tam giác vuông, bình phương cạnh huyền bằng tổng bình phương hai cạnh góc vuông.', 3, 2),
(1, 'Tìm chiều dài đường chéo hình vuông cạnh 5', '5√2', '10', '25', '5', '5√2', 1.0, 'Áp dụng Pythagoras: √(25+25)=√50=5√2.', 3, 2),
(1, 'Tan 45° = ?', '1', '0', '∞', '√2', '1', 1.0, 'Tan 45° = 1.', 3, 2),
(1, 'Diện tích tam giác với đáy 6, cao 4?', '12', '24', '10', '8', '12', 1.0, ' (1/2)64=12.', 3, 2),
(1, 'Chu vi hình tròn bán kính r?', '2πr', 'πr^2', '4r', 'πr', '2πr', 1.0, 'Chu vi = 2πr.', 3, 2),
(1, 'Giải bất phương trình: x^2 - 4 > 0', 'x < -2 hoặc x > 2', ' -2 < x < 2', 'x > 0', 'x < 0', 'x < -2 hoặc x > 2', 1.0, '(x-2)(x+2)>0, nghiệm ngoài khoảng.', 3, 2),
(1, 'Tìm sin nếu cos=3/5 trong tam giác vuông', '4/5', '3/5', '5/4', '5/3', '4/5', 1.0, 'Áp dụng Pythagoras, cạnh đối =4, sin=4/5.', 3, 2),
(1, 'Số đo góc trong tam giác đều?', '60°', '90°', '45°', '120°', '60°', 1.0, 'Tam giác đều có ba góc 60°.', 3, 2),
(2, 'Lực hấp dẫn là gì?', 'Lực kéo vật xuống đất', 'Lực đẩy vật lên', 'Lực xoay vật', 'Lực dừng vật', 'Lực kéo vật xuống đất', 1.0, 'Lực hấp dẫn là lực kéo các vật về phía Trái Đất.', 1, 2),
(2, 'Ánh sáng di chuyển như thế nào?', 'Thẳng', 'Cong', 'Zigzag', 'Vòng tròn', 'Thẳng', 1.0, 'Ánh sáng di chuyển theo đường thẳng.', 1, 2),
(2, 'Nước sôi ở nhiệt độ bao nhiêu?', '100°C', '0°C', '50°C', '200°C', '100°C', 1.0, 'Nước sôi ở 100 độ C.', 1, 2),
(2, 'Âm thanh truyền qua gì?', 'Không khí', 'Chân không', 'Đá', 'Nước', 'Không khí', 1.0, 'Âm thanh truyền qua không khí.', 1, 2),
(2, 'Trọng lực do ai phát hiện?', 'Newton', 'Einstein', 'Galileo', 'Tesla', 'Newton', 1.0, 'Isaac Newton phát hiện lực hấp dẫn.', 1, 2),
(2, 'Đơn vị đo lực là gì?', 'Newton', 'Joule', 'Watt', 'Ampere', 'Newton', 1.0, 'Đơn vị đo lực là Newton.', 1, 2),
(2, 'Năng lượng mặt trời từ đâu?', 'Mặt trời', 'Trái đất', 'Mặt trăng', 'Sao', 'Mặt trời', 1.0, 'Năng lượng mặt trời từ Mặt Trời.', 1, 2),
(2, 'Điện từ đâu?', 'Pin', 'Gió', 'Nước', 'Lửa', 'Pin', 1.0, 'Điện có thể từ pin.', 1, 2),
(2, 'Tốc độ là gì?', 'Khoảng cách trên thời gian', 'Thời gian trên khoảng cách', 'Lực trên khối lượng', 'Năng lượng trên công suất', 'Khoảng cách trên thời gian', 1.0, 'Tốc độ = khoảng cách / thời gian.', 1, 2),
(2, 'Màu cơ bản là gì?', 'Đỏ, xanh, vàng', 'Đen, trắng', 'Vàng, cam', 'Tím, hồng', 'Đỏ, xanh, vàng', 1.0, 'Màu cơ bản là đỏ, xanh, vàng.', 1, 2),
(2, 'Công thức lực là gì?', 'F = m*a', 'F = m/v', 'F = v*t', 'F = e/m', 'F = m*a', 1.0, 'Lực = khối lượng nhân gia tốc.', 2, 2),
(2, 'Định luật bảo toàn năng lượng?', 'Năng lượng không mất', 'Năng lượng tăng', 'Năng lượng giảm', 'Năng lượng biến mất', 'Năng lượng không mất', 1.0, 'Năng lượng không tạo ra hay mất đi.', 2, 2),
(2, 'Tần số là gì?', 'Số dao động trên giây', 'Khoảng cách', 'Thời gian', 'Lực', 'Số dao động trên giây', 1.0, 'Tần số là số dao động mỗi giây.', 2, 2),
(2, 'Điện trở là gì?', 'R = V/I', 'R = I/V', 'R = V*I', 'R = V+I', 'R = V/I', 1.0, 'Điện trở = điện áp / dòng điện.', 2, 2),
(2, 'Gia tốc trọng trường?', '9.8 m/s²', '10 m/s²', '8 m/s²', '9 m/s²', '9.8 m/s²', 1.0, 'Gia tốc trọng trường là 9.8 m/s².', 2, 2),
(2, 'Công suất là gì?', 'P = W/t', 'P = t/W', 'P = W*t', 'P = W+t', 'P = W/t', 1.0, 'Công suất = công / thời gian.', 2, 2),
(2, 'Sóng ngang là gì?', 'Dao động vuông góc', 'Dao động song song', 'Dao động tròn', 'Dao động thẳng', 'Dao động vuông góc', 1.0, 'Sóng ngang dao động vuông góc với hướng lan.', 2, 2),
(2, 'Định luật Ohm?', 'V = I*R', 'V = I/R', 'V = I+R', 'V = R/I', 'V = I*R', 1.0, 'Điện áp = dòng điện nhân điện trở.', 2, 2),
(2, 'Năng lượng kinetic?', '1/2 m v²', 'm v', 'm v²', '1/2 m v', '1/2 m v²', 1.0, 'Năng lượng động học = 1/2 mv².', 2, 2),
(2, 'Áp suất là gì?', 'P = F/A', 'P = A/F', 'P = F*A', 'P = F+A', 'P = F/A', 1.0, 'Áp suất = lực / diện tích.', 2, 2),
(2, 'Định luật Kepler thứ nhất?', 'Quỹ đạo elip', 'Quỹ đạo tròn', 'Quỹ đạo vuông', 'Quỹ đạo thẳng', 'Quỹ đạo elip', 1.0, 'Hành tinh quay quanh Mặt Trời theo elip.', 3, 2),
(2, 'Thuyết tương đối?', 'E = mc²', 'E = m/c²', 'E = m c', 'E = m + c²', 'E = mc²', 1.0, 'Năng lượng = khối lượng nhân bình phương tốc độ ánh sáng.', 3, 2),
(2, 'Sóng điện từ?', 'Ánh sáng', 'Âm thanh', 'Nước', 'Gió', 'Ánh sáng', 1.0, 'Ánh sáng là sóng điện từ.', 3, 2),
(2, 'Hiệu ứng Doppler?', 'Tần số thay đổi khi nguồn di chuyển', 'Tần số cố định', 'Tần số giảm', 'Tần số tăng', 'Tần số thay đổi khi nguồn di chuyển', 1.0, 'Hiệu ứng Doppler thay đổi tần số khi nguồn hoặc người nghe di chuyển.', 3, 2),
(2, 'Định luật Faraday?', 'Cảm ứng điện từ', 'Cảm ứng từ', 'Cảm ứng nhiệt', 'Cảm ứng áp', 'Cảm ứng điện từ', 1.0, 'Dòng điện cảm ứng từ thay đổi từ thông.', 3, 2),
(2, 'Lượng tử năng lượng?', 'E = h f', 'E = h / f', 'E = h + f', 'E = f / h', 'E = h f', 1.0, 'Năng lượng photon = h tần số.', 3, 2),
(2, 'Lực Lorentz?', 'F = q (v x B)', 'F = q v B', 'F = q / (v B)', 'F = q + v B', 'F = q (v x B)', 1.0, 'Lực trên hạt tích điện trong từ trường.', 3, 2),
(2, 'Nguyên lý bất định Heisenberg?', 'Không xác định chính xác vị trí và động lượng', 'Xác định chính xác', 'Chỉ vị trí', 'Chỉ động lượng', 'Không xác định chính xác vị trí và động lượng', 1.0, 'Không thể biết chính xác vị trí và động lượng cùng lúc.', 3, 2),
(2, 'Bước sóng de Broglie?', 'λ = h / p', 'λ = p / h', 'λ = h p', 'λ = h + p', 'λ = h / p', 1.0, 'Bước sóng = h / động lượng.', 3, 2),
(2, 'Định luật Hooke?', 'F = -k x', 'F = k x', 'F = k / x', 'F = x / k', 'F = -k x', 1.0, 'Lực lò xo = -hằng số nhân độ giãn.', 3, 2),
(3, 'Hello nghĩa là gì?', 'Xin chào', 'Tạm biệt', 'Cảm ơn', 'Xin lỗi', 'Xin chào', 1.0, 'Hello là lời chào.', 1, 2),
(3, 'Apple là gì?', 'Quả táo', 'Quả chuối', 'Quả cam', 'Quả lê', 'Quả táo', 1.0, 'Apple là quả táo.', 1, 2),
(3, 'Color của sky?', 'Blue', 'Red', 'Green', 'Yellow', 'Blue', 1.0, 'Bầu trời màu xanh.', 1, 2),
(3, 'Number one?', 'One', 'Two', 'Three', 'Four', 'One', 1.0, 'Số một là one.', 1, 2),
(3, 'Dog là gì?', 'Con chó', 'Con mèo', 'Con chim', 'Con cá', 'Con chó', 1.0, 'Dog là con chó.', 1, 2),
(3, 'Thank you nghĩa là?', 'Cảm ơn', 'Xin chào', 'Tạm biệt', 'Xin lỗi', 'Cảm ơn', 1.0, 'Thank you là cảm ơn.', 1, 2),
(3, 'Water là gì?', 'Nước', 'Lửa', 'Gió', 'Đất', 'Nước', 1.0, 'Water là nước.', 1, 2),
(3, 'Yes nghĩa là?', 'Có', 'Không', 'Có lẽ', 'Chưa', 'Có', 1.0, 'Yes là có.', 1, 2),
(3, 'Book là gì?', 'Sách', 'Bút', 'Giấy', 'Bàn', 'Sách', 1.0, 'Book là sách.', 1, 2),
(3, 'Red là màu gì?', 'Đỏ', 'Xanh', 'Vàng', 'Đen', 'Đỏ', 1.0, 'Red là đỏ.', 1, 2),
(3, 'I am là gì?', 'Tôi là', 'Bạn là', 'Anh ấy là', 'Cô ấy là', 'Tôi là', 1.0, 'I am nghĩa là tôi là.', 2, 2),
(3, 'He runs fast. Runs là gì?', 'Chạy', 'Đi', 'Nhảy', 'Bơi', 'Chạy', 1.0, 'Runs là chạy.', 2, 2),
(3, 'The cat is on the table. On nghĩa là?', 'Trên', 'Dưới', 'Bên', 'Trong', 'Trên', 1.0, 'On là trên.', 2, 2),
(3, 'She likes apples. Likes nghĩa là?', 'Thích', 'Ghét', 'Ăn', 'Uống', 'Thích', 1.0, 'Likes là thích.', 2, 2),
(3, 'We go to school. Go nghĩa là?', 'Đi', 'Ở', 'Về', 'Đến', 'Đi', 1.0, 'Go là đi.', 2, 2),
(3, 'It is raining. Is raining nghĩa là?', 'Đang mưa', 'Mưa', 'Sẽ mưa', 'Đã mưa', 'Đang mưa', 1.0, 'Is raining là đang mưa.', 2, 2),
(3, 'They play football. Play nghĩa là?', 'Chơi', 'Ăn', 'Uống', 'Ngủ', 'Chơi', 1.0, 'Play là chơi.', 2, 2),
(3, 'This is my book. My nghĩa là?', 'Của tôi', 'Của bạn', 'Của anh ấy', 'Của cô ấy', 'Của tôi', 1.0, 'My là của tôi.', 2, 2),
(3, 'Bird can fly. Can nghĩa là?', 'Có thể', 'Phải', 'Nên', 'Sẽ', 'Có thể', 1.0, 'Can là có thể.', 2, 2),
(3, 'I eat breakfast. Eat nghĩa là?', 'Ăn', 'Uống', 'Nấu', 'Mua', 'Ăn', 1.0, 'Eat là ăn.', 2, 2),
(3, 'What is the past tense of go?', 'Went', 'Goed', 'Gone', 'Going', 'Went', 1.0, 'Quá khứ của go là went.', 3, 2),
(3, 'If it rains, we will stay home. Đây là câu gì?', 'Điều kiện loại 1', 'Điều kiện loại 2', 'Điều kiện loại 3', 'Không phải điều kiện', 'Điều kiện loại 1', 1.0, 'Đây là câu điều kiện loại 1.', 3, 2),
(3, 'The book was read by him. Đây là gì?', 'Bị động', 'Chủ động', 'Hiện tại', 'Quá khứ', 'Bị động', 1.0, 'Đây là câu bị động.', 3, 2),
(3, 'She has been to Paris. Has been là gì?', 'Hiện tại hoàn thành tiếp diễn', 'Hiện tại hoàn thành', 'Quá khứ hoàn thành', 'Tương lai', 'Hiện tại hoàn thành', 1.0, 'Has been là hiện tại hoàn thành.', 3, 2),
(3, 'Opposite of happy?', 'Sad', 'Angry', 'Tired', 'Hungry', 'Sad', 1.0, 'Trái nghĩa của happy là sad.', 3, 2),
(3, 'He asked if I was coming. Đây là gì?', 'Câu gián tiếp', 'Câu trực tiếp', 'Câu hỏi', 'Câu khẳng định', 'Câu gián tiếp', 1.0, 'Đây là câu tường thuật gián tiếp.', 3, 2),
(3, 'The more you study, the better you get. Đây là?', 'So sánh kép', 'So sánh hơn', 'So sánh nhất', 'Không so sánh', 'So sánh kép', 1.0, 'Đây là cấu trúc the more... the better.', 3, 2),
(3, 'I wish I could fly. Đây là?', 'Điều ước không thực', 'Điều ước thực', 'Khẳng định', 'Phủ định', 'Điều ước không thực', 1.0, 'Wish + could là điều ước không thực ở hiện tại.', 3, 2),
(3, 'Neither John nor Mary likes it. Neither...nor nghĩa là?', 'Không...cũng không', 'Hoặc...hoặc', 'Và', 'Nhưng', 'Không...cũng không', 1.0, 'Neither...nor là không cái này cũng không cái kia.', 3, 2),
(3, 'It is time we went home. Đây là?', 'Cấu trúc it is time', 'Hiện tại', 'Quá khứ', 'Tương lai', 'Cấu trúc it is time', 1.0, 'It is time + past tense nghĩa là đã đến lúc.', 3, 2);
-- 8. Exam
CREATE TABLE IF NOT EXISTS exam (
    id_ex INT PRIMARY KEY AUTO_INCREMENT,
    total_ques INT NOT NULL,
    duration INT NOT NULL,       -- Số phút
    name_ex VARCHAR(50),
    id_user INT NOT NULL,
    id_category INT,             -- Liên kết môn học
    id_class INT,                -- Liên kết lớp
    exam_cat VARCHAR(50) DEFAULT 'draft', -- draft/published
    start_time DATETIME,
    end_time DATETIME,
    FOREIGN KEY (id_user) REFERENCES users(id_user),
    FOREIGN KEY (id_category) REFERENCES categories(id_category),
    FOREIGN KEY (id_class) REFERENCES classroom(id_class)
);


INSERT INTO exam (total_ques, duration, name_ex, id_user, id_category, id_class, exam_cat, start_time, end_time) VALUES
(10, 60, 'Kiểm tra giữa kỳ Toán', 2, 1, 1, 'published', '2025-10-05 08:00:00', '2025-10-05 09:00:00'),
(15, 90, 'Kiểm tra cuối kỳ Vật lý', 2, 2, 2, 'published', '2025-10-06 08:00:00', '2025-10-06 09:30:00');

-- 9. Exam_Question
CREATE TABLE IF NOT EXISTS exam_question (
    id_inter INT PRIMARY KEY AUTO_INCREMENT,
    id_ex INT NOT NULL,
    id_ques INT NOT NULL,
    FOREIGN KEY (id_ex) REFERENCES exam(id_ex),
    FOREIGN KEY (id_ques) REFERENCES questions(id_ques)
);

INSERT INTO exam_question (id_ex, id_ques) VALUES
(1, 1),
(2, 2);

-- 10. Answer
CREATE TABLE IF NOT EXISTS answer (
    id_ans INT PRIMARY KEY AUTO_INCREMENT,
    id_ques INT NOT NULL,
    answer VARCHAR(255) NOT NULL,
    id_ex INT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    id_user INT NOT NULL,
    id_inter INT NOT NULL,
    create_at DATETIME NOT NULL,
    FOREIGN KEY (id_ques) REFERENCES questions(id_ques),
    FOREIGN KEY (id_ex) REFERENCES exam(id_ex),
    FOREIGN KEY (id_user) REFERENCES users(id_user),
    FOREIGN KEY (id_inter) REFERENCES exam_question(id_inter)
);

INSERT INTO answer (id_ques, answer, id_ex, is_correct, id_user, id_inter, create_at) VALUES
(1, '4', 1, TRUE, 1, 1, '2025-10-03 10:00:00'),
(2, 'F = ma', 2, FALSE, 1, 2, '2025-10-03 10:05:00');

-- 11. Results
CREATE TABLE IF NOT EXISTS results (
    id_result INT PRIMARY KEY AUTO_INCREMENT,
    id_user INT NOT NULL,
    id_ex INT NOT NULL,
    score INT NOT NULL,
    total_correct FLOAT NOT NULL,
    start_time DATETIME NOT NULL,
    completed_time DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL,
    exam_cat VARCHAR(50) NOT NULL,
    FOREIGN KEY (id_user) REFERENCES users(id_user),
    FOREIGN KEY (id_ex) REFERENCES exam(id_ex)
);

INSERT INTO results (id_user, id_ex, score, total_correct, start_time, completed_time, status, exam_cat) VALUES
(1, 1, 80, 8.0, '2025-10-03 11:00:00', '2025-10-03 11:00:00', 'Hoàn thành', 'Kiểm tra'),
(1, 2, 60, 6.0, '2025-10-03 11:00:00', '2025-10-03 12:00:00', 'Hoàn thành', 'Luyện bài');

-- 14. Payment
CREATE TABLE IF NOT EXISTS payment (
    id_payment INT PRIMARY KEY AUTO_INCREMENT,
    id_user INT NOT NULL,
    id_package INT NOT NULL,
    amount FLOAT NOT NULL,
    duration VARCHAR(100),
    status VARCHAR(100),
    payment VARCHAR(100),
    code VARCHAR(100),
    FOREIGN KEY (id_user) REFERENCES users(id_user),
    FOREIGN KEY (id_package) REFERENCES package(id_package)
);

INSERT INTO payment (id_user, id_package, amount, duration, status, payment, code) VALUES
(1, 1, 200000, '1 tháng', 'Hoàn thành', 'Thẻ tín dụng', 'PAY123'),
(2, 2, 400000, '1 tháng', 'Hoàn thành', 'Ví điện tử', 'PAY456');
"""

for statement in sql_script.split(";"):
    if statement.strip():
        cursor.execute(statement)
db.commit()
cursor.close()
db.close()
print('Cơ sở dữ liệu đã được cập nhật!')