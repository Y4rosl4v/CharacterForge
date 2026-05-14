from datetime import datetime
from pathlib import Path
from io import BytesIO
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import os
import random

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from generator import generate_character, edit_character_with_ai  # ИЗМЕНЕНО: добавили edit_character_with_ai

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
IMAGE_DIR = BASE_DIR / "static" / "generated"

EXPORT_DIR.mkdir(exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


app = Flask(__name__)

app.config["SECRET_KEY"] = "dev-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///characters.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    characters = db.relationship(
        "Character",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    source_prompt = db.Column(db.Text, nullable=False)

    name = db.Column(db.String(120), nullable=False)
    character_class = db.Column(db.String(120), nullable=False)
    race = db.Column(db.String(120), nullable=False)

    strength = db.Column(db.Integer, nullable=False)
    intelligence = db.Column(db.Integer, nullable=False)
    agility = db.Column(db.Integer, nullable=False)
    magic = db.Column(db.Integer, nullable=False)

    description = db.Column(db.Text, nullable=False)
    goal = db.Column(db.Text, nullable=False)
    abilities = db.Column(db.Text, nullable=False)

    image_prompt = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def ensure_database_schema():
    """
    Добавляет новые поля в уже существующую SQLite-базу без удаления данных.
    Нужно, потому что раньше таблица character была создана без image_prompt.
    """

    with db.engine.connect() as connection:
        columns = connection.exec_driver_sql(
            "PRAGMA table_info(character)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "image_prompt" not in column_names:
            connection.exec_driver_sql(
                "ALTER TABLE character ADD COLUMN image_prompt TEXT"
            )
            connection.commit()


def character_to_text(character):
    return f"""Карточка игрового персонажа

Имя: {character.name}
Класс: {character.character_class}
Раса: {character.race}

Характеристики:
Сила: {character.strength}/10
Интеллект: {character.intelligence}/10
Ловкость: {character.agility}/10
Магия: {character.magic}/10

Описание:
{character.description}

Цель:
{character.goal}

Способности:
{character.abilities}

Исходный запрос:
{character.source_prompt}
"""


def get_pdf_font_path():
    font_paths = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
    ]

    for font_path in font_paths:
        if font_path.exists():
            return font_path

    return None


def get_pil_font(size=28):
    font_path = get_pdf_font_path()

    if font_path:
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except Exception:
            pass

    return ImageFont.load_default()


def get_character_image_path(character):
    return IMAGE_DIR / f"character_{character.id}.png"


def get_character_image_filename(character):
    image_path = get_character_image_path(character)

    if image_path.exists():
        return f"generated/character_{character.id}.png"

    return "generated/placeholder.png"


def get_image_version(character):
    image_path = get_character_image_path(character)

    if image_path.exists():
        return int(image_path.stat().st_mtime)

    return 1


def create_placeholder_image():
    file_path = IMAGE_DIR / "placeholder.png"

    if file_path.exists():
        return

    width = 768
    height = 1024

    image = Image.new("RGB", (width, height), (12, 14, 28))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        r = int(12 + y / height * 24)
        g = int(14 + y / height * 18)
        b = int(28 + y / height * 54)
        draw.line((0, y, width, y), fill=(r, g, b))

    draw.rounded_rectangle(
        (55, 65, width - 55, height - 65),
        radius=36,
        outline=(139, 92, 246),
        width=4
    )

    font_title = get_pil_font(44)
    font_text = get_pil_font(27)

    draw.text((80, 160), "Иллюстрация", font=font_title, fill=(255, 255, 255))
    draw.text((80, 220), "ещё не создана", font=font_title, fill=(196, 181, 253))

    draw.text(
        (80, 340),
        "Нажми кнопку ниже,\nчтобы сгенерировать\nanime-изображение.",
        font=font_text,
        fill=(220, 220, 245)
    )

    image.save(file_path, "PNG")


def create_error_image(character, error_text="AI image generation failed"):
    width = 768
    height = 1024

    image = Image.new("RGB", (width, height), (12, 14, 28))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        r = int(12 + y / height * 24)
        g = int(14 + y / height * 18)
        b = int(28 + y / height * 54)
        draw.line((0, y, width, y), fill=(r, g, b))

    draw.rounded_rectangle(
        (50, 60, width - 50, height - 60),
        radius=34,
        outline=(139, 92, 246),
        width=4
    )

    font_title = get_pil_font(42)
    font_text = get_pil_font(25)

    draw.text(
        (80, 140),
        "Изображение не создано",
        font=font_title,
        fill=(255, 255, 255)
    )

    draw.text(
        (80, 215),
        "Проверь интернет или API.",
        font=font_text,
        fill=(220, 220, 245)
    )

    draw.text(
        (80, 330),
        character.name,
        font=font_title,
        fill=(196, 181, 253)
    )

    draw.text(
        (80, 390),
        f"{character.character_class} · {character.race}",
        font=font_text,
        fill=(230, 230, 255)
    )

    draw.text(
        (80, 520),
        str(error_text)[:420],
        font=font_text,
        fill=(255, 170, 170)
    )

    image.save(get_character_image_path(character), "PNG")


def build_anime_image_prompt(character):
    """
    Главное изменение:
    картинка строится не по нашим if/else-правилам,
    а по image_prompt, который сгенерировала языковая модель.
    """

    if character.image_prompt:
        return character.image_prompt

    return (
        f"anime fantasy RPG character, full body illustration, "
        f"race: {character.race}, class: {character.character_class}, "
        f"description: {character.description}, abilities: {character.abilities}, "
        f"high quality digital art, detailed costume, dramatic lighting, "
        f"solo character, no text, no logo, no watermark"
    )


def download_image_from_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 CharacterForgeStudentProject/1.0",
            "Accept": "image/png,image/jpeg,image/webp,*/*"
        }
    )

    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "")

        if "image" not in content_type:
            raise ValueError(f"API вернул не изображение. Content-Type: {content_type}")

        return response.read()


