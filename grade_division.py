import hashlib
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk
import mysql.connector
from mysql.connector import errorcode

import ui_kit as ui
from machine_lock import is_allowed

DB_SETTINGS = {
    "host": "localhost",
    "user": "root",
    "password": "********",
    "database": "grade_db",
    "autocommit": True,  # save every change right away
}

# The admin password is stored as a hash so it can't be read out of the app.
# To change it, run this and paste the printed value below:
#   python -c "import hashlib; print(hashlib.sha256(b'NEW_PASSWORD').hexdigest())"
ADMIN_PASSWORD_HASH = "588327d0c94392136dbddef9aa8a2a7fb97aa9ce6d0768b2924dcc9e03857d04"

APP_NAME = "Grade Division"
MAX_INT = 2147483647  # largest number a MySQL INT column can hold


def to_int(text):
    try:
        value = int(text)
    except ValueError:
        return None
    if abs(value) > MAX_INT:
        return None
    return value


def show_db_error(error):
    messagebox.showerror(APP_NAME, f"Something went wrong with the database.\n\n{error}")


# ---------------------------------------------------------------- database

class Database:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_SETTINGS)

    def _run(self, sql, params=(), fetch=False):
        # reconnects if MySQL dropped the connection (e.g. app left open overnight)
        self.conn.ping(reconnect=True, attempts=3, delay=1)
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            if fetch:
                return cursor.fetchall()

    def register_student(self, id_no, name, cls):
        self._run(
            "INSERT INTO students (id, name, class) VALUES (%s, %s, %s)",
            (id_no, name, cls)
        )

    def add_grade(self, id_no, subject, score):
        self._run(
            "INSERT INTO grade (id, subject, score) VALUES (%s, %s, %s)",
            (id_no, subject, score)
        )

    def find_student(self, id_no):
        rows = self._run("SELECT name, class FROM students WHERE id = %s", (id_no,), fetch=True)
        return rows[0] if rows else None

    def all_students(self):
        return self._run("SELECT id, name, class FROM students ORDER BY id", fetch=True)

    def grades_for(self, id_no):
        return self._run(
            "SELECT subject, score FROM grade WHERE id = %s ORDER BY subject", (id_no,), fetch=True
        )

    def summary(self):
        students = self._run("SELECT COUNT(*) FROM students", fetch=True)[0][0]
        grades, subjects = self._run("SELECT COUNT(*), COUNT(DISTINCT subject) FROM grade", fetch=True)[0]
        return students, grades, subjects

    def close(self):
        try:
            self.conn.close()
        except mysql.connector.Error:
            pass


# ---------------------------------------------------------------- login

class LoginArt(ui.HeroCanvas):
    layout = "panel"

    def decorations(self, box):
        x0, y0, x1, y1 = box
        self.badge = (x0 + ui.px(104), y0 + (y1 - y0) * 0.30, ui.px(50))
        return [(*self.badge, (255, 255, 255, 235))], ()

    def draw_content(self, box):
        x0, y0, x1, y1 = box
        cx, cy, r = self.badge
        self.create_text(cx, cy, text=ui.ICON_CAP, font=(ui.ICON_FONT, -ui.px(46)), fill=ui.PRIMARY)
        left, width = x0 + ui.px(54), (x1 - x0) - ui.px(108)
        title = self.create_text(left, cy + r + ui.px(30), text="Every student's grades,\nall in one place.",
                                 font=ui.tk_font(32, "heavy"), fill=ui.INK, anchor="nw", width=width)
        self.create_text(left, self.bbox(title)[3] + ui.px(14),
                         text="Register students, save their scores and look back at records in a few clicks.",
                         font=ui.tk_font(17, "semi"), fill=ui.PRIMARY_DARK, anchor="nw", width=width)


class LoginScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app, fg_color=ui.CARD, corner_radius=0)
        self.app = app
        self.columnconfigure(0, weight=11, uniform="login")
        self.columnconfigure(1, weight=9, uniform="login")
        self.rowconfigure(0, weight=1)
        LoginArt(self, bg=ui.CARD, radius=30).grid(row=0, column=0, sticky="nsew", padx=(14, 0), pady=14)

        side = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=0)
        side.grid(row=0, column=1, sticky="nsew")
        form = ctk.CTkFrame(side, fg_color=ui.CARD, corner_radius=0)
        form.place(relx=0.5, rely=0.5, anchor="center")
        brand = ctk.CTkFrame(form, fg_color="transparent")
        brand.pack(anchor="w", pady=(0, 28))
        ctk.CTkLabel(brand, text="", image=ctk.CTkImage(ui.draw_logo(128), size=(40, 40))).pack(side="left")
        ctk.CTkLabel(brand, text=APP_NAME, font=ui.font(19, "heavy"), text_color=ui.INK).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(form, text="Welcome back!", font=ui.font(32, "heavy"), text_color=ui.INK).pack(anchor="w")
        ctk.CTkLabel(form, text="Log in to look after your students.", font=ui.font(16, "semi"),
                     text_color=ui.MUTED).pack(anchor="w", pady=(0, 24))

        self.name_field = ui.Field(form, "Your name", width=340)
        self.password_field = ui.Field(form, "Password", show="•", width=340)
        for field in (self.name_field, self.password_field):
            field.frame.pack(fill="x", pady=(0, 4))
            field.entry.bind("<Return>", lambda e: self.login())
        self.show_password = ctk.CTkCheckBox(
            form, text="Show password", command=self.toggle_password, font=ui.font(14, "semi"),
            text_color=ui.MUTED, fg_color=ui.PRIMARY, hover_color=ui.PRIMARY_HOVER, border_color=ui.FIELD_BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=2)
        self.show_password.pack(anchor="w", pady=(0, 20))
        ui.CandyButton(form, "Log in", self.login, height=54, size=16).pack(fill="x")
        self.after(100, self.name_field.entry.focus_set)

    def toggle_password(self):
        self.password_field.entry.configure(show="" if self.show_password.get() else "•")

    def login(self):
        username = self.name_field.get()
        password = self.password_field.var.get()
        if not username:
            self.name_field.error("Please enter your name.")
            self.name_field.entry.focus_set()
            return
        if hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
            self.password_field.set("")
            self.password_field.error("That password isn't right. Please try again.")
            self.password_field.entry.focus_set()
            return
        self.app.show_main(username)


# ---------------------------------------------------------------- pages

class Page(ctk.CTkFrame):
    title = ""
    subtitle = ""

    def __init__(self, parent, main):
        super().__init__(parent, fg_color=ui.BG, corner_radius=0)
        self.main = main
        self.db = main.db
        self.inner = ctk.CTkFrame(self, fg_color=ui.BG, corner_radius=0)
        self.inner.pack(fill="both", expand=True, padx=22, pady=(22, 10))
        if self.title:
            self.top = ctk.CTkFrame(self.inner, fg_color="transparent")
            self.top.pack(fill="x", padx=10, pady=(0, 8))
            ui.CandyButton(self.top, "Home", main.go_home, style="soft", icon=ui.ICON_HOME,
                           height=44, bg=ui.BG, size=14).pack(side="right")
            words = ctk.CTkFrame(self.top, fg_color="transparent")
            words.pack(side="left")
            ctk.CTkLabel(words, text=self.title, font=ui.font(30, "heavy"), text_color=ui.INK,
                         height=40, anchor="w").pack(anchor="w")
            ctk.CTkLabel(words, text=self.subtitle, font=ui.font(16, "semi"), text_color=ui.MUTED,
                         height=22, anchor="w").pack(anchor="w")

    def two_columns(self):
        row = ctk.CTkFrame(self.inner, fg_color="transparent")
        row.pack(fill="both", expand=True)
        row.columnconfigure(0, weight=3, uniform="cols")
        row.columnconfigure(1, weight=2, uniform="cols")
        row.rowconfigure(0, weight=1)
        return row

    def on_show(self, **kwargs):
        pass


class FormPage(Page):
    def make_form(self, parent, labels, save_text, save_icon):
        self.fields = [ui.Field(parent, label) for label in labels]
        for field in self.fields:
            field.frame.pack(fill="x", pady=(0, 4))
            field.entry.bind("<Return>", lambda e: self.save())
        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))
        ui.CandyButton(buttons, save_text, self.save, icon=save_icon, height=50).pack(side="left")
        ui.CandyButton(buttons, "Clear", self.clear, style="soft", height=50).pack(side="left", padx=(12, 0))
        self.notice = ui.Notice(parent)
        return self.fields

    def clear(self):
        for field in self.fields:
            field.set("")
            field.clear_message()
        self.notice.hide()
        self.fields[0].entry.focus_set()

    def save(self):
        raise NotImplementedError


