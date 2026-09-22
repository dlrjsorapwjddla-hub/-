import datetime
import random
import sqlite3
import streamlit as st

class DBManager:
    def __init__(self, db_name="vocab_app.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT NOT NULL,
                korean TEXT NOT NULL,
                stage INTEGER DEFAULT 0,
                next_date TEXT,
                last_direction INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value INTEGER)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emergency_log (date TEXT PRIMARY KEY, count INTEGER)
        ''')
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ratio', 5)")
        self.conn.commit()

    def add_word(self, english, korean):
        cursor = self.conn.cursor()
        today = datetime.date.today().isoformat()
        cursor.execute(
            "INSERT INTO words (english, korean, stage, next_date, last_direction) VALUES (?, ?, 0, ?, 0)",
            (english.strip(), korean.strip(), today)
        )
        self.conn.commit()

    def get_all_words(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT english, korean FROM words")
        return cursor.fetchall()

    def get_review_words(self):
        cursor = self.conn.cursor()
        today = datetime.date.today().isoformat()
        cursor.execute("SELECT id, english, korean, stage, last_direction FROM words WHERE next_date <= ? AND stage < 7", (today,))
        return cursor.fetchall()

    def update_word_progress(self, word_id, current_stage, current_direction):
        intervals = [1, 3, 7, 30, 90, 180, 365]
        new_stage = current_stage + 1
        cursor = self.conn.cursor()
        if new_stage >= len(intervals):
            cursor.execute("UPDATE words SET stage = 7, next_date = '9999-12-31' WHERE id = ?", (word_id,))
        else:
            next_date = (datetime.date.today() + datetime.timedelta(days=intervals[new_stage])).isoformat()
            next_dir = 1 - current_direction
            cursor.execute(
                "UPDATE words SET stage = ?, next_date = ?, last_direction = ? WHERE id = ?",
                (new_stage, next_date, next_dir, word_id)
            )
        self.conn.commit()

    def get_ratio(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'ratio'")
        row = cursor.fetchone()
        return row[0] if row else 5

    def set_ratio(self, val):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'ratio'", (val,))
        self.conn.commit()

    def use_emergency(self):
        today = datetime.date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("SELECT count FROM emergency_log WHERE date = ?", (today,))
        row = cursor.fetchone()
        count = row[0] if row else 0
        if count < 3:
            cursor.execute("INSERT OR REPLACE INTO emergency_log (date, count) VALUES (?, ?)", (today, count + 1))
            self.conn.commit()
            return True, 3 - (count + 1)
        return False, 0

db = DBManager()

st.set_page_config(page_title="스마트 단어장", page_icon="📱", layout="centered")
menu = st.sidebar.radio("메뉴 선택", ["메인 홈", "단어 추가 및 목록", "복습 퀴즈 게임", "잠금화면 대용 퀴즈"])

if menu == "메인 홈":
    st.title("📱 에빙하우스 단어장 앱")
    reviews = db.get_review_words()
    if reviews:
        st.error(f"🚨 오늘 복습해야 할 단어가 **{len(reviews)}개** 있습니다!")
    else:
        st.success("🎉 오늘 복습할 단어를 모두 마쳤거나 단어가 없습니다!")
    st.info("왼쪽 메뉴를 열어 단어를 추가하거나 퀴즈를 시작하세요.")

elif menu == "단어 추가 및 목록":
    st.title("✍️ 단어 추가 및 리스트")
    with st.form("add_word_form", clear_on_submit=True):
        eng = st.text_input("영어 단어")
        kor = st.text_input("한국어 뜻")
        submitted = st.form_submit_button("단어 추가하기")
        if submitted:
            if eng and kor:
                db.add_word(eng, kor)
                st.success(f"'{eng}' 단어가 추가되었습니다!")
            else:
                st.warning("단어와 뜻을 모두 입력해주세요.")
    st.subheader("📚 나의 단어 리스트")
    words = db.get_all_words()
    if words:
        for idx, (e, k) in enumerate(words, 1):
            st.write(f"**{idx}.** {e} : {k}")
    else:
        st.caption("저장된 단어가 없습니다.")

elif menu == "복습 퀴즈 게임":
    st.title("🎮 영어 단어 맞추기 게임")
    if 'quiz_words' not in st.session_state or st.button("새 게임 시작하기"):
        reviews = db.get_review_words()
        random.shuffle(reviews)
        st.session_state.quiz_words = reviews[:10]
        st.session_state.quiz_index = 0
    words = st.session_state.quiz_words
    idx = st.session_state.quiz_index
    if not words:
        st.info("오늘 복습할 단어가 없습니다.")
    elif idx >= len(words):
        st.balloons()
        st.success("🎉 오늘 단어 복습 게임 완료!")
    else:
        current_word = words[idx]
        w_id, eng, kor, stage, last_dir = current_word
        mode = 1 - last_dir
        if mode == 0:
            st.subheader(f"문제 {idx + 1}/{len(words)}: 영 -> 한")
            st.info(f"👉 **{eng}**의 뜻은 무엇일까요?")
            target_ans = kor
        else:
            st.subheader(f"문제 {idx + 1}/{len(words)}: 한 -> 영")
            st.info(f"👉 **{kor}**의 영어 단어는 무엇일까요?")
            target_ans = eng
        user_ans = st.text_input("정답 입력", key=f"ans_{idx}").strip()
        if st.button("정답 확인", key=f"btn_{idx}"):
            if user_ans.lower() == target_ans.lower():
                db.update_word_progress(w_id, stage, mode)
                st.session_state.quiz_index += 1
                st.success("⭕ 정답입니다!")
                st.rerun()
            else:
                st.error("❌ 정답이 아닙니다.")

elif menu == "잠금화면 대용 퀴즈":
    st.title("🔓 잠금화면 대용 퀴즈")
    ratio = st.slider("영->한 출제 비율 (1~10)", 1, 10, db.get_ratio())
    if st.button("비율 설정 저장"):
        db.set_ratio(ratio)
        st.success("설정이 저장되었습니다.")
    st.write("---")
    words = db.get_review_words()
    if not words:
        st.info("복습할 단어가 없습니다!")
    else:
        if 'lock_word' not in st.session_state:
            st.session_state.lock_word = random.choice(words)
        l_id, l_eng, l_kor, l_stage, l_last_dir = st.session_state.lock_word
        if random.randint(1, 10) <= db.get_ratio():
            st.write(f"❓ 다음 단어의 뜻은? : **{l_eng}**")
            l_target = l_kor
        else:
            st.write(f"❓ 다음 뜻의 영어 단어는? : **{l_kor}**")
            l_target = l_eng
        lock_ans = st.text_input("정답을 입력하면 잠금이 해제됩니다.").strip()
        if st.button("잠금 해제 시도"):
            if lock_ans.lower() == l_target.lower():
                st.balloons()
                st.success("🔓 잠금 해제 성공!")
                del st.session_state.lock_word
                st.rerun()
            else:
                st.error("🔒 정답이 틀렸습니다.")
        if st.button("🚨 비상 탈출 버튼 (일 3회 제한)"):
            success, remain = db.use_emergency()
            if success:
                st.warning(f"비상 해제되었습니다! (남은 횟수: {remain}회)")
                del st.session_state.lock_word
                st.rerun()
            else:
                st.error("오늘 사용 횟수를 초과했습니다!")
