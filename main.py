import os
import shutil
import atexit
import time
from gtts import gTTS
import flet as ft
import firebase_admin
from firebase_admin import credentials, db
import requests
import json
import re
from playsound import playsound 

def safe_dict(data):
    if data is None: 
        return {}
    if isinstance(data, list): 
        # 리스트라면 [0, 1, 2] 인덱스를 문자열 키 "0", "1", "2"로 바꿈
        return {str(i): v for i, v in enumerate(data) if v is not None}
    if isinstance(data, dict): 
        return data
    return {}

GROQ_API_KEY = "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"
TARGET_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- 임시 폴더 설정 및 종료 시 삭제 로직 ---
TEMP_FOLDER = "temp_voices"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

def cleanup_temp_files():
    if os.path.exists(TEMP_FOLDER):
        try:
            shutil.rmtree(TEMP_FOLDER)
            print("임시 음성 파일이 모두 삭제되었습니다.")
        except Exception as e:
            print(f"파일 삭제 중 오류 발생: {e}")

atexit.register(cleanup_temp_files)

# 1. Firebase 초기화
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("naratmal.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://naratmalssami-ed385-default-rtdb.firebaseio.com'
        })
    except Exception as e:
        print(f"Firebase 초기화 에러: {e}")

# 파이어베이스 데이터를 안전하게 딕셔너리로 변환하는 헬퍼 함수
def safe_dict(data):
    if data is None: return {}
    if isinstance(data, dict): return data
    if isinstance(data, list): return {str(i): v for i, v in enumerate(data) if v is not None}
    return {}

def main(page: ft.Page):
    page.title = "나랏말싸미:꿈틀이의 문해력 키우기"
    page.window_width = 1800
    page.window_height = 900
    page.padding = 0
    page.spacing = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    # --- 입력 필드 정의 (로그인 정보) ---
    school_field = ft.TextField(label="학교명", width=300, bgcolor="white")
    grade_field = ft.Dropdown(
        label="학년", width=145, bgcolor="white",
        options=[ft.dropdown.Option(f"{i}학년") for i in range(1, 7)],
    )
    class_field = ft.TextField(label="반", width=145, bgcolor="white")
    name_field = ft.TextField(label="이름", width=300, bgcolor="white")
    pw_field = ft.TextField(label="비밀번호", width=300, password=True, can_reveal_password=True, bgcolor="white")
    
    role_selection = ft.RadioGroup(content=ft.Row([
        ft.Radio(value="학생", label="학생"),
        ft.Radio(value="교사", label="교사")
    ], alignment="center"), value="학생")