def tips_card(parent, title, tips):
    card = ui.SoftCard(parent, fill="#F7F2FF", border="#ECE3FE", padding=24)
    head = ctk.CTkFrame(card.body, fg_color="transparent")
    head.pack(fill="x")
    ui.icon_bubble(head, ui.ICON_BULB, ui.PEACH, size=46, icon_size=21, fill=ui.CARD).pack(side="left")
    ctk.CTkLabel(head, text=title, font=ui.font(18, "heavy"), text_color=ui.INK).pack(side="left", padx=(12, 0))
    for tip in tips:
        line = ctk.CTkFrame(card.body, fg_color="transparent")
        line.pack(fill="x", pady=(14, 0))
        ui.icon_bubble(line, ui.ICON_CHECK, ui.MINT, size=26, icon_size=12, radius=13,
                       fill=ui.CARD).pack(side="left", anchor="n")
        ctk.CTkLabel(line, text=tip, font=ui.font(15, "semi"), text_color=ui.TEXT, anchor="w",
                     justify="left", wraplength=300).pack(side="left", padx=(10, 0))
    return card


class GreetingBanner(ui.HeroCanvas):
    def __init__(self, parent, username, **kwargs):
        super().__init__(parent, **kwargs)
        self.username = username

    def decorations(self, box):
        x0, y0, x1, y1 = box
        cy = (y0 + y1) / 2
        self.badge = (x0 + ui.px(72), cy, ui.px(38))
        now = datetime.now()
        if now.hour < 12:
            self.greeting, self.icon, self.icon_color = "Good morning", ui.ICON_SUN, "#D97706"
        elif now.hour < 18:
            self.greeting, self.icon, self.icon_color = "Good afternoon", ui.ICON_SUN, "#D97706"
        else:
            self.greeting, self.icon, self.icon_color = "Good evening", ui.ICON_MOON, ui.PRIMARY
        self.greeting = f"{self.greeting}, {self.username}!"
        self.date_text = f"{now:%A}, {now.day} {now:%B}"

        text_end = self.badge[0] + self.badge[2] + ui.px(24) + \
            tkfont.Font(font=ui.tk_font(30, "heavy")).measure(self.greeting)
        pill_width = tkfont.Font(font=ui.tk_font(15, "heavy")).measure(self.date_text) + ui.px(74)
        pill_height = ui.px(44)
        self.pill = (x1 - ui.px(30) - pill_width, cy - pill_height / 2, x1 - ui.px(30), cy + pill_height / 2)
        if text_end + ui.px(30) > self.pill[0]:
            self.pill = None    # a long name needs the room more than the date does
            return [(*self.badge, (255, 255, 255, 235))], ()
        return [(*self.badge, (255, 255, 255, 235))], [(*self.pill, (255, 255, 255, 205))]

    def draw_content(self, box):
        cx, cy, r = self.badge
        self.create_text(cx, cy, text=self.icon, font=(ui.ICON_FONT, -ui.px(36)), fill=self.icon_color)
        left = cx + r + ui.px(24)
        self.create_text(left, cy + ui.px(3), text=self.greeting,
                         font=ui.tk_font(30, "heavy"), fill=ui.INK, anchor="sw")
        self.create_text(left, cy + ui.px(6), text="What would you like to do today?",
                         font=ui.tk_font(17, "semi"), fill=ui.PRIMARY_DARK, anchor="nw")
        if self.pill:
            px0, py0, px1, py1 = self.pill
            mid = (py0 + py1) / 2
            self.create_text(px0 + ui.px(30), mid, text=ui.ICON_CALENDAR, font=(ui.ICON_FONT, -ui.px(17)),
                             fill=ui.PINK.strong)
            self.create_text(px0 + ui.px(50), mid, text=self.date_text, font=ui.tk_font(15, "heavy"),
                             fill=ui.INK, anchor="w")