def generate_character_image(character):
    """
    Генерация картинки выполняется только при нажатии кнопки.
    При обычном открытии страниц внешний API не вызывается, поэтому сайт не должен лагать.
    """

    prompt = build_anime_image_prompt(character)
    seed = random.randint(1, 999999999)
    encoded_prompt = quote(prompt, safe="")

    image_path = get_character_image_path(character)

    urls = [
        (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width=768"
            f"&height=1024"
            f"&model=flux"
            f"&seed={seed}"
            f"&nologo=true"
            f"&enhance=true"
            f"&safe=true"
        )
    ]

    api_key = os.getenv("POLLINATIONS_API_KEY")

    if api_key:
        urls.append(
            f"https://gen.pollinations.ai/image/{encoded_prompt}"
            f"?width=768"
            f"&height=1024"
            f"&model=flux"
            f"&seed={seed}"
            f"&enhance=true"
            f"&safe=true"
            f"&key={quote(api_key, safe='')}"
        )

    last_error = None

    for url in urls:
        try:
            image_data = download_image_from_url(url)
            image = Image.open(BytesIO(image_data)).convert("RGB")
            image.save(image_path, "PNG")
            return True

        except HTTPError as error:
            last_error = f"HTTP Error {error.code}: {error.reason}"

            if error.code == 429 and not api_key:
                break

        except URLError as error:
            last_error = f"Network error: {error.reason}"

        except Exception as error:
            last_error = error

    # Если у персонажа уже была хорошая картинка, не затираем её ошибкой.
    if image_path.exists():
        return False

    create_error_image(character, last_error)
    return False


@app.context_processor
def utility_processor():
    def character_image_src(character):
        image_path = get_character_image_path(character)

        if image_path.exists():
            return url_for(
                "static",
                filename=f"generated/character_{character.id}.png",
                v=int(image_path.stat().st_mtime)
            )

        return url_for("static", filename="generated/placeholder.png")

    return dict(character_image_src=character_image_src)


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Заполните все поля.")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash("Логин должен быть не короче 3 символов.")
            return redirect(url_for("register"))

        if len(password) < 5:
            flash("Пароль должен быть не короче 5 символов.")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash("Пользователь с таким логином уже существует.")
            return redirect(url_for("register"))

        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        login_user(user)

        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверный логин или пароль.")
            return redirect(url_for("login"))

        login_user(user)

        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    prompt = request.form.get("prompt", "").strip()

    if len(prompt) < 5:
        flash("Описание персонажа слишком короткое.")
        return redirect(url_for("index"))

    existing_characters = Character.query.filter_by(
        user_id=current_user.id
    ).all()

    used_races = [character.race for character in existing_characters]
    used_classes = [character.character_class for character in existing_characters]
    used_names = [character.name for character in existing_characters]

    try:
        character_data = generate_character(
            prompt,
            used_races=used_races,
            used_classes=used_classes,
            used_names=used_names
        )

    except Exception as error:
        flash(str(error))
        return redirect(url_for("index"))

    character = Character(
        user_id=current_user.id,
        source_prompt=character_data["source_prompt"],
        name=character_data["name"],
        character_class=character_data["character_class"],
        race=character_data["race"],
        strength=character_data["strength"],
        intelligence=character_data["intelligence"],
        agility=character_data["agility"],
        magic=character_data["magic"],
        description=character_data["description"],
        goal=character_data["goal"],
        abilities=character_data["abilities"],
        image_prompt=character_data.get("image_prompt", "")
    )

    db.session.add(character)
    db.session.commit()

    return redirect(url_for("view_character", character_id=character.id))