# ==========================================
    # [1] 교사 대시보드 화면 함수
    # ==========================================
    def show_teacher_dashboard():
        page.clean()

        def play_voice(text):
            try:
                import os, time, tempfile, ctypes
                from gtts import gTTS
                temp_dir = tempfile.gettempdir()
                filename = f"v_{int(time.time() * 1000)}.mp3"
                full_path = os.path.join(temp_dir, filename)
                tts = gTTS(text=text, lang='ko')
                tts.save(full_path)
                alias = f"v_{int(time.time() * 1000)}"
                ctypes.windll.winmm.mciSendStringW(f'open "{full_path}" type mpegvideo alias {alias}', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            except Exception as e:
                print(f"음성 재생 오류 상세: {e}")

        def get_student_management_view():
            all_users = safe_dict(db.reference('users').get())
            student_rows = []
            
            def make_analyze_func(student_uid, st_name, st_scores):
                def do_analyze(e):
                    e.control.text = "분석 중..."
                    e.control.disabled = True
                    page.update()
                    prompt = f"초등학교 학생 '{st_name}'의 활동 점수입니다. 맞춤법:{st_scores.get('spelling',0)}, 문해력:{st_scores.get('literacy',0)}, 글쓰기:{st_scores.get('writing',0)}, 집현전(독서):{st_scores.get('jiphyeon',0)}. 이 점수를 바탕으로 이 학생의 강점과 보완할 점을 다정한 선생님의 말투로 3줄 이내로 분석해줘."
                    try:
                        payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a helpful AI assistant for elementary school teachers. 반드시 자연스럽고 완벽한 한국어(표준어)로만 작성하세요. 다정하고 전문적인 교사의 말투를 사용하세요. 오타나 어색한 번역투 문장이 없도록 철저히 검수하세요."}, {"role": "user", "content": prompt}]}
                        res = requests.post(TARGET_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"})
                        report = res.json()['choices'][0]['message']['content']
                        db.reference(f"users/{student_uid}").update({'ai_report': report})
                        
                        content_area.content = ft.Column([ft.Text("[학생 관리]", size=40, weight="bold", color="#5D4037"), ft.Divider(), get_student_management_view()], scroll="always", expand=True)
                        page.update()
                    except Exception as ex:
                        e.control.text = "🤖 AI 분석하기"
                        e.control.disabled = False
                        page.snack_bar = ft.SnackBar(ft.Text(f"오류 발생: {ex}")); page.snack_bar.open = True; page.update()
                return do_analyze

            for uid, data in all_users.items():
                if isinstance(data, dict) and data.get('role') == '학생' and data.get('school') == school_field.value and data.get('grade') == grade_field.value and data.get('class') == class_field.value:
                    scores = data.get('scores', {})
                    total = scores.get('total', 0)
                    sp = scores.get('spelling', 0)
                    li = scores.get('literacy', 0)
                    wr = scores.get('writing', 0)
                    zi = scores.get('jiphyeon', 0)
                    ai_report = data.get('ai_report', "버튼을 눌러 현재 학습 데이터를 분석해보세요.")

                    student_rows.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"👤 {data.get('name')}", size=22, weight="bold", color="#5D4037"),
                                    ft.Text(f"🏆 총점: {total}점", size=20, weight="bold", color="#C62828")
                                ], spacing=20),
                                ft.Row([
                                    ft.Container(content=ft.Text(f"맞춤법: {sp}"), bgcolor="#FDEEF4", padding=8, border_radius=10),
                                    ft.Container(content=ft.Text(f"문해력: {li}"), bgcolor="#EBF4FA", padding=8, border_radius=10),
                                    ft.Container(content=ft.Text(f"글쓰기: {wr}"), bgcolor="#F0F9ED", padding=8, border_radius=10),
                                    ft.Container(content=ft.Text(f"집현전: {zi}"), bgcolor="#FFF9E5", padding=8, border_radius=10),
                                ], spacing=10),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Row([
                                            ft.Text("⭐", size=18), 
                                            ft.Text("AI 학습 능력 분석", weight="bold"),
                                            ft.ElevatedButton("🤖 AI 분석하기", on_click=make_analyze_func(uid, data.get('name'), scores), height=30)
                                        ]),
                                        ft.Text(ai_report, size=15)
                                    ]),
                                    bgcolor="#F5F5F5", padding=15, border_radius=10, width=1000
                                ),
                                ft.Divider(height=30)
                            ])
                        )
                    )
            if not student_rows:
                return ft.Container(content=ft.Text("조회된 학생이 없습니다.", size=18), padding=50)
            return ft.Column(student_rows, scroll="always", expand=True)
        
        def get_spelling_manual_view():
            problem_list = ft.Column(spacing=20) 
            feedback_text = ft.Text("", color="green", size=16, weight="bold")
            
            def create_problem_row(index):
                audio_f = ft.TextField(label="[소리] 아이들에게 들려줄 문장", bgcolor="white", width=800)
                answer_f = ft.TextField(label="[정답] 채점용 정답 문장", bgcolor="white", width=800)
                return ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"{index}번 문제", weight="bold", size=16),
                            ft.Row([
                                ft.TextButton(content=ft.Text("🔊 듣기"), on_click=lambda _, af=audio_f: play_voice(af.value) if af.value else None),
                                ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_problem(index))
                            ])
                        ], alignment="spaceBetween"),
                        audio_f,
                        answer_f,
                        ft.Divider(height=10, color="#EEEEEE")
                    ]), padding=10, key=str(index)
                )

            def add_problem(e):
                new_idx = len(problem_list.controls) + 1
                problem_list.controls.append(create_problem_row(new_idx))
                page.update()

            def remove_problem(index):
                if len(problem_list.controls) >= index:
                    problem_list.controls.pop(index - 1)
                    for i, cnt in enumerate(problem_list.controls):
                        cnt.content.controls[0].controls[0].value = f"{i + 1}번 문제"
                page.update()

            def save_to_firebase(e):
                test_data = []
                for control in problem_list.controls:
                    audio_text = control.content.controls[1].value
                    answer_text = control.content.controls[2].value
                    if audio_text and answer_text:
                        test_data.append({"audio": audio_text, "answer": answer_text})
                if not test_data: return
                try:
                    path = f"spelling_tests/{school_field.value}/{grade_field.value}/{class_field.value}"
                    db.reference(path).set({"title": f"{grade_field.value} {class_field.value} 받아쓰기", "problems": test_data, "created_at": "2024-05-20"})
                    feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                    page.update()
                except Exception as ex: print(f"저장 에러: {ex}")

            for i in range(1, 11):
                problem_list.controls.append(create_problem_row(i))

            return ft.Column([
                ft.Row([ft.Text("문제를 입력하고 배포 버튼을 눌러주세요.", size=18, weight="bold"), ft.ElevatedButton("➕ 문제 추가", on_click=add_problem, bgcolor="#8D6E63", color="white")], alignment="spaceBetween"),
                ft.Divider(), problem_list,
                ft.ElevatedButton("문제 저장 및 학생들에게 배포하기", width=1000, height=60, bgcolor="blue", color="white", on_click=save_to_firebase),
                feedback_text
            ], scroll="always", expand=True)

        def get_spelling_method_selection():
            spell_grade = ft.Dropdown(label="학년 수준", width=120, options=[ft.dropdown.Option(f"{i}학년") for i in range(1, 7)], value=grade_field.value if grade_field.value else "3학년")

            def start_ai_generation(e):
                content_area.content = ft.Column([ft.ProgressRing(), ft.Text(f"Groq AI가 {spell_grade.value} 수준 문제를 생성 중입니다...", size=16)], alignment="center", horizontal_alignment="center")
                page.update()
                prompt = f"초등학교 {spell_grade.value} 수준 국어 받아쓰기 문제 10개를 JSON으로만 답해. 형식: {{'problems': [{{'audio': '문장', 'answer': '정답'}}]}}"
                try:
                    payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a helpful assistant that outputs only JSON. 반드시 자연스럽고 완벽한 한국어(표준어)로만 작성하세요. 오타나 어색한 표현이 없도록 철저히 검수하세요."}, {"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    response = requests.post(TARGET_URL, json=payload, headers=headers)
                    result = response.json()

                    if 'choices' in result:
                        data = json.loads(result['choices'][0]['message']['content'])
                        problem_list_col = ft.Column(spacing=10)
                        feedback_text = ft.Text("", color="green", size=16, weight="bold")

                        def remove_problem(row_control):
                            problem_list_col.controls.remove(row_control)
                            for i, ctrl in enumerate(problem_list_col.controls): ctrl.controls[0].value = f"{i+1}."
                            page.update()

                        def create_prob_row(index, audio="", answer=""):
                            row = ft.Row()
                            row.controls = [
                                ft.Text(f"{index}.", width=30), ft.TextField(value=audio, label="문제 문장", expand=True), ft.TextField(value=answer, label="정답", width=120),
                                ft.TextButton(content=ft.Text("🔊 듣기"), on_click=lambda _, t=audio: play_voice(t)),
                                ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_problem(row))
                            ]
                            return row

                        def add_prob(e):
                            problem_list_col.controls.append(create_prob_row(len(problem_list_col.controls) + 1))
                            page.update()

                        for i, p in enumerate(data.get('problems', [])):
                            problem_list_col.controls.append(create_prob_row(i+1, p.get('audio',''), p.get('answer','')))

                        def save_spelling_to_firebase(e):
                            test_data = [{"audio": c.controls[1].value, "answer": c.controls[2].value} for c in problem_list_col.controls if c.controls[1].value and c.controls[2].value]
                            if not test_data: return
                            db.reference(f"spelling_tests/{school_field.value}/{grade_field.value}/{class_field.value}").set({"title": f"{spell_grade.value} {class_field.value} 받아쓰기 (AI)", "problems": test_data, "created_at": str(time.time())})
                            feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                            page.update()

                        def save_to_txt(e):
                            probs = [{"audio": c.controls[1].value, "answer": c.controls[2].value} for c in problem_list_col.controls if c.controls[1].value and c.controls[2].value]
                            try:
                                with open("dictation_result.txt", "w", encoding="utf-8") as f:
                                    for i, p in enumerate(probs): f.write(f"{i+1}. 문장: {p['audio']} / 정답: {p['answer']}\n")
                                page.snack_bar = ft.SnackBar(ft.Text("메모장 저장완료!")); page.snack_bar.open = True; page.update()
                            except Exception as ex: print(ex)

                        content_area.content = ft.Column([
                            ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "맞춤법 및 받아쓰기 관리")), ft.Text("📝 AI 생성 문제 확인 및 수정", size=24, weight="bold")]),
                            ft.Row([ft.ElevatedButton("➕ 문제 추가", on_click=add_prob, height=30)]), ft.Divider(),
                            ft.Column(controls=[problem_list_col], scroll="always", expand=True, height=400), ft.Divider(),
                            ft.Row([ft.ElevatedButton("🔄 다시 생성", on_click=start_ai_generation), ft.ElevatedButton("💾 PC에 저장(TXT)", on_click=save_to_txt), ft.ElevatedButton("✅ 확정 저장", on_click=save_spelling_to_firebase)], alignment="end"),
                            feedback_text
                        ], expand=True)
                    else: raise Exception("API 에러")
                except Exception as ex:
                    content_area.content = ft.Column([ft.Text("⚠️ 오류", size=22, weight="bold"), ft.ElevatedButton("다시 시도", on_click=start_ai_generation)], horizontal_alignment="center")
                page.update()

            def go_manual_teacher(e):
                content_area.content = ft.Column([
                    ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "맞춤법 및 받아쓰기 관리")), ft.Text("[교사 직접 출제]", size=40, weight="bold")]),
                    ft.Divider(height=10, thickness=2), get_spelling_manual_view()
                ], scroll="always", expand=True)
                page.update()

            return ft.Row([
                ft.Container(content=ft.Column([ft.Text("🤖", size=50), ft.Text("AI 자동 출제", size=20, weight="bold"), spell_grade, ft.ElevatedButton("AI 출제 시작", on_click=start_ai_generation, bgcolor="#8D6E63", color="white")], alignment="center", horizontal_alignment="center"), width=300, height=350, bgcolor="#F5F5F5", border_radius=20, padding=20),
                ft.Container(content=ft.Column([ft.Text("✍️", size=50), ft.Text("교사 직접 출제", size=20, weight="bold"), ft.ElevatedButton("직접 출제하기", on_click=go_manual_teacher)], alignment="center", horizontal_alignment="center"), width=300, height=350, bgcolor="#F5F5F5", border_radius=20, padding=20)
            ], spacing=30, alignment="center")

        def get_literacy_management_view():
            lit_grade = ft.Dropdown(label="학년 수준", width=120, options=[ft.dropdown.Option(f"{i}학년") for i in range(1, 7)], value=grade_field.value if grade_field.value else "3학년")

            def start_ai_literacy_generation(e):
                content_area.content = ft.Column([ft.ProgressRing(), ft.Text(f"Groq AI가 {lit_grade.value} 수준 세트를 구성 중입니다...", size=16)], alignment="center", horizontal_alignment="center")
                page.update()
                prompt = f"초등학교 {lit_grade.value} 수준의 문해력 학습 세트를 JSON으로 생성해줘. 1. vocab: 어려운 낱말 2개와 뜻(mean) 2. passage: 150자 내외 읽기 지문 3. questions: 확인 문제 2개(질문 q, 정답 a). 형식: {{ 'vocab': [ {{ 'word': '..', 'mean': '..' }} ], 'passage': '...', 'questions': [ {{ 'q': '..', 'a': '..' }} ] }}"
                try:
                    payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a literacy education expert. Output ONLY JSON. 반드시 자연스럽고 완벽한 한국어(표준어)로만 작성하세요. 오타나 어색한 문법이 없어야 합니다."}, {"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    response = requests.post(TARGET_URL, json=payload, headers=headers)
                    res_data = json.loads(response.json()['choices'][0]['message']['content'])
                    
                    vocab_list = ft.Column(spacing=10)
                    question_list = ft.Column(spacing=10)
                    passage_field = ft.TextField(value=res_data.get('passage', ''), multiline=True, min_lines=5, width=1000)
                    feedback_text = ft.Text("", color="green", size=16, weight="bold")

                    def remove_vocab(row_control): vocab_list.controls.remove(row_control); page.update()
                    def create_vocab_row(word="", mean=""):
                        row = ft.Row()
                        row.controls = [ft.Text("📍", width=30), ft.TextField(label="단어", value=word, width=150), ft.TextField(label="뜻", value=mean, expand=True), ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_vocab(row))]
                        return row
                    def add_vocab(e): vocab_list.controls.append(create_vocab_row()); page.update()
                    
                    def remove_question(row_control):
                        question_list.controls.remove(row_control)
                        for i, ctrl in enumerate(question_list.controls): ctrl.controls[0].value = f"Q{i+1}"
                        page.update()
                    def create_question_row(idx, q="", a=""):
                        row = ft.Row()
                        row.controls = [ft.Text(f"Q{idx}", width=40, weight="bold"), ft.TextField(label="질문", value=q, expand=True), ft.TextField(label="정답", value=a, width=150), ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_question(row))]
                        return row
                    def add_question(e): question_list.controls.append(create_question_row(len(question_list.controls) + 1)); page.update()

                    for v in res_data.get('vocab', []): vocab_list.controls.append(create_vocab_row(v.get('word', ''), v.get('mean', '')))
                    for i, q in enumerate(res_data.get('questions', [])): question_list.controls.append(create_question_row(i+1, q.get('q', ''), q.get('a', '')))

                    def ai_manual_save(e):
                        v_data = [{"word": c.controls[1].value, "mean": c.controls[2].value} for c in vocab_list.controls if c.controls[1].value]
                        q_data = [{"q": c.controls[1].value, "a": c.controls[2].value} for c in question_list.controls if c.controls[1].value]
                        db.reference(f"literacy_tests/{school_field.value}/{grade_field.value}/{class_field.value}").set({"vocab": v_data, "passage": passage_field.value, "questions": q_data})
                        feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                        page.update()

                    content_area.content = ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "문해력 관리"))]), ft.Text("📖 AI 통합 문해력 학습 세트 확인 및 수정", size=24, weight="bold"), ft.Divider(),
                        ft.Row([ft.Text("Step 1. 어휘", size=18, weight="bold", color="blue"), ft.ElevatedButton("➕ 어휘 추가", on_click=add_vocab, height=30)]), vocab_list, ft.Divider(),
                        ft.Text("Step 2. 지문", size=18, weight="bold", color="green"), passage_field, ft.Divider(),
                        ft.Row([ft.Text("Step 3. 문제", size=18, weight="bold", color="orange"), ft.ElevatedButton("➕ 문제 추가", on_click=add_question, height=30)]), question_list, ft.Divider(),
                        ft.Row([ft.ElevatedButton("🔄 다시 생성", on_click=start_ai_literacy_generation), ft.ElevatedButton("💾 배포하기", bgcolor="blue", color="white", on_click=ai_manual_save)], alignment="end"),
                        feedback_text
                    ], scroll="always", expand=True)
                except Exception as ex: content_area.content = ft.Text(f"생성 오류: {ex}")
                page.update()

            def go_manual_literacy(e):
                vocab_list = ft.Column(spacing=10); question_list = ft.Column(spacing=10); 
                passage_field = ft.TextField(label="지문 내용", multiline=True, min_lines=5, width=1000)
                feedback_text = ft.Text("", color="green", size=16, weight="bold")
                
                def remove_v(row_control):
                    vocab_list.controls.remove(row_control)
                    page.update()
                    
                def add_v(e): 
                    row = ft.Row()
                    row.controls = [
                        ft.Text("어휘", width=60, weight="bold"), 
                        ft.TextField(label="단어", width=150), 
                        ft.TextField(label="뜻", expand=True),
                        ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_v(row))
                    ]
                    vocab_list.controls.append(row)
                    if e is not None: page.update()
                    
                def remove_q(row_control):
                    question_list.controls.remove(row_control)
                    page.update()
                    
                def add_q(e): 
                    row = ft.Row()
                    row.controls = [
                        ft.Text("문제", width=60, weight="bold"), 
                        ft.TextField(label="질문", expand=True), 
                        ft.TextField(label="정답", width=150),
                        ft.TextButton(content=ft.Text("❌ 삭제", color="red"), on_click=lambda _: remove_q(row))
                    ]
                    question_list.controls.append(row)
                    if e is not None: page.update()
                    
                def manual_save(e):
                    v_data = [{"word": c.controls[1].value, "mean": c.controls[2].value} for c in vocab_list.controls if c.controls[1].value]
                    q_data = [{"q": c.controls[1].value, "a": c.controls[2].value} for c in question_list.controls if c.controls[1].value]
                    db.reference(f"literacy_tests/{school_field.value}/{grade_field.value}/{class_field.value}").set({"vocab": v_data, "passage": passage_field.value, "questions": q_data})
                    feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                    page.update()
                    
                add_v(None); add_q(None)
                content_area.content = ft.Column([
                    ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "문해력 관리")), ft.Text("✍️ 문해력 직접 출제", size=24, weight="bold")]), ft.Divider(),
                    ft.Row([ft.Text("1. 어휘 등록"), ft.ElevatedButton("➕ 추가", on_click=add_v)]), vocab_list, ft.Divider(),
                    ft.Text("2. 지문 등록"), passage_field, ft.Divider(),
                    ft.Row([ft.Text("3. 문제 등록"), ft.ElevatedButton("➕ 추가", on_click=add_q)]), question_list, ft.Divider(),
                    ft.ElevatedButton("💾 저장 및 배포", bgcolor="green", color="white", on_click=manual_save),
                    feedback_text
                ], scroll="always", expand=True)
                page.update()

            return ft.Row([
                ft.Container(content=ft.Column([ft.Text("🤖", size=50), ft.Text("AI 통합 출제", size=20, weight="bold"), lit_grade, ft.ElevatedButton("시작하기", on_click=start_ai_literacy_generation, bgcolor="#8D6E63", color="white")], alignment="center", horizontal_alignment="center"), width=300, height=400, bgcolor="#F5F5F5", border_radius=20, padding=20),
                ft.Container(content=ft.Column([ft.Text("✍️", size=50), ft.Text("교사 직접 출제", size=20, weight="bold"), ft.ElevatedButton("직접하기", on_click=go_manual_literacy)], alignment="center", horizontal_alignment="center"), width=300, height=400, bgcolor="#F5F5F5", border_radius=20, padding=20)
            ], alignment="center", spacing=30)

        def get_writing_management_view():
            write_grade = ft.Dropdown(label="학년 수준", width=120, options=[ft.dropdown.Option(f"{i}학년") for i in range(1, 7)], value=grade_field.value if grade_field.value else "3학년")
            def start_ai_writing_generation(e):
                content_area.content = ft.Column([ft.ProgressRing(), ft.Text("AI가 주제를 고민 중...")], alignment="center")
                page.update()
                try:
                    prompt = f"초등학교 {write_grade.value} 수준에 맞는 재미있고 창의적인 글쓰기 주제 1개를 JSON으로 생성해줘. 형식: {{ 'topic': '글쓰기 주제', 'guideline': '가이드라인' }}"
                    payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a creative writing teacher. Output ONLY JSON. 반드시 자연스럽고 완벽한 한국어(표준어)로만 작성하세요."}, {"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                    response = requests.post(TARGET_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"})
                    res_data = json.loads(response.json()['choices'][0]['message']['content'])
                    
                    feedback_text = ft.Text("", color="green", size=16, weight="bold")
                    def ai_save(e):
                        db.reference(f"writing_tasks/{school_field.value}/{grade_field.value}/{class_field.value}").set({"topic": content_area.content.controls[4].value, "guideline": content_area.content.controls[6].value, "created_at": str(time.time())})
                        feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                        page.update()

                    content_area.content = ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "글쓰기 관리"))]), ft.Text("✨ AI 주제 생성 완료", size=24, weight="bold"), ft.Divider(),
                        ft.Text("주제", color="blue"), ft.TextField(value=res_data.get('topic', ''), width=1000, multiline=True),
                        ft.Text("가이드라인", color="green"), ft.TextField(value=res_data.get('guideline', ''), multiline=True, min_lines=3, width=1000),
                        ft.Row([ft.ElevatedButton("🔄 다시 생성", on_click=start_ai_writing_generation), ft.ElevatedButton("💾 배포하기", bgcolor="blue", color="white", on_click=ai_save)], alignment="end"),
                        feedback_text
                    ], scroll="always", expand=True)
                except Exception as ex: content_area.content = ft.Text(f"생성 오류: {ex}")
                page.update()
                
            def go_manual_writing(e):
                m_state = {"topic": "", "guide": ""}
                topic_field = ft.TextField(label="주제", multiline=True, width=1000, on_change=lambda ev: m_state.update({"topic": ev.control.value}))
                guide_field = ft.TextField(label="가이드라인", multiline=True, min_lines=3, width=1000, on_change=lambda ev: m_state.update({"guide": ev.control.value}))
                feedback_text = ft.Text("", color="green", size=16, weight="bold")
                
                def manual_save(e):
                    if m_state["topic"]:
                        db.reference(f"writing_tasks/{school_field.value}/{grade_field.value}/{class_field.value}").set({"topic": m_state["topic"], "guideline": m_state["guide"], "created_at": str(time.time())})
                        feedback_text.value = "✅ 문제 배포가 완료되었습니다!"
                        page.update()

                content_area.content = ft.Column([
                    ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda e: menu_click(e, "글쓰기 관리")), ft.Text("✍️ 직접 제시", size=24, weight="bold")]),
                    topic_field, guide_field, ft.ElevatedButton("배포", bgcolor="green", color="white", on_click=manual_save),
                    feedback_text
                ], scroll="always")
                page.update()
                
            return ft.Row([
                ft.Container(content=ft.Column([ft.Text("🤖", size=50), ft.Text("AI 주제 추천", size=20, weight="bold"), write_grade, ft.ElevatedButton("시작", on_click=start_ai_writing_generation)], alignment="center", horizontal_alignment="center"), width=300, height=400, bgcolor="#F5F5F5", border_radius=20, padding=20),
                ft.Container(content=ft.Column([ft.Text("✍️", size=50), ft.Text("직접 제시", size=20, weight="bold"), ft.ElevatedButton("시작", on_click=go_manual_writing)], alignment="center", horizontal_alignment="center"), width=300, height=400, bgcolor="#F5F5F5", border_radius=20, padding=20)
            ], alignment="center", spacing=30)

        def get_board_management_view():
            board_view = ft.Column(expand=True, scroll="always")
            path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"

            def show_shared_board_menu(is_init=False):
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Text("글 공유 게시판 관리", size=32, weight="bold", color="#5D4037"),
                        ft.Container(height=40),
                        ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("📚", size=60),
                                    ft.Text("주제별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("그동안 제시된 주제별로\n학생들의 글을 모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_topics_list()
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("👤", size=60),
                                    ft.Text("학생별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("우리 반 학생들 이름별로\n작성한 글을 모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_students_list()
                            )
                        ], alignment="center", spacing=50)
                    ], horizontal_alignment="center", expand=True)
                )
                if not is_init: page.update()

            def show_topics_list():
                all_posts = safe_dict(db.reference(path).get())
                topics = set()
                for key, data in all_posts.items():
                    if isinstance(data, dict) and 'title' in data and data['title']: topics.add(str(data['title']))
                
                topic_buttons = [ft.ElevatedButton(topic, width=400, height=60, on_click=lambda e, t=topic: show_posts_by_filter("title", t)) for topic in sorted(list(topics))]
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_shared_board_menu()), ft.Text("주제별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=topic_buttons, scroll="always", spacing=10, horizontal_alignment="center") if topic_buttons else ft.Text("등록된 주제가 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def show_students_list():
                all_posts = safe_dict(db.reference(path).get())
                students = set()
                for key, data in all_posts.items():
                    if isinstance(data, dict) and 'author' in data and data['author']: students.add(str(data['author']))
                
                student_buttons = [ft.ElevatedButton(student, width=400, height=60, on_click=lambda e, s=student: show_posts_by_filter("author", s)) for student in sorted(list(students))]
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_shared_board_menu()), ft.Text("학생별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=student_buttons, scroll="always", spacing=10, horizontal_alignment="center") if student_buttons else ft.Text("등록된 학생이 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def delete_post_action(post_id, post_title, post_author, filter_type, filter_value):
                db.reference(f"{path}/{post_id}").delete()
                # 연동 삭제 
                a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{post_author}"
                a_posts = safe_dict(db.reference(a_path).get())
                for apid, adata in a_posts.items():
                    if isinstance(adata, dict) and str(adata.get('topic', '')) == str(post_title): 
                        db.reference(f"{a_path}/{apid}").delete()
                page.snack_bar = ft.SnackBar(ft.Text("게시글이 삭제되었습니다.")); page.snack_bar.open = True
                show_posts_by_filter(filter_type, filter_value)

            def show_posts_by_filter(filter_type, filter_value):
                all_posts = safe_dict(db.reference(path).get())
                filtered_data = []
                max_likes = 0
                for pid, pdata in all_posts.items():
                    if isinstance(pdata, dict) and str(pdata.get(filter_type, '')) == str(filter_value):
                        likes = pdata.get('likes', 0)
                        if likes > max_likes: max_likes = likes
                        filtered_data.append((pid, pdata, likes))
                        
                filtered_posts = []
                for pid, pdata, likes in reversed(filtered_data):
                    best_badge = "👑 [BEST 인기글]" if likes > 0 and likes == max_likes else ""
                    c_ui = []
                    for cid, cdata in pdata.get('comments', {}).items():
                        if isinstance(cdata, dict): 
                            is_my_com = (str(cdata.get('author', '')) == name_field.value or str(cdata.get('author', '')) == "교사")
                            com_acts = []
                            if is_my_com:
                                def make_com_edit(p, c, curr_txt):
                                    def open_edit(_):
                                        st = {"text": str(curr_txt or "")}
                                        edit_f = ft.TextField(value=st["text"], on_change=lambda ev: st.update({"text": ev.control.value}))
                                        dlg = ft.AlertDialog(title=ft.Text("댓글 수정"))
                                        def save_c(ev):
                                            val = st["text"].strip()
                                            if val: db.reference(f"{path}/{p}/comments/{c}").update({'text': val})
                                            dlg.open = False; page.update(); show_posts_by_filter(filter_type, filter_value)
                                        def close_c(ev): dlg.open = False; page.update()
                                        dlg.content = edit_f
                                        dlg.actions = [ft.TextButton("저장", on_click=save_c), ft.TextButton("취소", on_click=close_c)]
                                        page.overlay.append(dlg)
                                        dlg.open = True
                                        page.update()
                                    return open_edit
                                com_acts.append(ft.TextButton("✏️", on_click=make_com_edit(pid, cid, cdata.get('text',''))))
                            
                            # 교사는 모든 댓글 삭제 가능
                            com_acts.append(ft.TextButton("❌", icon_color="red", on_click=lambda _, p=pid, c=cid: (db.reference(f"{path}/{p}/comments/{c}").delete(), show_posts_by_filter(filter_type, filter_value))))
                            c_ui.append(ft.Row([ft.Text(f"↳ {cdata.get('author', '익명')}: {cdata.get('text', '')}", size=14), ft.Row(com_acts)], alignment="spaceBetween"))
                    
                    def make_add_comment(post_id):
                        st = {"text": ""}
                        cf = ft.TextField(hint_text="교사 댓글 달기", expand=True, height=40, on_change=lambda ev: st.update({"text": ev.control.value}))
                        def do_add(e):
                            val = st["text"].strip()
                            if not val: return
                            db.reference(f"{path}/{post_id}/comments").push({"author": name_field.value if name_field.value else "교사", "text": val})
                            show_posts_by_filter(filter_type, filter_value)
                        return cf, do_add

                    comment_field, add_comment_func = make_add_comment(pid)

                    liked_users = safe_dict(pdata.get('liked_users', {}))
                    user_name = name_field.value if name_field.value else "교사"
                    has_liked = user_name in liked_users
                    like_text = f"❤️ 좋아요 취소 {likes}" if has_liked else f"🤍 좋아요 {likes}"

                    def toggle_like(e, post_id=pid, curr_liked_users=liked_users, u_name=user_name):
                        if u_name in curr_liked_users:
                            del curr_liked_users[u_name]
                        else:
                            curr_liked_users[u_name] = True
                        db.reference(f"{path}/{post_id}/liked_users").set(curr_liked_users)
                        db.reference(f"{path}/{post_id}/likes").set(len(curr_liked_users))
                        show_posts_by_filter(filter_type, filter_value)
                    
                    post_acts = [ft.TextButton(content=ft.Text(like_text), on_click=toggle_like)]
                    
                    is_my_post = (str(pdata.get('author', '')) == name_field.value or str(pdata.get('author', '')) == "교사")
                    if is_my_post:
                        def open_post_edit(p, t, curr_txt):
                            p_state = {"text": str(curr_txt or "")}
                            edit_f = ft.TextField(value=p_state["text"], multiline=True, on_change=lambda ev: p_state.update({"text": ev.control.value}))
                            dlg = ft.AlertDialog(title=ft.Text("글 수정"))
                            def save_p(ev):
                                val = p_state["text"].strip()
                                if val:
                                    db.reference(f"{path}/{p}").update({'content': val})
                                    update_anthology_post(t, val)
                                dlg.open = False; page.update(); show_posts_by_filter(filter_type, filter_value)
                            def close_p(ev): dlg.open = False; page.update()
                            dlg.content = edit_f
                            dlg.actions = [ft.TextButton("저장", on_click=save_p), ft.TextButton("취소", on_click=close_p)]
                            page.overlay.append(dlg)
                            dlg.open = True
                            page.update()
                        post_acts.append(ft.TextButton("✏️ 수정", on_click=lambda _, p=pid, t=pdata.get('title',''), c=pdata.get('content',''): open_post_edit(p, t, c)))
                    
                    # 교사는 모든 글 삭제 가능
                    post_acts.append(ft.TextButton("🗑️ 게시글 삭제", icon_color="red", on_click=lambda _, p=pid, t=pdata.get('title',''), a=pdata.get('author',''): delete_post_action(p, t, a, filter_type, filter_value)))

                    post_card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"📝 {pdata.get('title', '')} ({pdata.get('author', '')}) {best_badge}", weight="bold", size=18, color="blue" if best_badge else "black"), 
                                ft.Row(post_acts)
                            ], alignment="spaceBetween"),
                            ft.Text(pdata.get('content', ''), size=16), ft.Divider(height=1), ft.Text("💬 댓글", weight="bold"), ft.Column(c_ui),
                            ft.Row([comment_field, ft.ElevatedButton("댓글 등록", on_click=add_comment_func)])
                        ]), bgcolor="white", padding=20, border_radius=10, border=ft.border.all(1, "#E0E0E0")
                    )
                    filtered_posts.append(post_card)

                back_func = show_topics_list if filter_type == "title" else show_students_list
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: back_func()), ft.Text(f"'{filter_value}' 관련 글", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=filtered_posts, scroll="always", spacing=20) if filtered_posts else ft.Text("해당 조건의 게시글이 없습니다.", size=16)
                    ], expand=True)
                )
                page.update()

            show_shared_board_menu(is_init=True)
            return board_view

        def get_jiphyeonjeon_management_view():
            jiphyeonjeon_view = ft.Column(expand=True, scroll="always")
            path = f"jiphyeonjeon_books/{school_field.value}/{grade_field.value}/{class_field.value}"

            def edit_book(book_id, book_data):
                b_state = {"title": book_data.get('title', ''), "author": book_data.get('author', ''), "desc": book_data.get('desc', '')}
                edit_title = ft.TextField(label="도서 제목", value=b_state["title"], width=300, on_change=lambda e: b_state.update({"title": e.control.value}))
                edit_author = ft.TextField(label="지은이", value=b_state["author"], width=200, on_change=lambda e: b_state.update({"author": e.control.value}))
                edit_desc = ft.TextField(label="독서 포인트", value=b_state["desc"], multiline=True, expand=True, on_change=lambda e: b_state.update({"desc": e.control.value}))
                def save_edit(e):
                    db.reference(f"{path}/{book_id}").update({"title": b_state["title"], "author": b_state["author"], "desc": b_state["desc"]})
                    show_bookshelf()
                jiphyeonjeon_view.controls.clear()
                jiphyeonjeon_view.controls.extend([
                    ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_bookshelf()), ft.Text("✏️ 도서 정보 수정", size=24, weight="bold")]), ft.Divider(),
                    ft.Row([edit_title, edit_author]), edit_desc, ft.Row([ft.ElevatedButton("💾 수정 완료", on_click=save_edit), ft.ElevatedButton("취소", on_click=lambda _: show_bookshelf())])
                ])
                page.update()

            def show_bookshelf(is_init=False):
                jiphyeonjeon_view.controls.clear()
                jiphyeon_grade = ft.Dropdown(label="추천 학년", width=120, height=40, options=[ft.dropdown.Option(f"{i}학년") for i in range(1, 7)], value=grade_field.value if grade_field.value else "3학년")
                def ai_recommend(e):
                    jiphyeonjeon_view.controls.insert(0, ft.ProgressRing()); page.update()
                    try:
                        payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a helpful librarian. Output ONLY JSON. 반드시 완벽하고 자연스러운 한국어(표준어)로 작성하세요."}, {"role": "user", "content": f"초등학교 {jiphyeon_grade.value} 추천 도서 3권. 형식: {{ 'books': [ {{'title': '..', 'author': '..', 'desc': '..'}} ] }}"}], "response_format": {"type": "json_object"}}
                        res = requests.post(TARGET_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}).json()
                        for b in json.loads(res['choices'][0]['message']['content']).get('books', []): db.reference(path).push({"title": b.get('title'), "author": b.get('author'), "desc": b.get('desc'), "recommender": "AI 선생님"})
                    except Exception as ex: print(ex)
                    show_bookshelf()

                n_state = {"title": "", "author": "", "desc": ""}
                title_f = ft.TextField(label="제목", width=200, on_change=lambda e: n_state.update({"title": e.control.value}))
                author_f = ft.TextField(label="지은이", width=150, on_change=lambda e: n_state.update({"author": e.control.value}))
                desc_f = ft.TextField(label="소개", expand=True, on_change=lambda e: n_state.update({"desc": e.control.value}))
                def add_b(e):
                    val = n_state["title"].strip()
                    if val:
                        db.reference(path).push({"title": val, "author": n_state["author"], "desc": n_state["desc"], "recommender": "교사"})
                        show_bookshelf()

                books_row = ft.Row(wrap=True, spacing=20, run_spacing=20)
                books = safe_dict(db.reference(path).get())
                book_items = []
                max_avg = 0
                if books:
                    for bid, bdata in books.items():
                        if not isinstance(bdata, dict): continue
                        revs = safe_dict(bdata.get('reviews', {}))
                        avg = sum(r.get('rating',0) for r in revs.values())/len(revs) if revs else 0
                        if avg > max_avg: max_avg = avg
                        book_items.append((bid, bdata, revs, avg))
                        
                    for bid, bdata, revs, avg in book_items:
                        best_badge = "👑 [BEST 추천 도서]\n" if avg > 0 and avg == max_avg else ""
                        title_text = best_badge + str(bdata.get('title', ''))
                        book_cover = ft.Container(width=140, height=190, bgcolor="#8D6E63", border_radius=10, padding=15, alignment=ft.Alignment(0,0), content=ft.Column([ft.Text(title_text, weight="bold", size=16, color="white", text_align="center"), ft.Text(bdata.get('author', ''), size=12, color="#E0E0E0", text_align="center")], alignment="center", horizontal_alignment="center"), on_click=lambda _, i=bid, d=bdata: show_book_detail(i, d))
                        books_row.controls.append(ft.Container(width=160, content=ft.Column([book_cover, ft.Text(f"⭐ {avg:.1f} ({len(revs)}명 읽음)", size=12, color="#FF8F00", weight="bold"), ft.Text(f"추천인: {bdata.get('recommender', '교사')}", size=11, color="blue"), ft.Row([ft.TextButton("✏️수정", on_click=lambda _, i=bid, d=bdata: edit_book(i, d)), ft.TextButton("❌삭제", on_click=lambda _, i=bid: db.reference(f"{path}/{i}").delete() or show_bookshelf())], alignment="center", spacing=5)], horizontal_alignment="center", spacing=5)))
                
                jiphyeonjeon_view.controls.extend([
                    ft.Row([ft.Text("📚 집현전 책장", size=24, weight="bold"), ft.Row([jiphyeon_grade, ft.ElevatedButton("🤖 AI 추천 추가", on_click=ai_recommend)])], alignment="spaceBetween"), ft.Divider(),
                    ft.Container(content=ft.Column([ft.Row([title_f, author_f, desc_f]), ft.ElevatedButton("➕ 직접 등록", on_click=add_b)]), bgcolor="#F5F5F5", padding=15), ft.Divider(), books_row
                ])
                if not is_init: page.update()

            def show_book_detail(book_id, book_data):
                jiphyeonjeon_view.controls.clear()
                r_path = f"{path}/{book_id}/reviews"
                
                def make_edit_rev(rev_id, b_title, curr_txt):
                    def open_edit(_):
                        st = {"text": str(curr_txt or "")}
                        edit_f = ft.TextField(value=st["text"], multiline=True, on_change=lambda ev: st.update({"text": ev.control.value}))
                        dlg = ft.AlertDialog(title=ft.Text("감상평 수정"))
                        def save_r(ev):
                            val = st["text"].strip()
                            if val:
                                db.reference(f"{r_path}/{rev_id}").update({'text': val})
                                a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}"
                                a_posts = safe_dict(db.reference(a_path).get())
                                for apid, adata in a_posts.items():
                                    if isinstance(adata, dict) and str(adata.get('topic', '')) == f"[독서록] {b_title}" and str(adata.get('content', '')) == curr_txt:
                                        db.reference(f"{a_path}/{apid}").update({'content': val})
                            dlg.open = False; page.update(); load_r()
                        def close_r(ev): dlg.open = False; page.update()
                        dlg.content = edit_f
                        dlg.actions = [ft.TextButton("저장", on_click=save_r), ft.TextButton("취소", on_click=close_r)]
                        page.overlay.append(dlg)
                        dlg.open = True
                        page.update()
                    return open_edit

                def delete_rev_action(rev_id, rev_text, rev_author):
                    db.reference(f"{r_path}/{rev_id}").delete()
                    # 연동 삭제
                    a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{rev_author}"
                    a_posts = safe_dict(db.reference(a_path).get())
                    for apid, adata in a_posts.items():
                        if isinstance(adata, dict) and str(adata.get('topic', '')) == f"[독서록] {book_data.get('title','')}" and str(adata.get('content', '')) == str(rev_text):
                            db.reference(f"{a_path}/{apid}").delete()
                    load_r()

                r_col = ft.Column()
                def load_r():
                    r_col.controls.clear()
                    revs = safe_dict(db.reference(r_path).get())
                    if revs: 
                        for rid, r in revs.items():
                            if isinstance(r, dict):
                                is_mine = (str(r.get('author', '')) == "교사" or str(r.get('author', '')) == name_field.value)
                                acts = []
                                if is_mine:
                                    acts.append(ft.TextButton("✏️ 수정", on_click=make_edit_rev(rid, book_data.get('title',''), r.get('text',''))))
                                # 교사는 모든 감상평 삭제 가능
                                acts.append(ft.TextButton("❌ 삭제", icon_color="red", on_click=lambda _, r_id=rid, txt=r.get('text',''), au=r.get('author',''): delete_rev_action(r_id, txt, au)))
                                r_col.controls.append(ft.Container(content=ft.Column([ft.Row([ft.Row([ft.Text(f"👤 {r.get('author')}", weight="bold"), ft.Text(f"⭐ {r.get('rating')}점", color="#FF8F00")]), ft.Row(acts)], alignment="spaceBetween"), ft.Text(r.get('text'))]), bgcolor="#F9F9F9", padding=10))
                    page.update()
                
                r_state = {"text": ""}
                
                def make_report_ui():
                    def on_t_change(ev): r_state["text"] = ev.control.value
                    report_field = ft.TextField(multiline=True, min_lines=5, expand=True, hint_text="느낀 점을 적어주세요!", on_change=on_t_change)
                    rating_dropdown = ft.Dropdown(label="별점", width=100, options=[ft.dropdown.Option(str(i)) for i in range(1,6)], value="5")
                    
                    def submit_report(e):
                        val = r_state["text"].strip()
                        if not val or len(val) < 5: return
                        
                        rating_val = int(rating_dropdown.value) if rating_dropdown.value else 5
                        
                        db.reference(r_path).push({"author": name_field.value if name_field.value else "교사", "rating": rating_val, "text": val, "created_at": str(time.time())})
                        db.reference(f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}").push({"topic": f"[독서록] {book_data.get('title','')}", "content": val, "date": str(time.time())})
                        
                        report_field.value = ""; rating_dropdown.value = "5"; r_state.update({"text": ""}); load_r()
                    
                    return rating_dropdown, report_field, submit_report

                rd, rf, sub_func = make_report_ui()
                load_r()
                jiphyeonjeon_view.controls.extend([
                    ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_bookshelf()), ft.Text(f"📖 {book_data.get('title')}", size=28, weight="bold")]),
                    ft.Container(content=ft.Column([ft.Text(f"지은이: {book_data.get('author')}", weight="bold"), ft.Text(book_data.get('desc'))]), bgcolor="#FFF8E1", padding=20),
                    ft.Divider(), ft.Text("💬 친구들의 감상평", weight="bold"), r_col,
                    ft.Divider(), ft.Text("📝 교사 감상평 달기", weight="bold", color="blue"), rd, rf, ft.ElevatedButton("등록 및 점수 받기", on_click=sub_func)
                ])
                page.update()

            show_bookshelf(is_init=True)
            return jiphyeonjeon_view

        def get_anthology_management_view():
            anthology_view = ft.Column(expand=True, scroll="always")
            path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}"

            def show_anthology_menu(is_init=False):
                anthology_view.controls.clear()
                anthology_view.controls.append(
                    ft.Column([
                        ft.Row([
                            ft.Text("학급 문집 관리", size=32, weight="bold", color="#5D4037"),
                        ], alignment="spaceBetween"),
                        ft.Container(height=40),
                        ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("📚", size=60),
                                    ft.Text("주제별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("제시된 글쓰기 주제별로\n모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_topics_list()
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("👤", size=60),
                                    ft.Text("학생별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("학생 이름별로\n모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_students_list()
                            )
                        ], alignment="center", spacing=50)
                    ], horizontal_alignment="center", expand=True)
                )
                if not is_init: page.update()

            def show_topics_list():
                all_students = safe_dict(db.reference(path).get())
                topics = set()
                for student, w_dict in all_students.items():
                    if isinstance(w_dict, dict):
                        for wid, wd in w_dict.items():
                            if isinstance(wd, dict) and wd.get('topic'): topics.add(str(wd['topic']))
                
                topic_buttons = [ft.ElevatedButton(topic, width=400, height=60, on_click=lambda e, t=topic: show_posts_by_filter("topic", t)) for topic in sorted(list(topics))]
                anthology_view.controls.clear()
                anthology_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_anthology_menu()), ft.Text("주제별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=topic_buttons, scroll="always", spacing=10, horizontal_alignment="center") if topic_buttons else ft.Text("등록된 주제가 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def show_students_list():
                all_students = safe_dict(db.reference(path).get())
                students = set(all_students.keys())
                student_buttons = [ft.ElevatedButton(student, width=400, height=60, on_click=lambda e, s=student: show_posts_by_filter("student", s)) for student in sorted(list(students))]
                anthology_view.controls.clear()
                anthology_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_anthology_menu()), ft.Text("학생별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=student_buttons, scroll="always", spacing=10, horizontal_alignment="center") if student_buttons else ft.Text("등록된 학생이 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def delete_anthology_post(e, student_name, post_id, topic, content):
                db.reference(f"{path}/{student_name}/{post_id}").delete()
                if str(topic).startswith("[독서록] "):
                    btitle = str(topic).replace("[독서록] ", "")
                    j_path = f"jiphyeonjeon_books/{school_field.value}/{grade_field.value}/{class_field.value}"
                    books = safe_dict(db.reference(j_path).get())
                    for bid, bdata in books.items():
                        if isinstance(bdata, dict) and str(bdata.get('title', '')) == btitle:
                            revs = safe_dict(db.reference(f"{j_path}/{bid}/reviews").get())
                            for rid, rdata in revs.items():
                                if isinstance(rdata, dict) and str(rdata.get('author', '')) == student_name and str(rdata.get('text', '')) == str(content): 
                                    db.reference(f"{j_path}/{bid}/reviews/{rid}").delete()
                else:
                    b_path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"
                    b_posts = safe_dict(db.reference(b_path).get())
                    for b_pid, b_data in b_posts.items():
                        if isinstance(b_data, dict) and str(b_data.get('title', '')) == str(topic) and str(b_data.get('author', '')) == student_name: 
                            db.reference(f"{b_path}/{b_pid}").delete()
                page.snack_bar = ft.SnackBar(ft.Text("문집 글이 삭제되었습니다.")); page.snack_bar.open=True
                show_posts_by_filter("student", student_name)

            def show_posts_by_filter(filter_type, filter_value):
                all_students = safe_dict(db.reference(path).get())
                filtered_posts = []
                data_to_download = []
                
                for student, w_dict in all_students.items():
                    if isinstance(w_dict, dict):
                        for wid, wd in w_dict.items():
                            if isinstance(wd, dict):
                                if (filter_type == "topic" and str(wd.get('topic', '')) == str(filter_value)) or (filter_type == "student" and str(student) == str(filter_value)):
                                    data_to_download.append({"student": student, "topic": wd.get('topic', ''), "content": wd.get('content', '')})
                                    post_card = ft.Container(
                                        content=ft.Column([
                                            ft.Row([
                                                ft.Text(f"📝 {wd.get('topic', '')} (학생: {student})", weight="bold", size=18, color="blue"),
                                                ft.TextButton("❌ 삭제", icon_color="red", on_click=lambda e, s=student, pid=wid, t=wd.get('topic', ''), c=wd.get('content', ''): delete_anthology_post(e, s, pid, t, c))
                                            ], alignment="spaceBetween"),
                                            ft.Text(wd.get('content', ''), size=16)
                                        ]), bgcolor="white", padding=20, border_radius=10, border=ft.border.all(1, "#E0E0E0")
                                    )
                                    filtered_posts.append(post_card)

                def download_filtered(e):
                    try:
                        filename = f"{filter_value}_문집.txt".replace(" ", "_")
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(f"--- 나랏말싸미:꿈틀이의 문해력키우기 {grade_field.value} {class_field.value} '{filter_value}' 문집 ---\n\n")
                            for item in data_to_download:
                                f.write(f"[{item['student']}] 주제: {item['topic']}\n내용: {item['content']}\n\n")
                        page.snack_bar = ft.SnackBar(ft.Text(f"{filename} 다운로드 완료!")); page.snack_bar.open=True; page.update()
                    except Exception as ex: print(ex)

                back_func = show_topics_list if filter_type == "topic" else show_students_list
                anthology_view.controls.clear()
                anthology_view.controls.append(
                    ft.Column([
                        ft.Row([
                            ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: back_func()), ft.Text(f"'{filter_value}' 관련 글", size=28, weight="bold")]),
                            ft.ElevatedButton("💾 목록 다운로드", on_click=download_filtered, bgcolor="blue", color="white") if filtered_posts else ft.Container()
                        ], alignment="spaceBetween"),
                        ft.Divider(),
                        ft.Column(controls=filtered_posts, scroll="always", spacing=20) if filtered_posts else ft.Text("해당 조건의 글이 없습니다.", size=16)
                    ], expand=True)
                )
                page.update()

            show_anthology_menu(is_init=True)
            return anthology_view

        def get_shop_management_view():
            view = ft.Column(expand=True, scroll="always")
            shop_path = f"shop_items/{school_field.value}/{grade_field.value}/{class_field.value}"
            req_path = f"shop_requests/{school_field.value}/{grade_field.value}/{class_field.value}"
            
            s_state = {"name": "", "price": ""}
            item_name = ft.TextField(label="물품명", width=250, on_change=lambda e: s_state.update({"name": e.control.value}))
            item_price = ft.TextField(label="가격", width=150, on_change=lambda e: s_state.update({"price": e.control.value}))
            items_list = ft.Column(); reqs_list = ft.Column()

            def load_shop(is_init=False):
                items_list.controls.clear(); reqs_list.controls.clear()
                items = safe_dict(db.reference(shop_path).get())
                for iid, idata in items.items():
                    if isinstance(idata, dict): items_list.controls.append(ft.Row([ft.Text(f"🎁 {idata.get('name')}", width=200), ft.Text(f"💰 {idata.get('price')}P", width=150), ft.TextButton("❌ 삭제", on_click=lambda _, i=iid: db.reference(f"{shop_path}/{i}").delete() or load_shop())], alignment="spaceBetween"))
                reqs = safe_dict(db.reference(req_path).get())
                for rid, rdata in reqs.items():
                    if isinstance(rdata, dict) and not rdata.get('approved'):
                        reqs_list.controls.append(ft.Container(content=ft.Row([ft.Text(f"🙋‍♂️ {rdata.get('student_name')}님이 '{rdata.get('item_name')}' 요청"), ft.ElevatedButton("✅ 승인", on_click=lambda _, r=rid, d=rdata: approve(r, d))], alignment="spaceBetween"), bgcolor="#F9F9F9", padding=10))
                if not is_init: page.update()

            def add_item(e):
                if s_state["name"] and s_state["price"]: 
                    db.reference(shop_path).push({"name": s_state["name"], "price": int(s_state["price"])})
                    item_name.value=""; item_price.value=""; s_state["name"]=""; s_state["price"]=""
                    load_shop()
            def approve(rid, data):
                sid = data.get('student_id'); iname = data.get('item_name')
                if sid and iname:
                    inv_ref = db.reference(f"users/{sid}/inventory/{iname}"); curr = inv_ref.get() or 0
                    if curr > 0: inv_ref.set(curr - 1)
                db.reference(f"{req_path}/{rid}").update({"approved": True}); load_shop()

            load_shop(is_init=True)
            view.controls.extend([ft.Text("🛒 상점 관리", size=24, weight="bold"), ft.Divider(), ft.Row([item_name, item_price, ft.ElevatedButton("➕ 등록", on_click=add_item)]), ft.Container(content=items_list, padding=10), ft.Divider(), ft.Text("학생 사용 신청 내역"), reqs_list])
            return view

        def get_score_management_view():
            view = ft.Column(expand=True, scroll="always")
            settings_path = f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}"
            
            # 1. 파이어베이스 데이터를 안전하게 딕셔너리로 변환하는 함수
            def safe_to_dict(data):
                if isinstance(data, list):
                    # 리스트라면 인덱스를 키로 하는 딕셔너리로 변환 (None 값 제외)
                    return {str(i): v for i, v in enumerate(data) if v is not None}
                return data if isinstance(data, dict) else {}

            # 2. 데이터 불러오기 및 리스트 방어 처리
            raw_data = db.reference(settings_path).get()
            data = safe_to_dict(raw_data) # 전체 데이터가 리스트인 경우 방어
            
            # 기존 점수와 레벨 설정 가져오기 (각각 한 번 더 방어)
            existing_scores = safe_to_dict(data.get("scores"))
            existing_levels = safe_to_dict(data.get("levels"))

            # 기본값 설정 (데이터가 비어있을 때 사용)
            default_scores = {"spelling": 10, "spelling_bonus": 50, "literacy": 20, "literacy_bonus": 100, "writing": 50, "share": 5, "comment": 2, "jiphyeon": 100}
            default_levels = {"2": 100, "3": 300, "4": 600, "5": 1000, "6": 1500, "7": 2100}

            # 상태 관리를 위한 딕셔너리 (데이터가 없으면 기본값 사용)
            sc_state = {k: existing_scores.get(k, default_scores.get(k)) for k in default_scores.keys()}
            lv_state = {str(k): existing_levels.get(str(k), default_levels.get(str(k))) for k in default_levels.keys()}

            # 3. UI 컴포넌트 생성 (값 입력 및 변경 처리)
            s_spelling = ft.TextField(label="맞춤법 (기본)", value=str(sc_state["spelling"]), width=150, on_change=lambda e: sc_state.update({"spelling": int(e.control.value or 0)}))
            s_spelling_bonus = ft.TextField(label="맞춤법 (전체정답 보너스)", value=str(sc_state["spelling_bonus"]), width=180, on_change=lambda e: sc_state.update({"spelling_bonus": int(e.control.value or 0)}))
            s_literacy = ft.TextField(label="문해력 (기본)", value=str(sc_state["literacy"]), width=150, on_change=lambda e: sc_state.update({"literacy": int(e.control.value or 0)}))
            s_literacy_bonus = ft.TextField(label="문해력 (전체정답 보너스)", value=str(sc_state["literacy_bonus"]), width=180, on_change=lambda e: sc_state.update({"literacy_bonus": int(e.control.value or 0)}))
            s_writing = ft.TextField(label="글쓰기", value=str(sc_state["writing"]), width=150, on_change=lambda e: sc_state.update({"writing": int(e.control.value or 0)}))
            s_share = ft.TextField(label="공유", value=str(sc_state["share"]), width=150, on_change=lambda e: sc_state.update({"share": int(e.control.value or 0)}))
            s_comment = ft.TextField(label="댓글", value=str(sc_state["comment"]), width=150, on_change=lambda e: sc_state.update({"comment": int(e.control.value or 0)}))
            s_jiphyeon = ft.TextField(label="집현전", value=str(sc_state["jiphyeon"]), width=150, on_change=lambda e: sc_state.update({"jiphyeon": int(e.control.value or 0)}))

            s_l2 = ft.TextField(label="Lv.2 요구 점수", value=str(lv_state.get("2")), width=200, on_change=lambda e: lv_state.update({"2": int(e.control.value or 0)}))
            s_l3 = ft.TextField(label="Lv.3 요구 점수", value=str(lv_state.get("3")), width=200, on_change=lambda e: lv_state.update({"3": int(e.control.value or 0)}))
            s_l4 = ft.TextField(label="Lv.4 요구 점수", value=str(lv_state.get("4")), width=200, on_change=lambda e: lv_state.update({"4": int(e.control.value or 0)}))
            s_l5 = ft.TextField(label="Lv.5 요구 점수", value=str(lv_state.get("5")), width=200, on_change=lambda e: lv_state.update({"5": int(e.control.value or 0)}))
            s_l6 = ft.TextField(label="Lv.6 요구 점수", value=str(lv_state.get("6")), width=200, on_change=lambda e: lv_state.update({"6": int(e.control.value or 0)}))
            s_l7 = ft.TextField(label="Lv.7 요구 점수", value=str(lv_state.get("7")), width=200, on_change=lambda e: lv_state.update({"7": int(e.control.value or 0)}))

            feedback_text = ft.Text("", color="green", size=16, weight="bold")

            # 4. 저장 버튼 로직
            def save_settings(e):
                try:
                    db.reference(settings_path).set({
                        "scores": sc_state,
                        "levels": lv_state
                    })
                    feedback_text.value = "설정이 성공적으로 저장되었습니다!"
                    feedback_text.color = "green"
                    view.update()
                except Exception as ex:
                    feedback_text.value = f"저장 실패: {str(ex)}"
                    feedback_text.color = "red"
                    view.update()

            save_btn = ft.ElevatedButton("설정 저장하기", icon=ft.Icons.SAVE, on_click=save_settings)

            # 5. 화면 레이아웃
            view.controls = [
                ft.Text("활동별 획득 점수 설정", size=20, weight="bold"),
                ft.Row([s_spelling, s_spelling_bonus, s_literacy, s_literacy_bonus], wrap=True),
                ft.Row([s_writing, s_share, s_comment, s_jiphyeon], wrap=True),
                ft.Divider(),
                ft.Text("레벨업 요구 점수 설정", size=20, weight="bold"),
                ft.Row([s_l2, s_l3, s_l4], wrap=True),
                ft.Row([s_l5, s_l6, s_l7], wrap=True),
                ft.Row([save_btn, feedback_text], alignment="start")
            ]
            
            return view

        content_area = ft.Container(expand=True, padding=40, content=ft.Column([ft.Text("관리 메뉴를 선택해주세요.", size=30, weight="bold")]))

        def menu_click(e, forced_menu_name=None):
            menu_name = forced_menu_name if forced_menu_name else e.control.data 
            if menu_name == "처음으로 (로그아웃)": show_login_screen(); return
            if menu_name == "학생 관리": content_area.content = ft.Column([ft.Text(f"[{menu_name}]", size=40, weight="bold", color="#5D4037"), ft.Divider(), get_student_management_view()], scroll="always", expand=True)
            elif menu_name == "맞춤법 및 받아쓰기 관리": content_area.content = ft.Column([ft.Text(f"[{menu_name}]", size=40, weight="bold"), ft.Divider(), get_spelling_method_selection()], scroll="always", expand=True)
            elif menu_name == "문해력 관리": content_area.content = ft.Column([ft.Text(f"[{menu_name}]", size=40, weight="bold"), ft.Divider(), get_literacy_management_view()], scroll="always", expand=True)
            elif menu_name == "글쓰기 관리": content_area.content = ft.Column([ft.Text(f"[{menu_name}]", size=40, weight="bold"), ft.Divider(), get_writing_management_view()], scroll="always", expand=True)
            elif menu_name == "게시판 관리": content_area.content = ft.Column([get_board_management_view()], scroll="always", expand=True)
            elif menu_name == "집현전 관리": content_area.content = ft.Column([get_jiphyeonjeon_management_view()], scroll="always", expand=True)
            elif menu_name == "문집 관리": content_area.content = ft.Column([get_anthology_management_view()], scroll="always", expand=True)
            elif menu_name == "상점 관리": content_area.content = ft.Column([get_shop_management_view()], scroll="always", expand=True)
            elif menu_name == "점수 관리": content_area.content = ft.Column([get_score_management_view()], scroll="always", expand=True)
            page.update()

        menus = ["학생 관리", "맞춤법 및 받아쓰기 관리", "문해력 관리", "글쓰기 관리", "게시판 관리", "집현전 관리", "문집 관리", "상점 관리", "점수 관리", "처음으로 (로그아웃)"]
        menu_buttons = [ft.Container(content=ft.ElevatedButton(m, data=m, width=240, height=45, style=ft.ButtonStyle(bgcolor={"": "#8D6E63"}, color={"": "white"}), on_click=menu_click), margin=ft.margin.only(bottom=10)) for m in menus]
        page.add(ft.Row([ft.Container(width=280, bgcolor="#E0D7D1", padding=20, content=ft.Column([ft.Text("관리 센터", size=24, weight="bold"), ft.Column(menu_buttons, scroll="auto")], horizontal_alignment="center")), ft.VerticalDivider(width=1), content_area], expand=True))
        page.update()

    # ==========================================
    # [2] 학생 대시보드 화면 함수 
    # ==========================================
    def show_student_dashboard():
        page.clean()
        
        student_id = re.sub(r'[.#$\[\]]', '_', f"{school_field.value}_{grade_field.value}_{class_field.value}_{name_field.value}")
        user_ref = db.reference(f"users/{student_id}")
        
        user_data = safe_dict(user_ref.get())
        if not user_data:
            user_data = {'role': '학생', 'school': school_field.value, 'grade': grade_field.value, 'class': class_field.value, 'name': name_field.value, 'scores': {'total': 0, 'spelling': 0, 'literacy': 0, 'writing': 0, 'share': 0, 'comment': 0, 'jiphyeon': 0}, 'inventory': {}, 'completed': {}}
            user_ref.set(user_data)

        # 동기화 함수
        def update_anthology_post(topic, new_content):
            a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}"
            a_posts = safe_dict(db.reference(a_path).get())
            for a_pid, a_data in a_posts.items():
                if isinstance(a_data, dict) and str(a_data.get('topic', '')) == str(topic):
                    db.reference(f"{a_path}/{a_pid}").update({'content': new_content})

        def update_board_post(title, new_content):
            b_path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"
            b_posts = safe_dict(db.reference(b_path).get())
            for b_pid, b_data in b_posts.items():
                if isinstance(b_data, dict) and str(b_data.get('title', '')) == str(title) and str(b_data.get('author', '')) == name_field.value:
                    db.reference(f"{b_path}/{b_pid}").update({'content': new_content})

        def add_score(category, points):
            u_data = safe_dict(user_ref.get())
            scores = safe_dict(u_data.get('scores', {}))
            scores[category] = scores.get(category, 0) + points
            scores['total'] = scores.get('total', 0) + points
            user_ref.update({'scores': scores})
            if points > 0:
                page.snack_bar = ft.SnackBar(ft.Text(f"🎉 축하합니다! {points}점을 획득했습니다! (총점: {scores['total']}점)"), bgcolor="green")
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ 활동 취소(삭제)로 인해 {abs(points)}점이 차감되었습니다. (총점: {scores['total']}점)"), bgcolor="red")
            page.snack_bar.open = True; page.update()

        def get_level_info():
            u_data = safe_dict(user_ref.get())
            total = safe_dict(u_data.get('scores', {})).get('total', 0)
            settings_raw = db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get()
            settings = safe_dict(settings_raw)
            raw_lvls = settings.get("levels", {"2":100, "3":300, "4":600, "5":1000, "6":1500, "7":2100})
            lvls = {str(k): v for k, v in safe_dict(raw_lvls).items()}
            if total < int(lvls.get("2", 100)): return 1, "/level1.png", "(알)"
            elif total < int(lvls.get("3", 300)): return 2, "/level2.png", "(애벌레)"
            elif total < int(lvls.get("4", 600)): return 3, "/level3.png", "(도령)"
            elif total < int(lvls.get("5", 1000)): return 4, "/level4.png", "(유생)"
            elif total < int(lvls.get("6", 1500)): return 5, "/level5.png", "(선비)"
            elif total < int(lvls.get("7", 2100)): return 6, "/level6.png", "(관리)"
            else: return 7, "/level7.png", "(신선)"

        def get_home_view():
            u_data = safe_dict(user_ref.get())
            scores = safe_dict(u_data.get('scores', {}))
            lvl, image_file, desc = get_level_info()
            
            return ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Image(src=image_file, width=180, height=180, fit="contain"),
                ft.Text(desc, size=30, weight="bold", color="green800"),                              
                ft.Text(f"Lv.{lvl} {name_field.value} 학생", size=30, weight="bold"), 
                ft.Text(f"⭐ 나의 총점: {scores.get('total', 0)}점", size=24, color="blue", weight="bold")
            ], horizontal_alignment="center"), 
            alignment=ft.Alignment(0,0), 
            padding=40
        ),
        ft.Divider(thickness=2),
                ft.Text("📌 나의 세부 활동 점수", size=18, weight="bold"),
                ft.Row([
                    ft.Container(content=ft.Text(f"✍️ 맞춤법: {scores.get('spelling',0)}점"), bgcolor="#FDEEF4", padding=15, border_radius=10), 
                    ft.Container(content=ft.Text(f"📖 문해력: {scores.get('literacy',0)}점"), bgcolor="#EBF4FA", padding=15, border_radius=10), 
                    ft.Container(content=ft.Text(f"📝 글쓰기: {scores.get('writing',0)}점"), bgcolor="#F0F9ED", padding=15, border_radius=10), 
                    ft.Container(content=ft.Text(f"📢 게시판공유: {scores.get('share',0)}점"), bgcolor="#FFF3E0", padding=15, border_radius=10), 
                    ft.Container(content=ft.Text(f"💬 댓글: {scores.get('comment',0)}점"), bgcolor="#E0F7FA", padding=15, border_radius=10),
                    ft.Container(content=ft.Text(f"📚 집현전: {scores.get('jiphyeon',0)}점"), bgcolor="#FFF9E5", padding=15, border_radius=10)
                ], alignment="center", spacing=20, wrap=True)
            ], horizontal_alignment="center", scroll="always", expand=True)

        def get_spelling_view():
            test_data = safe_dict(db.reference(f"spelling_tests/{school_field.value}/{grade_field.value}/{class_field.value}").get())
            if not test_data: return ft.Column([ft.Text("선생님이 아직 문제를 내지 않으셨습니다.", size=20)], alignment="center")
            problems = test_data.get("problems", [])
            prob_ui = ft.Column(spacing=20)
            bonus_msg = ft.Text("", color="green", weight="bold", size=16)
            
            def play_voice(text):
                try:
                    temp_dir = __import__("tempfile").gettempdir()
                    full_path = os.path.join(temp_dir, f"v_{int(time.time() * 1000)}.mp3")
                    gTTS(text=text, lang='ko').save(full_path)
                    alias = f"v_{int(time.time() * 1000)}"
                    __import__("ctypes").windll.winmm.mciSendStringW(f'open "{full_path}" type mpegvideo alias {alias}', None, 0, 0)
                    __import__("ctypes").windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
                except: pass

            def check_answers(e):
                all_correct = True
                for i, p in enumerate(problems):
                    user_val = (prob_ui.controls[i].controls[2].value or "").strip().replace(" ", "")
                    correct_val = str(p.get('answer', '')).strip().replace(" ", "")
                    
                    if user_val == correct_val: 
                        prob_ui.controls[i].controls[3].value = "⭕ 정답!"
                        prob_ui.controls[i].controls[3].color = "green"
                    else: 
                        prob_ui.controls[i].controls[3].value = "❌ 다시!"
                        prob_ui.controls[i].controls[3].color = "red"
                        all_correct = False
                    prob_ui.controls[i].controls[3].update()
                
                u_data = safe_dict(user_ref.get())
                task_key = f"spell_{str(test_data.get('created_at','')).replace('.', '_')}"
                bonus_task_key = f"spell_bonus_{str(test_data.get('created_at','')).replace('.', '_')}"
                
                settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                base_pts = int(settings.get("activities", {}).get("spelling", 20))
                bonus_pts = int(settings.get("activities", {}).get("spelling_bonus", 10))
                
                gained = 0
                
                if not u_data.get('completed', {}).get(task_key, False):
                    add_score('spelling', base_pts)
                    db.reference(f"users/{student_id}/completed/{task_key}").set(True)
                    gained += base_pts
                
                if all_correct:
                    if not u_data.get('completed', {}).get(bonus_task_key, False):
                        add_score('spelling', bonus_pts)
                        db.reference(f"users/{student_id}/completed/{bonus_task_key}").set(True)
                        gained += bonus_pts
                        bonus_msg.value = f"🎁 모든 문제를 맞춰 보너스 점수({bonus_pts}점)가 제공됩니다!"
                    else:
                        bonus_msg.value = "🎁 이미 모든 문제를 맞춰 보너스 점수를 획득했습니다."
                else:
                    bonus_msg.value = ""
                
                if gained > 0:
                    page.snack_bar = ft.SnackBar(ft.Text(f"채점 완료! 총 {gained}점 획득!")); page.snack_bar.open = True
                else:
                    if all_correct:
                        page.snack_bar = ft.SnackBar(ft.Text("완벽합니다! (점수는 이미 모두 받았습니다)")); page.snack_bar.open = True
                    else:
                        page.snack_bar = ft.SnackBar(ft.Text("틀린 문제가 있습니다. 모두 고치면 보너스 점수를 받습니다!")); page.snack_bar.open = True

                page.update()

            for i, p in enumerate(problems): prob_ui.controls.append(ft.Row([ft.Text(f"{i+1}번", size=18, weight="bold"), ft.TextButton(content=ft.Text("🔊 듣기"), on_click=lambda _, t=p['audio']: play_voice(t)), ft.TextField(label="입력", width=400, on_change=lambda e: None), ft.Text("", size=16, weight="bold")]))
            return ft.Column([ft.Text("⚠️ 활동 기본 점수는 참여 시 1회 지급, 보너스는 100점 달성 시 1회 지급됩니다.", color="red", weight="bold"), ft.Text(f"✍️ {test_data.get('title', '연습')}", size=24, weight="bold"), ft.Divider(), prob_ui, ft.Row([ft.ElevatedButton("💯 채점 받기", on_click=check_answers, bgcolor="blue", color="white"), bonus_msg])], scroll="always", expand=True)

        def get_literacy_view():
            lit_data = safe_dict(db.reference(f"literacy_tests/{school_field.value}/{grade_field.value}/{class_field.value}").get())
            if not lit_data: return ft.Column([ft.Text("문해력 문제가 아직 없습니다.", size=20)])
            vocab = lit_data.get('vocab', []); passage = lit_data.get('passage', ''); questions = lit_data.get('questions', [])
            q_ui = ft.Column(spacing=15)
            bonus_msg = ft.Text("", color="green", weight="bold", size=16)
            
            def check_lit_answers(e):
                btn = e.control
                btn.text = "⏳ AI 채점 중..."
                btn.disabled = True
                page.update()

                all_correct = True
                for i, q in enumerate(questions):
                    user_val = (q_ui.controls[i].controls[1].value or "").strip()
                    correct_val = str(q.get('a', '')).strip()
                    
                    is_correct = False
                    if user_val.replace(" ", "") == correct_val.replace(" ", ""): 
                        is_correct = True
                    elif user_val: 
                        try:
                            prompt = f"질문: {q['q']}\n모범 정답: {correct_val}\n학생의 답: {user_val}\n\n학생의 답이 모범 정답과 의미상 일치하거나 문맥상 올바른 정답으로 인정할 수 있다면 오직 'O'만, 틀렸거나 부족하다면 오직 'X'만 출력하세요."
                            payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.1, "messages": [{"role": "system", "content": "You are a fair elementary school teacher. Output ONLY 'O' or 'X'."}, {"role": "user", "content": prompt}]}
                            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                            res = requests.post(TARGET_URL, json=payload, headers=headers).json()
                            ai_judge = res['choices'][0]['message']['content'].strip().upper()
                            if 'O' in ai_judge:
                                is_correct = True
                        except: pass
                    
                    if is_correct: 
                        q_ui.controls[i].controls[2].value = "⭕ 정답!"
                        q_ui.controls[i].controls[2].color = "green"
                    else: 
                        q_ui.controls[i].controls[2].value = f"❌ 다시!"
                        q_ui.controls[i].controls[2].color = "red"
                        all_correct = False
                    q_ui.controls[i].controls[2].update()
                
                u_data = safe_dict(user_ref.get())
                safe_passage = re.sub(r'[.#$\[\]]', '_', passage[:10])
                task_key = f"lit_{safe_passage}" 
                bonus_task_key = f"lit_bonus_{safe_passage}"
                
                settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                base_pts = int(settings.get("activities", {}).get("literacy", 50))
                bonus_pts = int(settings.get("activities", {}).get("literacy_bonus", 20))
                
                gained = 0
                if not u_data.get('completed', {}).get(task_key, False):
                    add_score('literacy', base_pts)
                    db.reference(f"users/{student_id}/completed/{task_key}").set(True)
                    gained += base_pts
                    
                if all_correct:
                    if not u_data.get('completed', {}).get(bonus_task_key, False):
                        add_score('literacy', bonus_pts)
                        db.reference(f"users/{student_id}/completed/{bonus_task_key}").set(True)
                        gained += bonus_pts
                        bonus_msg.value = f"🎁 모든 문제를 맞춰 보너스 점수({bonus_pts}점)가 제공됩니다!"
                    else:
                        bonus_msg.value = "🎁 이미 모든 문제를 맞춰 보너스 점수를 획득했습니다."
                else:
                    bonus_msg.value = ""
                    
                if gained > 0:
                    page.snack_bar = ft.SnackBar(ft.Text(f"채점 완료! 총 {gained}점 획득!")); page.snack_bar.open = True
                else:
                    if all_correct:
                        page.snack_bar = ft.SnackBar(ft.Text("완벽합니다! (점수는 이미 모두 받았습니다)")); page.snack_bar.open = True
                    else:
                        page.snack_bar = ft.SnackBar(ft.Text("틀린 문제가 있습니다. 모두 고치면 보너스 점수를 받습니다!")); page.snack_bar.open = True

                btn.text = "💯 채점 받기"
                btn.disabled = False
                page.update()

            for i, q in enumerate(questions): q_ui.controls.append(ft.Row([ft.Text(f"Q{i+1}. {q['q']}", weight="bold", width=350), ft.TextField(label="정답", width=200, on_change=lambda e: None), ft.Text("", weight="bold")]))
            
            return ft.Column([
                ft.Text("⚠️ 활동 기본 점수는 참여 시 1회 지급, 보너스는 100점 달성 시 1회 지급됩니다.", color="red", weight="bold"),
                ft.Text("📖 문해력 키우기 연습", size=24, weight="bold"),
                ft.Container(content=ft.Column([ft.Text("💡 핵심 어휘", color="blue", weight="bold")] + [ft.Text(f"[{v['word']}] {v['mean']}") for v in vocab]), bgcolor="#EBF4FA", padding=15, border_radius=10),
                ft.Container(content=ft.Column([ft.Text(passage, size=18)], scroll="always"), bgcolor="#F5F5F5", padding=20, border_radius=10, height=400),
                ft.Divider(), q_ui, ft.Row([ft.ElevatedButton("💯 채점 받기", on_click=check_lit_answers, bgcolor="blue", color="white"), bonus_msg])
            ], scroll="always", expand=True)

        def get_writing_view():
            task_data = safe_dict(db.reference(f"writing_tasks/{school_field.value}/{grade_field.value}/{class_field.value}").get())
            if not task_data: return ft.Column([ft.Text("주제가 아직 없습니다.", size=20)])
            
            # 이전에 작성한 문집 데이터 불러오기 (Pre-fill)
            a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}"
            a_posts = safe_dict(db.reference(a_path).get())
            existing_text = ""
            for pid, pdata in a_posts.items():
                if isinstance(pdata, dict) and str(pdata.get('topic', '')) == str(task_data.get('topic', '')):
                    existing_text = pdata.get('content', '')
                    break

            w_state = {"text": existing_text}
            def on_w_change(e): w_state["text"] = e.control.value
            writing_field = ft.TextField(multiline=True, expand=True, min_lines=12, hint_text="가이드라인을 생각하며 글을 써보세요.", value=existing_text, on_change=on_w_change)
            feedback_text = ft.Text("", color="blue", size=16, weight="bold")

            def get_ai_feedback(e):
                val = w_state["text"].strip()
                if len(val) < 10: 
                    page.snack_bar = ft.SnackBar(ft.Text("10자 이상 작성해주세요!")); page.snack_bar.open = True; page.update(); return
                try:
                    payload = {"model": "llama-3.3-70b-versatile", "temperature": 0.2, "messages": [{"role": "system", "content": "You are a helpful and kind writing teacher. 반드시 완벽하고 자연스러운 한국어(표준어)로만 작성하세요. 오타나 번역투가 없어야 합니다. 다정하게 작성하세요."}, {"role": "user", "content": f"초등 {grade_field.value} 학생 글이야. 맞춤법과 내용 3줄 피드백해줘.\n{val}"}]}
                    res = requests.post(TARGET_URL, json=payload, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}).json()
                    feedback_text.value = f"🤖 AI 피드백:\n{res['choices'][0]['message']['content']}"; feedback_text.color = "blue"; page.update()
                except: pass

            def save_writing(e):
                val = w_state["text"].strip()
                if len(val) < 10: 
                    page.snack_bar = ft.SnackBar(ft.Text("10자 이상 작성해주세요!")); page.snack_bar.open = True; page.update(); return
                
                existing_pid = None
                latest_a_posts = safe_dict(db.reference(a_path).get())
                for pid, pdata in latest_a_posts.items():
                    if isinstance(pdata, dict) and str(pdata.get('topic', '')) == str(task_data.get('topic')):
                        existing_pid = pid; break
                        
                settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                if existing_pid:
                    db.reference(f"{a_path}/{existing_pid}").update({'content': val})
                    update_board_post(task_data.get('topic'), val)
                    feedback_text.value = "💾 문집에 저장된 글이 성공적으로 수정되었습니다!"; feedback_text.color = "green"
                    page.snack_bar = ft.SnackBar(ft.Text("글이 성공적으로 수정되었습니다.")); page.snack_bar.open = True
                else:
                    db.reference(a_path).push({"topic": task_data.get('topic'), "content": val, "date": str(time.time())})
                    add_score('writing', int(settings.get("activities", {}).get("writing", 80)))
                    feedback_text.value = "💾 문집에 새 글이 성공적으로 저장되었습니다!"; feedback_text.color = "green"
                    page.snack_bar = ft.SnackBar(ft.Text("글이 성공적으로 저장되었습니다.")); page.snack_bar.open = True
                page.update()

            def share_writing(e):
                val = w_state["text"].strip()
                if len(val) < 10: 
                    page.snack_bar = ft.SnackBar(ft.Text("10자 이상 작성해주세요!")); page.snack_bar.open = True; page.update(); return
                
                b_path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"
                b_posts = safe_dict(db.reference(b_path).get())
                existing_pid = None
                for pid, pdata in b_posts.items():
                    if isinstance(pdata, dict) and str(pdata.get('title', '')) == str(task_data.get('topic')) and str(pdata.get('author', '')) == name_field.value:
                        existing_pid = pid; break
                        
                settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                if existing_pid:
                    db.reference(f"{b_path}/{existing_pid}").update({'content': val})
                    update_anthology_post(task_data.get('topic'), val)
                    feedback_text.value = "📢 게시판에 공유된 글이 성공적으로 수정되었습니다!"; feedback_text.color = "blue"
                    page.snack_bar = ft.SnackBar(ft.Text("공유된 글이 성공적으로 수정되었습니다.")); page.snack_bar.open = True
                else:
                    db.reference(b_path).push({"title": task_data.get('topic'), "content": val, "author": name_field.value, "likes": 0, "date": str(time.time()), "liked_users": {}})
                    add_score('share', int(settings.get("activities", {}).get("share", 20)))
                    feedback_text.value = "📢 게시판에 새 글이 성공적으로 공유되었습니다!"; feedback_text.color = "blue"
                    page.snack_bar = ft.SnackBar(ft.Text("글이 성공적으로 공유되었습니다.")); page.snack_bar.open = True
                page.update()

            return ft.Column([
                ft.Text("📝 오늘의 글쓰기 (자유롭게 무제한 저장/수정/공유 가능, 점수는 최초 1회만)", size=24, weight="bold"), ft.Container(content=ft.Column([ft.Text(f"주제: {task_data.get('topic','')}", size=18, weight="bold"), ft.Text(f"💡 {task_data.get('guideline','')}", color="gray")]), bgcolor="#F0F9ED", padding=15, border_radius=10),
                writing_field, 
                ft.Row([
                    ft.ElevatedButton("🤖 AI 검사", on_click=get_ai_feedback), 
                    ft.ElevatedButton("💾 문집에 저장", on_click=save_writing, bgcolor="green", color="white"),
                    ft.ElevatedButton("📢 게시판에 공유", on_click=share_writing, bgcolor="blue", color="white")
                ]), 
                feedback_text
            ], scroll="always", expand=True)

        def get_board_view():
            board_view = ft.Column(expand=True, scroll="always")
            path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"

            def show_shared_board_menu(is_init=False):
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Text("우리 반 글 공유 게시판", size=32, weight="bold", color="#5D4037"),
                        ft.Container(height=40),
                        ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("📚", size=60),
                                    ft.Text("주제별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("그동안 제시된 주제별로\n친구들의 글을 모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_topics_list()
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("👤", size=60),
                                    ft.Text("학생별 조회", size=24, weight="bold", color="#5D4037"),
                                    ft.Text("우리 반 친구들 이름별로\n작성한 글을 모아봅니다.", text_align="center", color="#757575")
                                ], alignment="center", horizontal_alignment="center"),
                                width=350, height=300, bgcolor="#F5F5F5", border_radius=20,
                                alignment=ft.Alignment(0, 0),
                                on_click=lambda _: show_students_list()
                            )
                        ], alignment="center", spacing=50)
                    ], horizontal_alignment="center", expand=True)
                )
                if not is_init: page.update()

            def show_topics_list():
                all_posts = safe_dict(db.reference(path).get())
                topics = set()
                for key, data in all_posts.items():
                    if isinstance(data, dict) and 'title' in data and data['title']: topics.add(str(data['title']))
                
                topic_buttons = [ft.ElevatedButton(topic, width=400, height=60, on_click=lambda e, t=topic: show_posts_by_filter("title", t)) for topic in sorted(list(topics))]
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_shared_board_menu()), ft.Text("주제별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=topic_buttons, scroll="always", spacing=10, horizontal_alignment="center") if topic_buttons else ft.Text("등록된 주제가 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def show_students_list():
                all_posts = safe_dict(db.reference(path).get())
                students = set()
                for key, data in all_posts.items():
                    if isinstance(data, dict) and 'author' in data and data['author']: students.add(str(data['author']))
                
                student_buttons = [ft.ElevatedButton(student, width=400, height=60, on_click=lambda e, s=student: show_posts_by_filter("author", s)) for student in sorted(list(students))]
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: show_shared_board_menu()), ft.Text("학생별 목록", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=student_buttons, scroll="always", spacing=10, horizontal_alignment="center") if student_buttons else ft.Text("등록된 학생이 없습니다.", size=16)
                    ], horizontal_alignment="center", expand=True)
                )
                page.update()

            def delete_post_action(post_id, post_title, post_author, filter_type, filter_value):
                db.reference(f"{path}/{post_id}").delete()
                # 연동 삭제 
                a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{post_author}"
                a_posts = safe_dict(db.reference(a_path).get())
                for apid, adata in a_posts.items():
                    if isinstance(adata, dict) and str(adata.get('topic', '')) == str(post_title): 
                        db.reference(f"{a_path}/{apid}").delete()
                page.snack_bar = ft.SnackBar(ft.Text("게시글이 삭제되었습니다.")); page.snack_bar.open = True
                show_posts_by_filter(filter_type, filter_value)

            def show_posts_by_filter(filter_type, filter_value):
                all_posts = safe_dict(db.reference(path).get())
                filtered_data = []
                max_likes = 0
                for pid, pdata in all_posts.items():
                    if isinstance(pdata, dict) and str(pdata.get(filter_type, '')) == str(filter_value):
                        likes = pdata.get('likes', 0)
                        if likes > max_likes: max_likes = likes
                        filtered_data.append((pid, pdata, likes))
                        
                filtered_posts = []
                for pid, pdata, likes in reversed(filtered_data):
                    best_badge = "👑 [BEST 인기글]" if likes > 0 and likes == max_likes else ""
                    c_ui = []
                    for cid, cdata in pdata.get('comments', {}).items():
                        if isinstance(cdata, dict): 
                            is_my_com = (str(cdata.get('author', '')) == name_field.value)
                            com_acts = []
                            if is_my_com:
                                def del_c_action(e, p=pid, c=cid):
                                    db.reference(f"{path}/{p}/comments/{c}").delete()
                                    add_score('comment', -int(safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get()).get("activities", {}).get("comment", 2)))
                                    show_posts_by_filter(filter_type, filter_value)
                                
                                def make_com_edit(p, c, curr_txt):
                                    def open_edit(_):
                                        st = {"text": str(curr_txt or "")}
                                        edit_f = ft.TextField(value=st["text"], on_change=lambda ev: st.update({"text": ev.control.value}))
                                        dlg = ft.AlertDialog(title=ft.Text("댓글 수정"))
                                        def save_c(ev):
                                            val = st["text"].strip()
                                            if val: db.reference(f"{path}/{p}/comments/{c}").update({'text': val})
                                            dlg.open = False; page.update(); show_posts_by_filter(filter_type, filter_value)
                                        def close_c(ev): dlg.open = False; page.update()
                                        dlg.content = edit_f
                                        dlg.actions = [ft.TextButton("저장", on_click=save_c), ft.TextButton("취소", on_click=close_c)]
                                        page.overlay.append(dlg)
                                        dlg.open = True
                                        page.update()
                                    return open_edit

                                com_acts = [
                                    ft.TextButton("✏️", on_click=make_com_edit(pid, cid, cdata.get('text',''))), 
                                    ft.TextButton("❌", icon_color="red", on_click=del_c_action)
                                ]
                            c_ui.append(ft.Row([ft.Text(f"↳ {cdata.get('author', '익명')}: {cdata.get('text', '')}", size=14), ft.Row(com_acts)], alignment="spaceBetween"))
                    
                    def make_add_comment(post_id):
                        st = {"text": ""}
                        cf = ft.TextField(hint_text="예쁜 칭찬 댓글을 달아주세요!", expand=True, height=40, on_change=lambda ev: st.update({"text": ev.control.value}))
                        def do_add(e):
                            val = st["text"].strip()
                            if not val: return
                            db.reference(f"{path}/{post_id}/comments").push({"author": name_field.value, "text": val})
                            settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                            add_score('comment', int(settings.get("activities", {}).get("comment", 2)))
                            page.snack_bar = ft.SnackBar(ft.Text("댓글이 등록되었습니다.")); page.snack_bar.open=True
                            show_posts_by_filter(filter_type, filter_value)
                        return cf, do_add

                    comment_field, add_comment_func = make_add_comment(pid)

                    liked_users = safe_dict(pdata.get('liked_users', {}))
                    user_name = name_field.value if name_field.value else "교사"
                    has_liked = user_name in liked_users
                    like_text = f"❤️ 좋아요 취소 {likes}" if has_liked else f"🤍 좋아요 {likes}"

                    def toggle_like(e, post_id=pid, curr_liked_users=liked_users, u_name=user_name):
                        if u_name in curr_liked_users:
                            del curr_liked_users[u_name]
                        else:
                            curr_liked_users[u_name] = True
                        db.reference(f"{path}/{post_id}/liked_users").set(curr_liked_users)
                        db.reference(f"{path}/{post_id}/likes").set(len(curr_liked_users))
                        show_posts_by_filter(filter_type, filter_value)
                    
                    post_acts = [ft.TextButton(content=ft.Text(like_text), on_click=toggle_like)]
                    
                    is_my_post = (str(pdata.get('author', '')) == name_field.value)
                    if is_my_post:
                        def open_post_edit(p, t, curr_txt):
                            p_state = {"text": str(curr_txt or "")}
                            edit_f = ft.TextField(value=p_state["text"], multiline=True, on_change=lambda ev: p_state.update({"text": ev.control.value}))
                            dlg = ft.AlertDialog(title=ft.Text("글 수정"))
                            def save_p(ev):
                                val = p_state["text"].strip()
                                if val:
                                    db.reference(f"{path}/{p}").update({'content': val})
                                    update_anthology_post(t, val)
                                dlg.open = False; page.update(); show_posts_by_filter(filter_type, filter_value)
                            def close_p(ev): dlg.open = False; page.update()
                            dlg.content = edit_f
                            dlg.actions = [ft.TextButton("저장", on_click=save_p), ft.TextButton("취소", on_click=close_p)]
                            page.overlay.append(dlg)
                            dlg.open = True
                            page.update()
                        post_acts.append(ft.TextButton("✏️ 수정", on_click=lambda _, p=pid, t=pdata.get('title',''), c=pdata.get('content',''): open_post_edit(p, t, c)))
                        post_acts.append(ft.TextButton("❌ 삭제", icon_color="red", on_click=lambda _, p=pid, t=pdata.get('title',''): delete_post_action(p, t, filter_type, filter_value)))

                    post_card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"📝 {pdata.get('title', '')} ({pdata.get('author', '')}) {best_badge}", weight="bold", size=18, color="blue" if best_badge else "black"), 
                                ft.Row(post_acts)
                            ], alignment="spaceBetween"),
                            ft.Text(pdata.get('content', ''), size=16), ft.Divider(height=1), ft.Text("💬 댓글", weight="bold"), ft.Column(c_ui),
                            ft.Row([comment_field, ft.ElevatedButton("댓글 등록", on_click=add_comment_func)])
                        ]), bgcolor="white", padding=20, border_radius=10, border=ft.border.all(1, "#E0E0E0")
                    )
                    filtered_posts.append(post_card)

                back_func = show_topics_list if filter_type == "title" else show_students_list
                board_view.controls.clear()
                board_view.controls.append(
                    ft.Column([
                        ft.Row([ft.TextButton("⬅️ 뒤로가기", on_click=lambda _: back_func()), ft.Text(f"'{filter_value}' 관련 글", size=28, weight="bold")], alignment="start"),
                        ft.Divider(),
                        ft.Column(controls=filtered_posts, scroll="always", spacing=20) if filtered_posts else ft.Text("해당 조건의 게시글이 없습니다.", size=16)
                    ], expand=True)
                )
                page.update()

            show_shared_board_menu(is_init=True)
            return board_view

        def get_jiphyeon_view():
            path = f"jiphyeonjeon_books/{school_field.value}/{grade_field.value}/{class_field.value}"
            view = ft.Column(expand=True, scroll="always")

            def show_bookshelf(is_init=False):
                view.controls.clear()
                books_row = ft.Row(wrap=True, spacing=20, run_spacing=20)
                books = safe_dict(db.reference(path).get())
                
                b_state = {"title": "", "author": "", "desc": ""}
                add_title = ft.TextField(label="내가 추천할 책 제목", width=200, on_change=lambda e: b_state.update({"title": e.control.value}))
                add_author = ft.TextField(label="지은이", width=150, on_change=lambda e: b_state.update({"author": e.control.value}))
                add_desc = ft.TextField(label="추천하는 이유", expand=True, on_change=lambda e: b_state.update({"desc": e.control.value}))
                def add_book(e):
                    val = b_state["title"].strip()
                    if val: db.reference(path).push({"title": val, "author": b_state["author"], "desc": b_state["desc"], "recommender": name_field.value, "created_at": str(time.time())}); show_bookshelf()
                        
                book_items = []
                max_avg = 0
                if books:
                    for bid, bdata in books.items():
                        if not isinstance(bdata, dict): continue
                        revs = safe_dict(bdata.get('reviews', {}))
                        avg = sum(r.get('rating',0) for r in revs.values())/len(revs) if revs else 0
                        if avg > max_avg: max_avg = avg
                        book_items.append((bid, bdata, revs, avg))
                        
                    for bid, bdata, revs, avg in book_items:
                        best_badge = "👑 [BEST 추천 도서]\n" if avg > 0 and avg == max_avg else ""
                        title_text = best_badge + str(bdata.get('title', ''))
                        book_cover = ft.Container(width=140, height=190, bgcolor="#8D6E63", border_radius=10, padding=15, alignment=ft.Alignment(0,0), content=ft.Column([ft.Text(title_text, weight="bold", size=16, color="white", text_align="center"), ft.Text(bdata.get('author', ''), size=12, color="#E0E0E0", text_align="center")], alignment="center", horizontal_alignment="center"), on_click=lambda _, i=bid, d=bdata: show_book_detail(i, d))
                        books_row.controls.append(ft.Container(width=160, content=ft.Column([book_cover, ft.Text(f"⭐ {avg:.1f} ({len(revs)}명 읽음)", size=12, color="#FF8F00", weight="bold"), ft.Text(f"추천인: {bdata.get('recommender', '교사')}", size=11, color="blue")], horizontal_alignment="center", spacing=3)))
                        
                view.controls.extend([
                    ft.Text("📚 집현전 (우리 반 도서관)", size=24, weight="bold"),
                    ft.Container(content=ft.Column([ft.Text("💡 친구들에게 좋은 책을 추천해 보세요!", weight="bold", color="blue"), ft.Row([add_title, add_author, add_desc, ft.ElevatedButton("➕ 추천", on_click=add_book, bgcolor="#8D6E63", color="white")])]), bgcolor="#F5F5F5", padding=15, border_radius=10),
                    ft.Divider(), books_row
                ])
                if not is_init: page.update()

            def show_book_detail(book_id, book_data):
                view.controls.clear()
                r_path = f"{path}/{book_id}/reviews"
                
                def make_edit_rev(rev_id, b_title, curr_txt):
                    def open_edit(_):
                        st = {"text": str(curr_txt or "")}
                        edit_f = ft.TextField(value=st["text"], multiline=True, on_change=lambda ev: st.update({"text": ev.control.value}))
                        dlg = ft.AlertDialog(title=ft.Text("감상평 수정"))
                        def save_r(ev):
                            val = st["text"].strip()
                            if val:
                                db.reference(f"{r_path}/{rev_id}").update({'text': val})
                                a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}"
                                a_posts = safe_dict(db.reference(a_path).get())
                                for apid, adata in a_posts.items():
                                    if isinstance(adata, dict) and str(adata.get('topic', '')) == f"[독서록] {b_title}" and str(adata.get('content', '')) == curr_txt:
                                        db.reference(f"{a_path}/{apid}").update({'content': val})
                            dlg.open = False; page.update(); load_r()
                        def close_r(ev): dlg.open = False; page.update()
                        dlg.content = edit_f
                        dlg.actions = [ft.TextButton("저장", on_click=save_r), ft.TextButton("취소", on_click=close_r)]
                        page.overlay.append(dlg)
                        dlg.open = True
                        page.update()
                    return open_edit

                def delete_rev_action(rev_id, rev_text, rev_author):
                    db.reference(f"{r_path}/{rev_id}").delete()
                    # 연동 삭제
                    a_path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{rev_author}"
                    a_posts = safe_dict(db.reference(a_path).get())
                    for apid, adata in a_posts.items():
                        if isinstance(adata, dict) and str(adata.get('topic', '')) == f"[독서록] {book_data.get('title','')}" and str(adata.get('content', '')) == str(rev_text):
                            db.reference(f"{a_path}/{apid}").delete()
                    load_r()

                r_col = ft.Column()
                def load_r():
                    r_col.controls.clear()
                    revs = safe_dict(db.reference(r_path).get())
                    if revs: 
                        for rid, r in revs.items():
                            if isinstance(r, dict):
                                is_mine = (str(r.get('author', '')) == "교사" or str(r.get('author', '')) == name_field.value)
                                acts = []
                                if is_mine:
                                    acts.append(ft.TextButton("✏️ 수정", on_click=make_edit_rev(rid, book_data.get('title',''), r.get('text',''))))
                                    acts.append(ft.TextButton("❌ 삭제", icon_color="red", on_click=lambda _, r_id=rid, txt=r.get('text',''), au=r.get('author',''): delete_rev_action(r_id, txt, au)))
                                r_col.controls.append(ft.Container(content=ft.Column([ft.Row([ft.Row([ft.Text(f"👤 {r.get('author')}", weight="bold"), ft.Text(f"⭐ {r.get('rating')}점", color="#FF8F00")]), ft.Row(acts)], alignment="spaceBetween"), ft.Text(r.get('text'))]), bgcolor="#F9F9F9", padding=10))
                    page.update()
                
                r_state = {"text": ""}
                
                def make_report_ui():
                    def on_t_change(ev): r_state["text"] = ev.control.value
                    report_field = ft.TextField(multiline=True, min_lines=5, expand=True, hint_text="느낀 점을 적어주세요!", on_change=on_t_change)
                    rating_dropdown = ft.Dropdown(label="별점", width=100, options=[ft.dropdown.Option(str(i)) for i in range(1,6)], value="5")
                    
                    def submit_report(e):
                        val = r_state["text"].strip()
                        if not val or len(val) < 5: return
                        
                        rating_val = int(rating_dropdown.value) if rating_dropdown.value else 5
                        
                        db.reference(r_path).push({"author": name_field.value if name_field.value else "교사", "rating": rating_val, "text": val, "created_at": str(time.time())})
                        db.reference(f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}").push({"topic": f"[독서록] {book_data.get('title','')}", "content": val, "date": str(time.time())})
                        
                        u_data = safe_dict(user_ref.get())
                        task_key = f"book_{str(book_id).replace('.', '_')}"
                        if not u_data.get('completed', {}).get(task_key, False):
                            settings = safe_dict(db.reference(f"score_settings/{school_field.value}/{grade_field.value}/{class_field.value}").get())
                            add_score('jiphyeon', int(settings.get("activities", {}).get("jiphyeon", 200)))
                            db.reference(f"users/{student_id}/completed/{task_key}").set(True)
                            page.snack_bar = ft.SnackBar(ft.Text("감상평이 등록되어 점수를 받았습니다!")); page.snack_bar.open=True
                        else:
                            page.snack_bar = ft.SnackBar(ft.Text("감상평이 추가 등록되었습니다. (점수는 1회만)")); page.snack_bar.open=True
                        
                        report_field.value = ""; rating_dropdown.value = "5"; r_state.update({"text": ""}); load_r()
                    
                    return rating_dropdown, report_field, submit_report

                rd, rf, sub_func = make_report_ui()
                load_r()
                view.controls.extend([
                    ft.Row([ft.TextButton("⬅️ 서가로 돌아가기", on_click=lambda _: show_bookshelf()), ft.Text(f"📖 {book_data.get('title')}", size=28, weight="bold")]),
                    ft.Container(content=ft.Column([ft.Text(f"지은이: {book_data.get('author')}", weight="bold"), ft.Text(book_data.get('desc'))]), bgcolor="#FFF8E1", padding=20),
                    ft.Divider(), ft.Text("💬 친구들의 감상평", weight="bold"), r_col,
                    ft.Divider(), ft.Text("📝 나의 독서 활동 (여러 번 추가 등록 가능)", weight="bold", color="blue"), rd, rf, ft.ElevatedButton("등록 및 점수 받기", on_click=sub_func)
                ])
                page.update()

            show_bookshelf(is_init=True)
            return view

        def get_anthology_view():
            view = ft.Column(expand=True, scroll="always")
            path = f"student_writings/{school_field.value}/{grade_field.value}/{class_field.value}/{name_field.value}"

            def open_anthology_edit(post_id, topic, current_txt):
                topic = str(topic or "")
                current_txt = str(current_txt or "")
                a_state = {"text": current_txt}
                
                edit_topic = ft.TextField(label="주제", value=topic, disabled=True)
                def on_change(ev): a_state["text"] = ev.control.value
                edit_content = ft.TextField(label="내용", value=current_txt, multiline=True, min_lines=5, on_change=on_change)
                
                dlg = ft.AlertDialog(title=ft.Text("내 글 수정하기"))
                def save_edit(ev):
                    new_text = a_state["text"].strip()
                    if not new_text: return
                    db.reference(f"{path}/{post_id}").update({'content': new_text})
                    
                    if topic.startswith("[독서록] "):
                        btitle = topic.replace("[독서록] ", "")
                        j_path = f"jiphyeonjeon_books/{school_field.value}/{grade_field.value}/{class_field.value}"
                        books = safe_dict(db.reference(j_path).get())
                        for bid, bdata in books.items():
                            if isinstance(bdata, dict) and str(bdata.get('title', '')) == btitle:
                                revs = safe_dict(db.reference(f"{j_path}/{bid}/reviews").get())
                                for rid, rdata in revs.items():
                                    if isinstance(rdata, dict) and str(rdata.get('author', '')) == name_field.value and str(rdata.get('text', '')) == current_txt: 
                                        db.reference(f"{j_path}/{bid}/reviews/{rid}").update({'text': new_text})
                    else:
                        update_board_post(topic, new_text)
                        
                    dlg.open = False; page.update(); load_my_writings()
                    
                def close_dialog(ev): dlg.open = False; page.update()
                
                dlg.content = ft.Column([edit_topic, edit_content], height=250)
                dlg.actions = [ft.TextButton("저장", on_click=save_edit), ft.TextButton("취소", on_click=close_dialog)]
                page.overlay.append(dlg)
                dlg.open = True
                page.update()

            def delete_my_post(post_id, topic, content):
                db.reference(f"{path}/{post_id}").delete()
                # 문집 글 지울 때는 점수 연동 차감을 생략하거나 별도 처리
                if topic.startswith("[독서록] "):
                    btitle = topic.replace("[독서록] ", "")
                    j_path = f"jiphyeonjeon_books/{school_field.value}/{grade_field.value}/{class_field.value}"
                    books = safe_dict(db.reference(j_path).get())
                    for bid, bdata in books.items():
                        if isinstance(bdata, dict) and bdata.get('title') == btitle:
                            revs = safe_dict(db.reference(f"{j_path}/{bid}/reviews").get())
                            for rid, rdata in revs.items():
                                if isinstance(rdata, dict) and rdata.get('author') == name_field.value and str(rdata.get('text', '')) == str(content): 
                                    db.reference(f"{j_path}/{bid}/reviews/{rid}").delete()
                else:
                    b_path = f"board_posts/{school_field.value}/{grade_field.value}/{class_field.value}"
                    b_posts = safe_dict(db.reference(b_path).get())
                    for b_pid, b_data in b_posts.items():
                        if isinstance(b_data, dict) and b_data.get('title') == topic and b_data.get('author') == name_field.value: 
                            db.reference(f"{b_path}/{b_pid}").delete()
                load_my_writings()

            def load_my_writings(is_init=False):
                view.controls.clear()
                writings_col = ft.Column(spacing=10)
                data = safe_dict(db.reference(path).get())
                
                for wid, wdata in reversed(list(data.items())):
                    if isinstance(wdata, dict):
                        writings_col.controls.append(
                            ft.Container(
                                content=ft.Column([
                                    ft.Text(f"📝 주제: {wdata.get('topic', '')}", weight="bold", size=18, color="#5D4037"),
                                    ft.Text(wdata.get('content', '')),
                                    ft.Divider(height=10),
                                    ft.Row([
                                        ft.TextButton("✏️ 수정", on_click=lambda _, p_id=wid, t=wdata.get('topic',''), c=wdata.get('content',''): open_anthology_edit(p_id, t, c)),
                                        ft.TextButton("❌ 삭제", icon_color="red", on_click=lambda _, p_id=wid, t=wdata.get('topic',''), c=wdata.get('content',''): delete_my_post(p_id, t, c))
                                    ], alignment="end")
                                ]), bgcolor="#F9F9F9", padding=15, border_radius=10
                            )
                        )
                if not writings_col.controls: writings_col.controls.append(ft.Text("아직 작성한 글이 없습니다.", color="gray"))

                def download_my_writings(e):
                    try:
                        d = safe_dict(db.reference(path).get())
                        with open(f"{name_field.value}_나만의문집.txt", "w", encoding="utf-8") as f:
                            f.write(f"--- {name_field.value} 학생의 나만의 문집 ---\n\n")
                            if d:
                                for wd in d.values(): 
                                    if isinstance(wd, dict): f.write(f"주제: {wd.get('topic')}\n내용: {wd.get('content')}\n\n")
                        page.snack_bar = ft.SnackBar(ft.Text("다운로드 완료!")); page.snack_bar.open=True; page.update()
                    except Exception as ex: print(ex)

                view.controls.extend([
                    ft.Row([ft.Text("📚 나만의 문집", size=24, weight="bold"), ft.ElevatedButton("💾 내 문집 전체 다운로드", on_click=download_my_writings, bgcolor="blue", color="white")], alignment="spaceBetween"),
                    ft.Text("내가 그동안 작성한 모든 글과 독서록이 이곳에 모입니다.", color="gray"),
                    ft.Divider(thickness=2), writings_col
                ])
                if not is_init: page.update()

            load_my_writings(is_init=True)
            return view
        
        def get_shop_view():
            shop_path = f"shop_items/{school_field.value}/{grade_field.value}/{class_field.value}"
            req_path = f"shop_requests/{school_field.value}/{grade_field.value}/{class_field.value}"
            shop_col = ft.Column(spacing=10); inv_col = ft.Column(spacing=10); pending_col = ft.Column(spacing=10)
            
            def load_shop(is_init=False):
                shop_col.controls.clear(); inv_col.controls.clear(); pending_col.controls.clear()
                u_data = safe_dict(user_ref.get())
                curr_points = u_data.get('scores',{}).get('total',0)
                inv = u_data.get('inventory', {})
                
                for iname, count in inv.items():
                    if count > 0:
                        def req_use(e, n=iname):
                            db.reference(req_path).push({"student_id": student_id, "student_name": name_field.value, "item_name": n, "approved": False})
                            page.snack_bar = ft.SnackBar(ft.Text("신청을 보냈습니다!")); page.snack_bar.open=True; page.update(); load_shop()
                        inv_col.controls.append(ft.Row([ft.Text(f"🎒 {iname} ({count}개)", weight="bold", width=200, color="blue"), ft.ElevatedButton("🙋‍♂️ 사용 신청", on_click=req_use)]))
                if not inv_col.controls: inv_col.controls.append(ft.Text("보유한 물건이 없습니다."))

                reqs = safe_dict(db.reference(req_path).get())
                for rid, rdata in reqs.items():
                    if isinstance(rdata, dict) and not rdata.get('approved') and str(rdata.get('student_id', '')) == str(student_id):
                        def cancel_req(e, r=rid): db.reference(f"{req_path}/{r}").delete(); page.snack_bar = ft.SnackBar(ft.Text("신청이 취소되었습니다.")); page.snack_bar.open=True; load_shop()
                        pending_col.controls.append(ft.Row([ft.Text(f"⏳ {rdata.get('item_name')} 신청 대기 중", width=200), ft.ElevatedButton("❌ 취소", on_click=cancel_req)]))
                if not pending_col.controls: pending_col.controls.append(ft.Text("대기 중인 신청이 없습니다.", color="gray"))

                items = safe_dict(db.reference(shop_path).get())
                for iid, idata in items.items():
                    if not isinstance(idata, dict): continue
                    def buy_item(e, n=idata.get('name'), p=idata.get('price')):
                        nonlocal curr_points
                        u = safe_dict(user_ref.get()); pts = u.get('scores',{}).get('total',0)
                        if pts >= p:
                            u['scores']['total'] -= p; 
                            i_dict = u.get('inventory', {})
                            i_dict[n] = i_dict.get(n, 0) + 1
                            user_ref.update({'scores': u['scores'], 'inventory': i_dict})
                            page.snack_bar = ft.SnackBar(ft.Text("구매 성공!")); page.snack_bar.open=True; load_shop()
                        else: page.snack_bar = ft.SnackBar(ft.Text("포인트 부족!")); page.snack_bar.open=True; page.update()
                    shop_col.controls.append(ft.Row([ft.Text(f"🎁 {idata.get('name')}", width=200), ft.Text(f"💰 {idata.get('price')}P", width=100), ft.ElevatedButton("구매", on_click=buy_item)]))
                if not shop_col.controls: shop_col.controls.append(ft.Text("등록된 물건이 없습니다.", color="gray"))
                if not is_init: page.update()

            load_shop(is_init=True)
            return ft.Column([ft.Text("🛒 꿈틀이 상점", size=24, weight="bold"), ft.Text(f"보유 포인트: {safe_dict(user_ref.get()).get('scores',{}).get('total',0)} P", color="red", weight="bold", size=20), ft.Divider(), ft.Text("🎒 내 가방", color="blue"), ft.Container(content=ft.Column([inv_col, ft.Divider(), ft.Text("대기 중인 신청", weight="bold"), pending_col]), bgcolor="#F5F5F5", padding=15), ft.Text("🎁 상점 구매", color="green"), ft.Container(content=shop_col, bgcolor="#F9F9F9", padding=15)], scroll="always", expand=True)

        student_content_area = ft.Container(expand=True, padding=40, content=get_home_view())

        def student_menu_click(e):
            m = e.control.data
            if m == "처음으로 (로그아웃)": show_login_screen(); return
            if m == "내 정보": student_content_area.content = get_home_view()
            elif m == "맞춤법 및 받아쓰기 연습": student_content_area.content = get_spelling_view()
            elif m == "문해력 연습": student_content_area.content = get_literacy_view()
            elif m == "글쓰기 연습": student_content_area.content = get_writing_view()
            elif m == "글 공유 게시판": student_content_area.content = get_board_view()
            elif m == "집현전(도서관)": student_content_area.content = get_jiphyeon_view()
            elif m == "나만의 문집": student_content_area.content = get_anthology_view()
            elif m == "상점": student_content_area.content = get_shop_view()
            page.update()

        s_menus = ["내 정보", "맞춤법 및 받아쓰기 연습", "문해력 연습", "글쓰기 연습", "글 공유 게시판", "집현전(도서관)", "나만의 문집", "상점", "처음으로 (로그아웃)"]
        s_buttons = [ft.Container(content=ft.ElevatedButton(m, data=m, width=240, height=45, style=ft.ButtonStyle(bgcolor={"": "#E0F7FA"}, color={"": "black"}), on_click=student_menu_click), margin=ft.margin.only(bottom=10)) for m in s_menus]

        page.add(
            ft.Row([
                ft.Container(width=280, bgcolor="#F5F5F5", padding=20, content=ft.Column([ft.Text("나의 학습 메뉴", size=24, weight="bold"), ft.Column(s_buttons, scroll="auto")], horizontal_alignment="center")), 
                ft.VerticalDivider(width=1), 
                student_content_area
            ], expand=True)
        )
        page.update()

    # ==========================================
    # [로그인 화면 및 화면 전환]
    # ==========================================
    login_box = ft.Container(
        bgcolor="#F2FFFFFF", padding=40, border_radius=20, width=420,
        content=ft.Column([
            ft.Text("나랏말싸미", size=50, weight="bold", color="#5D4037"),
            ft.Text(":꿈틀이의 문해력 키우기", size=30, weight="bold", color="#5D4037"),
            school_field,
            ft.Row([grade_field, class_field], alignment="center", width=300),
            name_field, pw_field, role_selection,
            ft.ElevatedButton("입장하기", color="white", bgcolor="#8D6E63", width=300, height=50, on_click=lambda e: enter_app(e))
        ], horizontal_alignment="center")
    )

    bg_img = ft.Image(src="bg.png", fit="cover", width=page.window_width, height=page.window_height)

    def show_login_screen():
        page.clean()
        page.add(ft.Stack([bg_img, ft.Container(content=login_box, alignment=ft.Alignment(0, 0), expand=True)], expand=True))
        page.update()

    def enter_app(e):
        if not school_field.value or not name_field.value:
            page.snack_bar = ft.SnackBar(ft.Text("학교명과 이름을 모두 입력해주세요.")); page.snack_bar.open=True; page.update()
            return
        if role_selection.value == "교사": show_teacher_dashboard()
        else: show_student_dashboard()

    page.on_resize = lambda e: (setattr(bg_img, "width", page.window_width), setattr(bg_img, "height", page.window_height), page.update())
    show_login_screen()

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", view=ft.AppView.WEB_BROWSER)