class HomePage(Page):
    TILES = (
        (ui.ICON_ADD_PERSON, ui.VIOLET, "Register student", "Add someone new to the class list", "register", None),
        (ui.ICON_EDIT, ui.PINK, "Add grade", "Save a score for one subject", "grade", None),
        (ui.ICON_CLIPBOARD, ui.SKY, "Records", "See every student and their grades", "records", None),
        (ui.ICON_CALCULATOR, ui.PEACH, "Grade calculate", "Turn saved scores into results", "calculate", "Coming soon"),
    )

    def __init__(self, parent, main):
        super().__init__(parent, main)
        self.banner = GreetingBanner(self.inner, main.username, height=156)
        self.banner.pack(fill="x")

        stats = ctk.CTkFrame(self.inner, fg_color="transparent")
        stats.pack(fill="x")
        stats.columnconfigure((0, 1, 2), weight=1, uniform="stats")
        self.numbers = []
        for col, (icon, theme, label) in enumerate((
            (ui.ICON_PEOPLE, ui.VIOLET, "Students"),
            (ui.ICON_STAR, ui.PINK, "Grades saved"),
            (ui.ICON_BOOKS, ui.SKY, "Subjects"),
        )):
            card = ui.SoftCard(stats, height=108, padding=16)
            card.grid(row=0, column=col, sticky="ew")
            ui.icon_bubble(card.body, icon, theme, size=54, icon_size=24).pack(side="left")
            words = ctk.CTkFrame(card.body, fg_color="transparent")
            words.pack(side="left", padx=(14, 0))
            number = ctk.CTkLabel(words, text="-", font=ui.font(26, "heavy"), text_color=ui.INK, height=32, anchor="w")
            number.pack(anchor="w")
            ctk.CTkLabel(words, text=label, font=ui.font(14, "semi"), text_color=ui.MUTED,
                         height=20, anchor="w").pack(anchor="w")
            self.numbers.append(number)

        heading = ctk.CTkFrame(self.inner, fg_color="transparent")
        heading.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(heading, text="Choose what to do", font=ui.font(21, "heavy"), text_color=ui.INK).pack(side="left")
        ctk.CTkLabel(heading, text="Tip: press 1, 2, 3 or 4", font=ui.font(14, "semi"),
                     text_color=ui.MUTED).pack(side="right")

        grid = ctk.CTkFrame(self.inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="tiles")
        self.tiles = []
        for i, (icon, theme, title, text, page, badge) in enumerate(self.TILES):
            tile = ui.Tile(grid, icon, theme, title, text, lambda p=page: main.open_page(p), badge)
            tile.grid(row=i // 2, column=i % 2, sticky="ew")
            self.tiles.append(tile)

    def on_show(self, **kwargs):
        for tile in self.tiles:
            tile.reset()
        self.banner.refresh()
        try:
            counts = self.db.summary()
        except mysql.connector.Error as e:
            show_db_error(e)
            return
        for label, value in zip(self.numbers, counts):
            label.configure(text=str(value))


class RegisterPage(FormPage):
    title = "Register a student"
    subtitle = "Add someone new to your class list."

    def __init__(self, parent, main):
        super().__init__(parent, main)
        row = self.two_columns()
        card = ui.SoftCard(row, padding=26)
        card.grid(row=0, column=0, sticky="new")
        self.id_field, self.name_field, self.class_field = self.make_form(
            card.body, ["Student ID", "Name", "Class"], "Register student", ui.ICON_ADD_PERSON)
        tips_card(row, "Good to know", [
            "IDs are whole numbers, like 12.",
            "Each ID belongs to one student only.",
            "You can add grades right after saving.",
        ]).grid(row=0, column=1, sticky="new")

    def on_show(self, student_id=None, **kwargs):
        if student_id is None:
            self.id_field.entry.focus_set()
            return
        self.clear()
        self.id_field.set(str(student_id))
        self.name_field.entry.focus_set()

    def save(self):
        id_text = self.id_field.get()
        id_no = to_int(id_text)
        name = self.name_field.get()
        cls = self.class_field.get()

        bad = []
        if not id_text:
            self.id_field.error("Please enter a student ID.")
            bad.append(self.id_field)
        elif id_no is None or id_no < 1:
            self.id_field.error("Student ID must be a whole number, like 12.")
            bad.append(self.id_field)
        if not name:
            self.name_field.error("Please enter the student's name.")
            bad.append(self.name_field)
        elif len(name) > 128:
            self.name_field.error("Name is too long (128 characters max).")
            bad.append(self.name_field)
        if not cls:
            self.class_field.error("Please enter the class.")
            bad.append(self.class_field)
        elif len(cls) > 30:
            self.class_field.error("Class is too long (30 characters max).")
            bad.append(self.class_field)
        if bad:
            self.notice.hide()
            bad[0].entry.focus_set()
            return

        try:
            self.db.register_student(id_no, name, cls)
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                self.id_field.error(f"A student with ID {id_no} already exists.")
                self.id_field.entry.focus_set()
            else:
                show_db_error(e)
            return

        self.clear()
        self.notice.show(f"{name} (ID {id_no}) is registered!", "Add grades",
                         lambda: self.main.open_page("grade", student_id=id_no))


class AddGradePage(FormPage):
    title = "Add a grade"
    subtitle = "Save a subject score for one of your students."

    def __init__(self, parent, main):
        super().__init__(parent, main)
        row = self.two_columns()
        card = ui.SoftCard(row, padding=26)
        card.grid(row=0, column=0, sticky="new")
        self.id_field, self.subject_field, self.score_field = self.make_form(
            card.body, ["Student ID", "Subject", "Score"], "Save grade", ui.ICON_STAR)
        side = ui.SoftCard(row, padding=24)
        side.grid(row=0, column=1, sticky="new")
        self.preview = ui.StudentPanel(side.body)
        self.preview.pack(fill="both", expand=True)
        self._lookup_job = None
        self.id_field.var.trace_add("write", lambda *_: self.schedule_lookup())
        self.show_preview()

    def on_show(self, student_id=None, **kwargs):
        if student_id is None:
            self.show_preview()
            self.id_field.entry.focus_set()
            return
        self.clear()
        self.id_field.set(str(student_id))
        self.show_preview()
        self.subject_field.entry.focus_set()

    def schedule_lookup(self):
        if self._lookup_job:
            self.after_cancel(self._lookup_job)
        self._lookup_job = self.after(300, self.show_preview)

    def show_preview(self):
        self._lookup_job = None
        id_no = to_int(self.id_field.get())
        if id_no is None:
            self.preview.show_message(ui.ICON_CONTACT, ui.VIOLET, "Who's this for?",
                                      "Type a student ID and they'll show up here.")
            return
        try:
            student = self.db.find_student(id_no)
            grades = self.db.grades_for(id_no) if student else []
        except mysql.connector.Error:
            return
        if student:
            self.preview.show_student(id_no, student[0], student[1], grades, limit=5)
        else:
            self.preview.show_message(
                ui.ICON_CONTACT, ui.PEACH, "No student found",
                f"There's no student with ID {id_no} yet.",
                button=("Register this student", lambda: self.main.open_page("register", student_id=id_no),
                        ui.ICON_ADD_PERSON))

    def save(self):
        id_text = self.id_field.get()
        id_no = to_int(id_text)
        subject = self.subject_field.get()
        score_text = self.score_field.get()
        score = to_int(score_text)

        bad = []
        if not id_text:
            self.id_field.error("Please enter a student ID.")
            bad.append(self.id_field)
        elif id_no is None or id_no < 1:
            self.id_field.error("Student ID must be a whole number, like 12.")
            bad.append(self.id_field)
        if not subject:
            self.subject_field.error("Please enter the subject.")
            bad.append(self.subject_field)
        elif len(subject) > 128:
            self.subject_field.error("Subject is too long (128 characters max).")
            bad.append(self.subject_field)
        if not score_text:
            self.score_field.error("Please enter the score.")
            bad.append(self.score_field)
        elif score is None:
            self.score_field.error("Score must be a whole number, like 85.")
            bad.append(self.score_field)
        if bad:
            self.notice.hide()
            bad[0].entry.focus_set()
            return

        try:
            self.db.add_grade(id_no, subject, score)
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_NO_REFERENCED_ROW_2:
                self.id_field.error(f"No student with ID {id_no}. Register them first.")
                self.id_field.entry.focus_set()
            elif e.errno == errorcode.ER_DUP_ENTRY:
                self.subject_field.error(f"This student already has a grade for {subject}.")
                self.subject_field.entry.focus_set()
            else:
                show_db_error(e)
            return

        try:
            student = self.db.find_student(id_no)
        except mysql.connector.Error:
            student = None
        who = student[0] if student else f"student {id_no}"
        self.subject_field.set("")
        self.score_field.set("")
        self.show_preview()
        self.notice.show(f"Saved! {subject}: {score} for {who}.")
        self.subject_field.entry.focus_set()


class RecordsPage(Page):
    title = "Student records"
    subtitle = "Pick a student to see all of their grades."

    def __init__(self, parent, main):
        super().__init__(parent, main)
        ui.CandyButton(self.top, "Refresh", self.refresh, style="soft", icon=ui.ICON_REFRESH,
                       height=44, bg=ui.BG, size=14).pack(side="right", padx=(0, 12))
        row = self.two_columns()

        left = ui.SoftCard(row, padding=20, expand=True)
        left.grid(row=0, column=0, sticky="nsew")
        head = ctk.CTkFrame(left.body, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Students", font=ui.font(18, "heavy"), text_color=ui.INK).pack(side="left")
        self.count = ui.chip(head, "0", ui.VIOLET, size=13)
        self.count.pack(side="left", padx=(10, 0))

        box = ctk.CTkFrame(left.body, fg_color=ui.CARD)
        box.pack(fill="both", expand=True, pady=(12, 0))
        self.table = ttk.Treeview(box, columns=("id", "name", "class"), show="headings",
                                  selectmode="browse", style="Sweet.Treeview")
        for key, heading, width in (("id", "ID", 110), ("name", "Name", 190), ("class", "Class", 110)):
            self.table.heading(key, text=heading, anchor="w")
            self.table.column(key, width=ui.px(width), minwidth=ui.px(60), anchor="w")
        scrollbar = ctk.CTkScrollbar(box, command=self.table.yview, fg_color=ui.CARD,
                                     button_color=ui.LINE, button_hover_color=ui.FIELD_BORDER)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", lambda e: self.show_grades())

        right = ui.SoftCard(row, padding=24, expand=True)
        right.grid(row=0, column=1, sticky="nsew")
        self.panel = ui.StudentPanel(right.body, scroll=True)
        self.panel.pack(fill="both", expand=True)

    def on_show(self, **kwargs):
        self.refresh()

    def refresh(self):
        try:
            rows = self.db.all_students()
        except mysql.connector.Error as e:
            show_db_error(e)
            return
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        for id_no, name, cls in rows:
            self.table.insert("", "end", iid=str(id_no), values=(id_no, name, cls))
        self.count.configure(text=str(len(rows)))
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
        elif rows:
            self.table.selection_set(str(rows[0][0]))
        self.show_grades()

    def show_grades(self):
        selected = self.table.selection()
        if not selected:
            if self.table.get_children():
                self.panel.show_message(ui.ICON_PEOPLE, ui.SKY, "Pick a student",
                                        "Choose someone from the list to see their grades here.")
            else:
                self.panel.show_message(
                    ui.ICON_ADD_PERSON, ui.VIOLET, "No students yet",
                    "Register your first student and they'll appear here.",
                    button=("Register a student", lambda: self.main.open_page("register"), ui.ICON_ADD_PERSON))
            return
        id_no = int(selected[0])
        _, name, cls = self.table.item(selected[0], "values")
        try:
            grades = self.db.grades_for(id_no)
        except mysql.connector.Error as e:
            show_db_error(e)
            return
        self.panel.show_student(id_no, name, cls, grades,
                                button=("Add a grade", lambda: self.main.open_page("grade", student_id=id_no)))


class CalculatePage(Page):
    title = "Grade calculate"
    subtitle = "Turn saved scores into results."

    def __init__(self, parent, main):
        super().__init__(parent, main)
        card = ui.SoftCard(self.inner, padding=40)
        card.pack(fill="x")
        box = ctk.CTkFrame(card.body, fg_color="transparent")
        box.pack(pady=10)
        ui.icon_bubble(box, ui.ICON_CALCULATOR, ui.PEACH, size=88, icon_size=40, radius=30).pack()
        ctk.CTkLabel(box, text="Coming soon!", font=ui.font(26, "heavy"), text_color=ui.INK).pack(pady=(18, 4))
        ctk.CTkLabel(box, text="This part of the app isn't built yet, so there's nothing to calculate for now.",
                     font=ui.font(16, "semi"), text_color=ui.MUTED, wraplength=460, justify="center").pack()


# ---------------------------------------------------------------- main window

class MainScreen(ctk.CTkFrame):
    PAGES = {
        "home": HomePage,
        "register": RegisterPage,
        "grade": AddGradePage,
        "records": RecordsPage,
        "calculate": CalculatePage,
    }

    def __init__(self, app, username):
        super().__init__(app, fg_color=ui.BG, corner_radius=0)
        self.app = app
        self.db = app.db
        self.username = username
        self.pages = {}
        self.current_page = None

        header = ctk.CTkFrame(self, fg_color=ui.CARD, corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkFrame(self, fg_color=ui.LINE, corner_radius=0, height=2).pack(fill="x")

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=32)
        logo = ctk.CTkLabel(brand, text="", image=ctk.CTkImage(ui.draw_logo(128), size=(38, 38)))
        logo.pack(side="left")
        name = ctk.CTkLabel(brand, text=APP_NAME, font=ui.font(20, "heavy"), text_color=ui.INK, cursor="hand2")
        name.pack(side="left", padx=(12, 0))
        for widget in (logo, name):
            widget.bind("<Button-1>", lambda e: self.go_home())

        ui.CandyButton(header, "Log out", app.show_login, style="soft", icon=ui.ICON_SIGN_OUT,
                       height=42, bg=ui.CARD, size=14).pack(side="right", padx=(0, 32))
        ctk.CTkLabel(header, text=username, font=ui.font(16, "bold"), text_color=ui.INK).pack(side="right", padx=(0, 20))
        ui.avatar(header, username, size=42).pack(side="right", padx=(0, 10))

        self.content = ctk.CTkFrame(self, fg_color=ui.BG, corner_radius=0)
        self.content.pack(fill="both", expand=True)
        self.open_page("home")

    def go_home(self):
        self.open_page("home")

    def open_page(self, name, **kwargs):
        if self.current_page:
            self.current_page.pack_forget()
        if name not in self.pages:
            self.pages[name] = self.PAGES[name](self.content, self)
        self.current_page = self.pages[name]
        self.current_page.pack(fill="both", expand=True)
        self.current_page.on_show(**kwargs)
        if name == "home":
            for n, tile in enumerate(self.pages["home"].tiles, start=1):
                self.app.bind(f"<Key-{n}>", lambda e, t=tile: t.command())
        else:
            self.unbind_keys()

    def unbind_keys(self):
        for n in range(1, 5):
            self.app.unbind(f"<Key-{n}>")


class App(ctk.CTk):
    def __init__(self, db):
        super().__init__(fg_color=ui.CARD)
        ui.setup(self)
        self.db = db
        self.screen = None
        self.title(APP_NAME)
        try:
            self.iconbitmap(ui.resource_path("app.ico"))
        except tk.TclError:
            pass

        width = min(1060, int(self.winfo_screenwidth() / ui.SCALE) - 40)
        height = min(710, int(self.winfo_screenheight() / ui.SCALE) - 90)
        x = (self.winfo_screenwidth() - ui.px(width)) // 2
        y = max(0, (self.winfo_screenheight() - ui.px(height)) // 4)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(960, width), min(660, height))
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.show_login()

    def switch_to(self, screen):
        if self.screen:
            if isinstance(self.screen, MainScreen):
                self.screen.unbind_keys()
            self.screen.destroy()
        self.screen = screen
        screen.pack(fill="both", expand=True)

    def show_login(self):
        self.switch_to(LoginScreen(self))

    def show_main(self, username):
        self.switch_to(MainScreen(self, username))

    def quit_app(self):
        self.destroy()
        self.db.close()


# ---------------------------------------------------------------- program start

def startup_error(message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(APP_NAME, message)
    root.destroy()
    sys.exit(1)


def main():
    if not is_allowed():
        startup_error("This app can only be used on its owner's laptop.")

    try:
        db = Database()
    except mysql.connector.Error as e:
        startup_error(f"Could not connect to the database.\n\nMake sure MySQL is running.\n\nDetails: {e}")

    ctk.set_appearance_mode("light")
    ui.load_fonts()
    App(db).mainloop()


if __name__ == "__main__":
    main()