@app.route("/characters")
@login_required
def characters():
    all_characters = Character.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Character.created_at.desc()
    ).all()

    return render_template("characters.html", characters=all_characters)


@app.route("/characters/<int:character_id>")
@login_required
def view_character(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "result.html",
        character=character,
        character_image=get_character_image_filename(character),
        image_version=get_image_version(character)
    )


@app.route("/characters/<int:character_id>/regenerate-image", methods=["POST"])
@login_required
def regenerate_character_image(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    generate_character_image(character)

    return redirect(url_for("view_character", character_id=character.id))


@app.route("/characters/<int:character_id>/delete", methods=["POST"])
@login_required
def delete_character(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    image_path = get_character_image_path(character)

    if image_path.exists():
        image_path.unlink()

    db.session.delete(character)
    db.session.commit()

    return redirect(url_for("characters"))


@app.route("/characters/<int:character_id>/edit", methods=["GET", "POST"])
@login_required
def edit_character(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        character.name = request.form.get("name", "").strip()
        character.character_class = request.form.get("character_class", "").strip()
        character.race = request.form.get("race", "").strip()

        character.strength = int(request.form.get("strength"))
        character.intelligence = int(request.form.get("intelligence"))
        character.agility = int(request.form.get("agility"))
        character.magic = int(request.form.get("magic"))

        character.description = request.form.get("description", "").strip()
        character.goal = request.form.get("goal", "").strip()
        character.abilities = request.form.get("abilities", "").strip()

        db.session.commit()

        return redirect(url_for("view_character", character_id=character.id))

    return render_template("edit.html", character=character)


# ========== НОВЫЙ МАРШРУТ ДЛЯ AI-РЕДАКТИРОВАНИЯ ==========

@app.route("/characters/<int:character_id>/ai_edit", methods=["POST"])
@login_required
def ai_edit_character(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()
    
    user_instruction = request.form.get("instruction", "").strip()
    if not user_instruction:
        flash("Напишите, что именно изменить в персонаже.")
        return redirect(url_for("view_character", character_id=character.id))
    
    # Подготавливаем словарь с текущими данными
    current_data = {
        "name": character.name,
        "character_class": character.character_class,
        "race": character.race,
        "strength": character.strength,
        "intelligence": character.intelligence,
        "agility": character.agility,
        "magic": character.magic,
        "description": character.description,
        "goal": character.goal,
        "abilities": character.abilities,
        "image_prompt": character.image_prompt or "",
    }
    
    try:
        updated_data = edit_character_with_ai(current_data, user_instruction)
    except Exception as e:
        flash(f"Ошибка AI: {e}")
        return redirect(url_for("view_character", character_id=character.id))
    
    # Обновляем поля, которые изменились
    for key, value in updated_data.items():
        setattr(character, key, value)
    
    db.session.commit()
    
    flash("Персонаж успешно изменён с помощью AI!")
    return redirect(url_for("view_character", character_id=character.id))


@app.route("/characters/<int:character_id>/export/txt")
@login_required
def export_txt(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    file_path = EXPORT_DIR / f"character_{character.id}.txt"

    file_path.write_text(
        character_to_text(character),
        encoding="utf-8"
    )

    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{character.name}.txt"
    )


@app.route("/characters/<int:character_id>/export/pdf")
@login_required
def export_pdf(character_id):
    character = Character.query.filter_by(
        id=character_id,
        user_id=current_user.id
    ).first_or_404()

    font_path = get_pdf_font_path()

    if font_path is None:
        flash("Не найден шрифт для создания PDF.")
        return redirect(url_for("view_character", character_id=character.id))

    file_path = EXPORT_DIR / f"character_{character.id}.pdf"
    image_path = get_character_image_path(character)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_font("ArialCyr", "", str(font_path))
    pdf.set_font("ArialCyr", size=14)

    if image_path.exists():
        pdf.image(str(image_path), x=58, y=12, w=95)
        pdf.ln(130)

    text = character_to_text(character)

    pdf.multi_cell(0, 8, text)
    pdf.output(str(file_path))

    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{character.name}.pdf"
    )


if __name__ == "__main__":
    create_placeholder_image()

    with app.app_context():
        db.create_all()
        ensure_database_schema()

    app.run(debug=True, threaded=True)