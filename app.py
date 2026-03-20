"""
ALUPS-OPE - Generateur de conventions DPS (version web)
Portage du logiciel Python (dps_generator6.py) vers Flask.
"""

import os
import re
import json
import math
import base64
import shutil
import subprocess
import tempfile
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, flash, session, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(BASE_DIR, "alups_ope.db")

TPL_CONVENTION_2 = "convention_2.docx"
TPL_CONVENTION_MULTI = "convention_4.docx"
TPL_DEVIS_UPS = "devisUPS.xlsx"
TPL_DEVIS_NON_UPS = "devisNonUPS.xlsx"

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_template_path(filename):
    path = os.path.join(BASE_DIR, filename)
    return path if os.path.exists(path) else None


# ═══════════════════════════════════════════════════════════════════════
# GRILLES TARIFAIRES
# ═══════════════════════════════════════════════════════════════════════

TARIFS_PARIS_SACLAY = {
    2:  {"fixe": 200, 4: 200, 5: 300, 6: 300, 7: 300, 8: 320, 9: 350, 10: 380, 11: 410, 12: 440, 13: 470, 14: 500, 15: 530, 16: 560, 17: 590, 18: 620, 19: 650, 20: 680},
    4:  {"fixe": 300, 4: 300, 5: 400, 6: 430, 7: 495, 8: 560, 9: 625, 10: 690, 11: 755, 12: 820, 13: 885, 14: 950, 15: 1015, 16: 1080, 17: 1145, 18: 1210, 19: 1275, 20: 1340},
    6:  {"fixe": 400, 4: 400, 5: 500, 6: 590, 7: 685, 8: 780, 9: 875, 10: 970, 11: 1065, 12: 1160, 13: 1255, 14: 1350, 15: 1445, 16: 1540, 17: 1635, 18: 1730, 19: 1825, 20: 1920},
    8:  {"fixe": 500, 4: 500, 5: 630, 6: 760, 7: 890, 8: 1020, 9: 1150, 10: 1280, 11: 1410, 12: 1540, 13: 1625, 14: 1800, 15: 1875, 16: 2000, 17: 2125, 18: 2250, 19: 2375, 20: 2500},
    10: {"fixe": 600, 4: 600, 5: 760, 6: 920, 7: 1080, 8: 1240, 9: 1400, 10: 1560, 11: 1720, 12: 1880, 13: 1995, 14: 2200, 15: 2305, 16: 2460, 17: 2615, 18: 2770, 19: 2925, 20: 3080},
    12: {"fixe": 700, 4: 700, 5: 885, 6: 1070, 7: 1255, 8: 1440, 9: 1625, 10: 1810, 11: 1995, 12: 2180, 13: 2365, 14: 2550, 15: 2735, 16: 2920, 17: 3105, 18: 3290, 19: 3475, 20: 3660},
    20: {"fixe": 1100, 4: 1100, 5: 1405, 6: 1710, 7: 2015, 8: 2320, 9: 2625, 10: 2930, 11: 3235, 12: 3540, 13: 3845, 14: 4150, 15: 4455, 16: 4760, 17: 5065, 18: 5370, 19: 5675, 20: 5980},
    22: {"fixe": 1200, 4: 1200, 5: 1535, 6: 1870, 7: 2205, 8: 2540, 9: 2875, 10: 3210, 11: 3545, 12: 3880, 13: 4215, 14: 4550, 15: 4885, 16: 5220, 17: 5555, 18: 5890, 19: 6225, 20: 6560},
    24: {"fixe": 1300, 4: 1300, 5: 1665, 6: 2030, 7: 2395, 8: 2760, 9: 3125, 10: 3490, 11: 3855, 12: 4220, 13: 4585, 14: 4950, 15: 5315, 16: 5680, 17: 6045, 18: 6410, 19: 6775, 20: 7140},
    26: {"fixe": 1400, 4: 1400, 5: 1795, 6: 2190, 7: 2585, 8: 2980, 9: 3375, 10: 3770, 11: 4165, 12: 4560, 13: 4955, 14: 5350, 15: 5745, 16: 6140, 17: 6535, 18: 6930, 19: 7325, 20: 7720},
    28: {"fixe": 1500, 4: 1500, 5: 1925, 6: 2350, 7: 2775, 8: 3200, 9: 3625, 10: 4050, 11: 4475, 12: 4900, 13: 5325, 14: 5750, 15: 6175, 16: 6600, 17: 7025, 18: 7450, 19: 7875, 20: 8300},
    30: {"fixe": 1600, 4: 1600, 5: 2055, 6: 2510, 7: 2965, 8: 3420, 9: 3875, 10: 4330, 11: 4785, 12: 5240, 13: 5695, 14: 6150, 15: 6605, 16: 7060, 17: 7515, 18: 7970, 19: 8425, 20: 8880},
    32: {"fixe": 1700, 4: 1700, 5: 2185, 6: 2670, 7: 3155, 8: 3640, 9: 4125, 10: 4610, 11: 5095, 12: 5580, 13: 6065, 14: 6550, 15: 7035, 16: 7520, 17: 8005, 18: 8490, 19: 8975, 20: 9460},
    34: {"fixe": 1800, 4: 1800, 5: 2315, 6: 2830, 7: 3345, 8: 3860, 9: 4375, 10: 4890, 11: 5405, 12: 5920, 13: 6435, 14: 6950, 15: 7465, 16: 7980, 17: 8495, 18: 9010, 19: 9525, 20: 10040},
    36: {"fixe": 1900, 4: 1900, 5: 2445, 6: 2990, 7: 3535, 8: 4080, 9: 4625, 10: 5170, 11: 5715, 12: 6260, 13: 6805, 14: 7350, 15: 7895, 16: 8440, 17: 8985, 18: 9530, 19: 10075, 20: 10620},
    38: {"fixe": 2000, 4: 2000, 5: 2575, 6: 3150, 7: 3725, 8: 4300, 9: 4875, 10: 5450, 11: 6025, 12: 6600, 13: 7175, 14: 7750, 15: 8325, 16: 8900, 17: 9475, 18: 10050, 19: 10625, 20: 11200},
    40: {"fixe": 2100, 4: 2100, 5: 2705, 6: 3310, 7: 3915, 8: 4520, 9: 5125, 10: 5730, 11: 6335, 12: 6940, 13: 7545, 14: 8150, 15: 8755, 16: 9360, 17: 9965, 18: 10570, 19: 11175, 20: 11780},
    42: {"fixe": 2200, 4: 2200, 5: 2835, 6: 3470, 7: 4105, 8: 4740, 9: 5375, 10: 6010, 11: 6645, 12: 7280, 13: 7915, 14: 8550, 15: 9185, 16: 9820, 17: 10455, 18: 11090, 19: 11725, 20: 12360},
    44: {"fixe": 2300, 4: 2300, 5: 2965, 6: 3630, 7: 4295, 8: 4960, 9: 5625, 10: 6290, 11: 6955, 12: 7620, 13: 8285, 14: 8950, 15: 9615, 16: 10280, 17: 10945, 18: 11610, 19: 12275, 20: 12940},
    46: {"fixe": 2400, 4: 2400, 5: 3095, 6: 3790, 7: 4485, 8: 5180, 9: 5875, 10: 6570, 11: 7265, 12: 7960, 13: 8655, 14: 9350, 15: 10045, 16: 10740, 17: 11435, 18: 12130, 19: 12825, 20: 13520},
    48: {"fixe": 2500, 4: 2500, 5: 3225, 6: 3950, 7: 4675, 8: 5400, 9: 6125, 10: 6850, 11: 7575, 12: 8300, 13: 9025, 14: 9750, 15: 10475, 16: 11200, 17: 11925, 18: 12650, 19: 13375, 20: 14100},
    50: {"fixe": 2600, 4: 2600, 5: 3355, 6: 4110, 7: 4865, 8: 5620, 9: 6375, 10: 7130, 11: 7885, 12: 8640, 13: 9395, 14: 10150, 15: 10905, 16: 11660, 17: 12415, 18: 13170, 19: 13925, 20: 14680},
}

TARIFS_NON_PARIS_SACLAY = {
    2:  {"fixe": 200, 4: 200, 5: 320, 6: 320, 7: 320, 8: 360, 9: 400, 10: 450, 11: 480, 12: 520, 13: 560, 14: 600, 15: 640, 16: 680},
    4:  {"fixe": 320, 4: 320, 5: 590, 6: 590, 7: 590, 8: 630, 9: 710, 10: 886, 11: 900, 12: 920, 13: 960, 14: 1040, 15: 1080, 16: 1120},
    6:  {"fixe": 480, 4: 480, 5: 885, 6: 885, 7: 885, 8: 945, 9: 1065, 10: 1329, 11: 1350, 12: 1380, 13: 1440, 14: 1560, 15: 1620, 16: 1680},
    8:  {"fixe": 640, 4: 640, 5: 1180, 6: 1180, 7: 1180, 8: 1260, 9: 1420, 10: 1772, 11: 1800, 12: 1840, 13: 1920, 14: 2080, 15: 2160, 16: 2240},
    10: {"fixe": 800, 4: 800, 5: 1475, 6: 1475, 7: 1475, 8: 1575, 9: 1775, 10: 2215, 11: 2250, 12: 2300, 13: 2400, 14: 2600, 15: 2700, 16: 2800},
    12: {"fixe": 960, 4: 960, 5: 1770, 6: 1770, 7: 1770, 8: 1890, 9: 2130, 10: 2658, 11: 2700, 12: 2760, 13: 2880, 14: 3120, 15: 3240, 16: 3360},
}


# ═══════════════════════════════════════════════════════════════════════
# UTILITAIRES (identiques au Python original)
# ═══════════════════════════════════════════════════════════════════════

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
           "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]

FIELD_CONSTRAINTS = {
    "org": "Nom complet de l'organisme demandeur (raison sociale, association, mairie...)",
    "rep": "Nom et prenom du representant ou interlocuteur de l'organisme demandeur",
    "qlt": "Qualite/Fonction du representant (ex: President, Directeur, Maire...)",
    "rep_legal": "Nom et prenom du representant legal de l'organisme (champ 'representant legal' du formulaire)",
    "qlt_legal": "Qualite/Fonction du representant legal (champ associe au representant legal)",
    "adr": "Adresse postale complete de l'organisme ou de la manifestation",
    "tel": "Numero de telephone (format 0X XX XX XX XX)",
    "mel": "Adresse email de contact",
    "int": "Intitule/nom de la manifestation ou de l'evenement",
    "dte": "Date de la manifestation au format JJ/MM/AAAA",
    "hde": "Heure de debut au format HH:MM (ex: 08:00)",
    "hfi": "Heure de fin au format HH:MM (ex: 18:00)",
    "loc": "Lieu/adresse precise de la manifestation",
    "effectif_acteurs": "Nombre d'acteurs/participants (nombre entier ou null)",
    "effectif_public": "Nombre de public attendu (nombre entier ou null)",
    "contact_nom": "Nom de la personne de contact sur place le jour de l'evenement",
    "contact_telephone": "Telephone portable du contact sur place",
}

EXTRACTION_JSON_STRUCTURE = {
    "org": "", "rep": "", "qlt": "",
    "rep_legal": "", "qlt_legal": "",
    "adr": "", "tel": "", "mel": "",
    "int": "", "dte": "", "hde": "", "hfi": "", "loc": "",
    "effectif_acteurs": None, "effectif_public": None,
    "contact_nom": "", "contact_telephone": "",
}


def format_date_full(d):
    return f"{JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month - 1]} {d.year}"


def format_date_short(d):
    return f"{d.day:02d} {MOIS_FR[d.month - 1]} {d.year}"


def normalize_heure(s):
    return s.strip().replace('h', ':').replace('H', ':')


def calc_duration(hde, hfi):
    try:
        h1 = datetime.strptime(normalize_heure(hde), "%H:%M")
        h2 = datetime.strptime(normalize_heure(hfi), "%H:%M")
        delta = (h2 - h1).total_seconds() / 3600
        if delta <= 0:
            delta += 24
        return math.ceil(delta)
    except ValueError:
        return 0


def calc_smx(d_edition, d_poste):
    delta = (d_poste - d_edition).days
    return d_edition + timedelta(days=math.floor(delta * 3 / 4))


def get_price(nb_sec, duree_h, is_ps):
    grille = TARIFS_PARIS_SACLAY if is_ps else TARIFS_NON_PARIS_SACLAY
    if nb_sec not in grille:
        return 0.0
    tarifs = grille[nb_sec]
    if duree_h <= 4:
        return float(tarifs["fixe"])
    if duree_h in tarifs:
        return float(tarifs[duree_h])
    max_h = max(k for k in tarifs if isinstance(k, int))
    return float(tarifs[max_h]) if duree_h > max_h else 0.0


def fmt_price(amount):
    whole = int(amount)
    cents = int(round((amount - whole) * 100))
    s = f"{whole:,}".replace(",", " ")
    return f"{s},{cents:02d}"


# ═══════════════════════════════════════════════════════════════════════
# CONVERSION .DOC (Linux - LibreOffice)
# ═══════════════════════════════════════════════════════════════════════

def find_libreoffice():
    return shutil.which("libreoffice") or shutil.which("soffice")


def convert_doc(doc_path, output_format):
    out_dir = tempfile.mkdtemp(prefix="dps_")
    base_name = os.path.splitext(os.path.basename(doc_path))[0]
    ext = ".docx" if output_format == "docx" else ".pdf"
    out_path = os.path.join(out_dir, base_name + ext)

    lo = find_libreoffice()
    if lo:
        result = subprocess.run(
            [lo, "--headless", "--convert-to", output_format, "--outdir", out_dir, doc_path],
            capture_output=True, text=True, timeout=60
        )
        if os.path.exists(out_path):
            return out_path
        raise RuntimeError(f"Echec de conversion LibreOffice : {result.stderr.strip()}")

    raise RuntimeError("LibreOffice non installe sur le serveur.")


# ═══════════════════════════════════════════════════════════════════════
# EXTRACTION AUTOMATIQUE (identique au Python original)
# ═══════════════════════════════════════════════════════════════════════

def pdf_to_images_b64(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    imgs = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
        b64 = base64.standard_b64encode(pix.tobytes("png")).decode()
        imgs.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64}
        })
    doc.close()
    return imgs


def call_claude(messages, max_tokens=4096):
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    resp = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=messages)
    text = resp.content[0].text.strip()
    text = re.sub(r"^```json?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text


def extract_from_pdf(pdf_path):
    images = pdf_to_images_b64(pdf_path)

    prompt = f"""Tu es un assistant specialise dans l'extraction de donnees depuis des formulaires
de Demande de Dispositif Previsionnel de Secours (DPS).

ATTENTION : Le document contient des en-tetes et pieds de page avec le logo, le nom,
l'adresse, le telephone et l'email de l'association de secourisme (Croix Blanche, SFCB, etc.).
IGNORE TOTALEMENT ces informations d'en-tete/pied de page.
Les donnees a extraire concernent UNIQUEMENT le DEMANDEUR (l'organisme qui demande le DPS),
PAS l'association de secourisme qui traite la demande.

Analyse le document et extrais les informations dans ce JSON :
{json.dumps(EXTRACTION_JSON_STRUCTURE, indent=2, ensure_ascii=False)}

Contraintes par champ :
{json.dumps(FIELD_CONSTRAINTS, indent=2, ensure_ascii=False)}

- rep = le representant ou interlocuteur mentionne dans le formulaire (pas forcement le representant legal)
- rep_legal = la personne identifiee comme "representant legal" dans le formulaire, meme si c'est la meme personne que rep
- qlt_legal = la fonction/qualite associee au representant legal
- Si le formulaire a un champ "representant legal", remplis rep_legal avec cette valeur
- Remplis uniquement les champs trouves dans le document.
- Laisse "" ou null si l'information n'est pas trouvee.
- NE PAS utiliser les coordonnees de l'en-tete/pied de page du document.
- Reponds UNIQUEMENT avec le JSON, sans backticks ni texte autour."""

    content = images + [{"type": "text", "text": prompt}]
    text = call_claude([{"role": "user", "content": content}])
    return json.loads(text)


def resolve_missing_fields(current_data, pdf_path):
    missing = {k: v for k, v in current_data.items()
               if v is None or (isinstance(v, str) and v.strip() == "")}

    missing.pop("rep_legal", None)
    missing.pop("qlt_legal", None)

    if not missing:
        return current_data

    missing_constraints = {k: FIELD_CONSTRAINTS.get(k, "") for k in missing}
    images = pdf_to_images_b64(pdf_path)

    prompt = f"""Le document a deja ete analyse et certaines informations n'ont pas pu etre extraites.

ATTENTION : IGNORE les en-tetes et pieds de page du document (logo, nom, adresse, telephone,
email de l'association de secourisme Croix Blanche / SFCB). Ces informations NE SONT PAS
celles du demandeur. Extrais UNIQUEMENT les donnees du DEMANDEUR de la manifestation.

Donnees deja extraites :
{json.dumps(current_data, indent=2, ensure_ascii=False)}

Champs MANQUANTS a completer :
{json.dumps(missing_constraints, indent=2, ensure_ascii=False)}

Analyse a nouveau le document en te concentrant UNIQUEMENT sur ces champs manquants.
Si tu ne trouves toujours pas un champ, ne l'inclus pas dans ta reponse.
Reponds UNIQUEMENT avec le JSON, sans backticks."""

    content = images + [{"type": "text", "text": prompt}]

    try:
        text = call_claude([{"role": "user", "content": content}])
        resolved = json.loads(text)
        for k, v in resolved.items():
            if v is not None and (not isinstance(v, str) or v.strip() != ""):
                current_data[k] = v
    except Exception:
        pass

    return current_data


# ═══════════════════════════════════════════════════════════════════════
# REMPLISSAGE TEMPLATES (identique au Python original)
# ═══════════════════════════════════════════════════════════════════════

def fill_docx(tpl_path, out_path, ctx):
    from docxtpl import DocxTemplate
    doc = DocxTemplate(tpl_path)
    doc.render(ctx)
    doc.save(out_path)


def fill_xlsx(tpl_path, out_path, ctx):
    import zipfile
    # Manipulation directe du ZIP pour preserver les images
    with zipfile.ZipFile(tpl_path, "r") as zin:
        items = {}
        for info in zin.infolist():
            items[info.filename] = (zin.read(info.filename), info)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for filename, (data, info) in items.items():
            if filename == "xl/sharedStrings.xml" or filename.startswith("xl/worksheets/"):
                text = data.decode("utf-8")
                for key, val in ctx.items():
                    safe = str(val) if val is not None else ""
                    safe = safe.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    for pat in [f"{{{{{key}}}}}", f"{{{{ {key} }}}}"]:
                        text = text.replace(pat, safe)
                zout.writestr(info, text.encode("utf-8"))
            else:
                zout.writestr(info, data)


# ═══════════════════════════════════════════════════════════════════════
# BASE DE DONNEES
# ═══════════════════════════════════════════════════════════════════════

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_root INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS postes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL DEFAULT '',
            donnees TEXT NOT NULL DEFAULT '{}',
            statut TEXT NOT NULL DEFAULT 'brouillon',
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fichiers_generes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poste_id INTEGER REFERENCES postes(id) ON DELETE CASCADE,
            nom_fichier TEXT NOT NULL,
            chemin TEXT NOT NULL,
            type_fichier TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()
    db.close()


def has_users():
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


# ═══════════════════════════════════════════════════════════════════════
# FLASK APP
# ═══════════════════════════════════════════════════════════════════════

app = Flask(__name__)

SECRET_KEY_FILE = os.path.join(BASE_DIR, ".secret_key")
if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "rb") as f:
        app.secret_key = f.read()
else:
    app.secret_key = os.urandom(24)
    with open(SECRET_KEY_FILE, "wb") as f:
        f.write(app.secret_key)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


# ── Prefix middleware pour deploiement sous /ALUPS-OPE/ ───────────────

class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix=""):
        self.app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        # Si nginx a deja strippe le prefixe, on le remet dans SCRIPT_NAME
        environ["SCRIPT_NAME"] = self.prefix
        path = environ.get("PATH_INFO", "")
        # Si le prefixe est encore dans PATH_INFO, le retirer
        if path.startswith(self.prefix):
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
        return self.app(environ, start_response)


PREFIX = os.environ.get("APP_PREFIX", "/ALUPS-OPE")
if PREFIX:
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=PREFIX)

app.teardown_appcontext(close_db)


# ── Auth helpers ──────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("connexion"))
        return f(*args, **kwargs)
    return decorated


def root_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("connexion"))
        if not session.get("is_root"):
            flash("Acces reserve a l'administrateur.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def tarifs_to_json(grille):
    """Convertit les cles int en string pour la serialisation JSON."""
    return {
        str(nb_sec): {str(k): v for k, v in tarifs.items()}
        for nb_sec, tarifs in grille.items()
    }


TARIFS_PS_JSON = tarifs_to_json(TARIFS_PARIS_SACLAY)
TARIFS_NPS_JSON = tarifs_to_json(TARIFS_NON_PARIS_SACLAY)


def get_tpl_status():
    status = {}
    for name in [TPL_CONVENTION_2, TPL_CONVENTION_MULTI, TPL_DEVIS_UPS, TPL_DEVIS_NON_UPS]:
        status[name] = get_template_path(name) is not None
    return status


# ═══════════════════════════════════════════════════════════════════════
# ROUTES - AUTH
# ═══════════════════════════════════════════════════════════════════════

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if has_users():
        return redirect(url_for("connexion"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        password2 = request.form.get("password2", "").strip()

        if not username or not password:
            flash("Identifiant et mot de passe requis.", "danger")
            return render_template("setup.html")
        if password != password2:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return render_template("setup.html")
        if len(password) < 4:
            flash("Le mot de passe doit faire au moins 4 caracteres.", "danger")
            return render_template("setup.html")

        db = get_db()
        db.execute(
            "INSERT INTO users (username, password_hash, is_root) VALUES (?, ?, 1)",
            (username, generate_password_hash(password))
        )
        db.commit()

        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["is_root"] = True
        flash(f"Compte ROOT \"{username}\" cree avec succes.", "success")
        return redirect(url_for("index"))

    return render_template("setup.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if not has_users():
        return redirect(url_for("setup"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_root"] = bool(user["is_root"])
            return redirect(url_for("index"))

        flash("Identifiant ou mot de passe incorrect.", "danger")

    return render_template("connexion.html")


@app.route("/mot-de-passe", methods=["GET", "POST"])
@login_required
def mot_de_passe():
    if request.method == "POST":
        ancien = request.form.get("ancien", "")
        nouveau = request.form.get("nouveau", "")
        nouveau2 = request.form.get("nouveau2", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

        if not check_password_hash(user["password_hash"], ancien):
            flash("Ancien mot de passe incorrect.", "danger")
            return render_template("mot_de_passe.html")
        if not nouveau or len(nouveau) < 4:
            flash("Le nouveau mot de passe doit faire au moins 4 caracteres.", "danger")
            return render_template("mot_de_passe.html")
        if nouveau != nouveau2:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return render_template("mot_de_passe.html")

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(nouveau), session["user_id"])
        )
        db.commit()
        flash("Mot de passe modifie avec succes.", "success")
        return redirect(url_for("index"))

    return render_template("mot_de_passe.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


# ═══════════════════════════════════════════════════════════════════════
# ROUTES - HISTORIQUE
# ═══════════════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    db = get_db()
    rows = db.execute("""
        SELECT p.*, u.username as auteur,
            (SELECT COUNT(*) FROM fichiers_generes fg WHERE fg.poste_id = p.id) as nb_fichiers
        FROM postes p
        LEFT JOIN users u ON p.created_by = u.id
        ORDER BY p.updated_at DESC
    """).fetchall()

    postes = []
    for r in rows:
        p = dict(r)
        try:
            d = json.loads(p.get("donnees", "{}"))
            p["nps"] = d.get("nps", "")
        except (json.JSONDecodeError, TypeError):
            p["nps"] = ""
        postes.append(p)

    return render_template("historique.html", postes=postes, tpl_status=get_tpl_status())


# ═══════════════════════════════════════════════════════════════════════
# ROUTES - EDITEUR
# ═══════════════════════════════════════════════════════════════════════

@app.route("/nouveau")
@login_required
def nouveau():
    nb_sec_values_ps = sorted(TARIFS_PARIS_SACLAY.keys())
    nb_sec_values_nps = sorted(TARIFS_NON_PARIS_SACLAY.keys())
    return render_template(
        "editeur.html",
        poste=None,
        tpl_status=get_tpl_status(),
        nb_sec_values_ps=nb_sec_values_ps,
        nb_sec_values_nps=nb_sec_values_nps,
        tarifs_ps=TARIFS_PS_JSON,
        tarifs_nps=TARIFS_NPS_JSON,
    )


@app.route("/editer/<int:poste_id>")
@login_required
def editer(poste_id):
    db = get_db()
    poste = db.execute("SELECT * FROM postes WHERE id = ?", (poste_id,)).fetchone()
    if not poste:
        flash("Poste introuvable.", "danger")
        return redirect(url_for("index"))

    fichiers_raw = db.execute(
        "SELECT * FROM fichiers_generes WHERE poste_id = ? ORDER BY created_at DESC",
        (poste_id,)
    ).fetchall()

    fichiers = []
    for f in fichiers_raw:
        rel = os.path.relpath(f["chemin"], OUTPUT_DIR)
        fichiers.append({
            "nom_fichier": f["nom_fichier"],
            "type_fichier": f["type_fichier"],
            "url": url_for("telecharger", filename=rel),
        })

    nb_sec_values_ps = sorted(TARIFS_PARIS_SACLAY.keys())
    nb_sec_values_nps = sorted(TARIFS_NON_PARIS_SACLAY.keys())
    return render_template(
        "editeur.html",
        poste=poste,
        fichiers=fichiers,
        tpl_status=get_tpl_status(),
        nb_sec_values_ps=nb_sec_values_ps,
        nb_sec_values_nps=nb_sec_values_nps,
        tarifs_ps=TARIFS_PS_JSON,
        tarifs_nps=TARIFS_NPS_JSON,
    )


# ═══════════════════════════════════════════════════════════════════════
# ROUTES - ADMIN
# ═══════════════════════════════════════════════════════════════════════

@app.route("/admin")
@root_required
def admin():
    db = get_db()
    users = db.execute("SELECT id, username, is_root, created_at FROM users ORDER BY id").fetchall()
    return render_template("admin.html", tpl_status=get_tpl_status(), users=users)


@app.route("/admin/upload-template", methods=["POST"])
@root_required
def admin_upload_template():
    tpl_name = request.form.get("template_name")
    valid = [TPL_CONVENTION_2, TPL_CONVENTION_MULTI, TPL_DEVIS_UPS, TPL_DEVIS_NON_UPS]
    if tpl_name not in valid:
        flash("Nom de template invalide.", "danger")
        return redirect(url_for("admin"))

    if "fichier" not in request.files or not request.files["fichier"].filename:
        flash("Aucun fichier selectionne.", "danger")
        return redirect(url_for("admin"))

    fichier = request.files["fichier"]
    dest = os.path.join(BASE_DIR, tpl_name)
    fichier.save(dest)
    flash(f"Template \"{tpl_name}\" mis a jour.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/download-template/<filename>")
@root_required
def admin_download_template(filename):
    valid = [TPL_CONVENTION_2, TPL_CONVENTION_MULTI, TPL_DEVIS_UPS, TPL_DEVIS_NON_UPS]
    if filename not in valid:
        flash("Fichier invalide.", "danger")
        return redirect(url_for("admin"))
    path = get_template_path(filename)
    if not path:
        flash("Fichier introuvable.", "danger")
        return redirect(url_for("admin"))
    return send_file(path, as_attachment=True)


@app.route("/admin/creer-utilisateur", methods=["POST"])
@root_required
def admin_creer_utilisateur():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Identifiant et mot de passe requis.", "danger")
        return redirect(url_for("admin"))
    if len(password) < 4:
        flash("Le mot de passe doit faire au moins 4 caracteres.", "danger")
        return redirect(url_for("admin"))

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        flash(f"L'utilisateur \"{username}\" existe deja.", "danger")
        return redirect(url_for("admin"))

    db.execute(
        "INSERT INTO users (username, password_hash, is_root) VALUES (?, ?, 0)",
        (username, generate_password_hash(password))
    )
    db.commit()
    flash(f"Utilisateur \"{username}\" cree.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/supprimer-utilisateur/<int:user_id>", methods=["POST"])
@root_required
def admin_supprimer_utilisateur(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("admin"))
    if user["is_root"]:
        flash("Impossible de supprimer le compte ROOT.", "danger")
        return redirect(url_for("admin"))

    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash(f"Utilisateur \"{user['username']}\" supprime.", "success")
    return redirect(url_for("admin"))


# ═══════════════════════════════════════════════════════════════════════
# API - SAUVEGARDE
# ═══════════════════════════════════════════════════════════════════════

@app.route("/api/sauvegarder", methods=["POST"])
@login_required
def api_sauvegarder():
    data = request.get_json()
    poste_id = data.get("id")
    donnees = data.get("donnees", {})
    nom = donnees.get("int", "") or donnees.get("nps", "") or "Sans nom"

    db = get_db()
    if poste_id:
        db.execute(
            "UPDATE postes SET nom=?, donnees=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (nom, json.dumps(donnees), poste_id)
        )
    else:
        cursor = db.execute(
            "INSERT INTO postes (nom, donnees, created_by) VALUES (?, ?, ?)",
            (nom, json.dumps(donnees), session["user_id"])
        )
        poste_id = cursor.lastrowid
    db.commit()

    return jsonify({"id": poste_id, "success": True})


@app.route("/api/supprimer/<int:poste_id>", methods=["POST"])
@login_required
def api_supprimer(poste_id):
    db = get_db()

    # Supprimer les fichiers generes du disque
    fichiers = db.execute(
        "SELECT chemin FROM fichiers_generes WHERE poste_id = ?", (poste_id,)
    ).fetchall()
    for f in fichiers:
        try:
            if os.path.exists(f["chemin"]):
                os.unlink(f["chemin"])
        except OSError:
            pass

    db.execute("DELETE FROM postes WHERE id = ?", (poste_id,))
    db.commit()
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════════
# API - EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

@app.route("/api/extraire", methods=["POST"])
@login_required
def api_extraire():
    if "fichier" not in request.files:
        return jsonify({"error": "Aucun fichier envoye."}), 400

    fichier = request.files["fichier"]
    if not fichier.filename:
        return jsonify({"error": "Aucun fichier selectionne."}), 400

    ext = os.path.splitext(fichier.filename)[1].lower()
    if ext.lstrip(".") not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Format non supporte. Utilisez PDF, DOCX ou DOC."}), 400

    safe_name = secure_filename(fichier.filename)
    upload_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}")
    fichier.save(upload_path)

    pdf_path = None
    try:
        if ext in (".doc", ".docx"):
            pdf_path = convert_doc(upload_path, "pdf")
        else:
            pdf_path = upload_path

        data = extract_from_pdf(pdf_path)

        missing = [k for k, v in data.items()
                   if k not in ("rep_legal", "qlt_legal")
                   and (v is None or (isinstance(v, str) and v.strip() == ""))]
        if missing:
            data = resolve_missing_fields(data, pdf_path)

        still_missing = [k for k, v in data.items()
                         if k not in ("rep_legal", "qlt_legal")
                         and (v is None or (isinstance(v, str) and v.strip() == ""))]

        return jsonify({
            "data": data,
            "success": True,
            "missing": still_missing,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if upload_path and os.path.exists(upload_path):
                os.unlink(upload_path)
            if pdf_path and pdf_path != upload_path and os.path.exists(pdf_path):
                os.unlink(pdf_path)
                parent = os.path.dirname(pdf_path)
                if parent.startswith(tempfile.gettempdir()):
                    shutil.rmtree(parent, ignore_errors=True)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# API - GENERATION
# ═══════════════════════════════════════════════════════════════════════

@app.route("/api/generer", methods=["POST"])
@login_required
def api_generer():
    data = request.get_json()
    v = data.get("donnees", {})
    poste_id = data.get("poste_id")

    is_ps = v.get("is_ps", False)
    nb_sec = int(v.get("nb_sec", 2))
    sec_type = v.get("sec_type", "Public")

    # Selection automatique des templates
    docx_name = TPL_CONVENTION_2 if nb_sec == 2 else TPL_CONVENTION_MULTI
    xlsx_name = TPL_DEVIS_UPS if is_ps else TPL_DEVIS_NON_UPS

    docx_tpl = get_template_path(docx_name)
    xlsx_tpl = get_template_path(xlsx_name)

    if not docx_tpl:
        return jsonify({"error": f"Fichier modele introuvable : {docx_name}"}), 400
    if not xlsx_tpl:
        return jsonify({"error": f"Fichier modele introuvable : {xlsx_name}"}), 400

    # Calculs (identiques au Python original)
    hde = v.get("hde", "")
    hfi = v.get("hfi", "")
    duree = calc_duration(hde, hfi)
    prix_brut = get_price(nb_sec, duree, is_ps)
    remise = round(prix_brut * 0.25, 2) if is_ps else 0.0
    prix_final = prix_brut - remise

    try:
        d_poste = datetime.strptime(v.get("dte", ""), "%d/%m/%Y").date()
        dte_full = format_date_full(d_poste)
        smx_full = format_date_full(calc_smx(date.today(), d_poste))
    except ValueError:
        dte_full = v.get("dte", "")
        smx_full = ""

    pbc = str(nb_sec) if sec_type == "Public" else "0"
    acc = str(nb_sec) if sec_type == "Acteurs" else "0"

    cnt = v.get("contact_nom", "")
    if v.get("contact_tel"):
        cnt += " - " + v["contact_tel"]

    ncl = v.get("rep_legal", "") or v.get("rep", "")
    fnc = v.get("qlt_legal", "") or v.get("qlt", "")

    ctx = {
        "nps": v.get("nps", ""),
        "org": v.get("org", ""),
        "rep": v.get("rep", ""),
        "qlt": v.get("qlt", ""),
        "adr": v.get("adr", ""),
        "tel": v.get("tel", ""),
        "mel": v.get("mel", ""),
        "int": v.get("int", ""),
        "dte": dte_full,
        "hor": f"{hde} - {hfi}" if hde and hfi else "",
        "hde": hde,
        "hfi": hfi,
        "loc": v.get("loc", ""),
        "los": v.get("loc", ""),
        "pbq": v.get("pbq", ""),
        "cnt": cnt,
        "pbc": pbc,
        "acc": acc,
        "pax": str(nb_sec),
        "rdd": v.get("contact_nom", ""),
        "rdn": v.get("contact_tel", ""),
        "pff": fmt_price(prix_brut),
        "pf2": fmt_price(remise),
        "ptl": fmt_price(prix_final),
        "mnt": fmt_price(prix_brut),
        "det": format_date_short(date.today()),
        "smx": smx_full,
        "dhe": f"{duree}H",
        "dst": v.get("org", ""),
        "qld": v.get("qlt", ""),
        "ndd": v.get("rep", ""),
        "ncl": ncl,
        "fnc": fnc,
    }

    # Dossier de sortie
    nps = v.get("nps", "").strip()
    if not nps:
        nps = re.sub(r'[\\/*?:"<>|]', "_", v.get("int", "DPS"))[:50]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_subdir = os.path.join(OUTPUT_DIR, f"{poste_id or 'tmp'}_{timestamp}")
    os.makedirs(out_subdir, exist_ok=True)

    files_generated = []
    errors = []
    db = get_db()

    # Supprimer les anciens fichiers generes pour ce poste
    if poste_id:
        old_files = db.execute(
            "SELECT chemin FROM fichiers_generes WHERE poste_id = ?", (poste_id,)
        ).fetchall()
        for of in old_files:
            try:
                if os.path.exists(of["chemin"]):
                    os.unlink(of["chemin"])
            except OSError:
                pass
        db.execute("DELETE FROM fichiers_generes WHERE poste_id = ?", (poste_id,))

    try:
        docx_out = os.path.join(out_subdir, f"{nps}_Convention.docx")
        fill_docx(docx_tpl, docx_out, ctx)
        files_generated.append({
            "name": f"{nps}_Convention.docx",
            "path": docx_out,
            "type": "convention"
        })
    except Exception as e:
        errors.append(f"Erreur generation convention : {e}")

    try:
        xlsx_out = os.path.join(out_subdir, f"{nps}_Devis.xlsx")
        fill_xlsx(xlsx_tpl, xlsx_out, ctx)
        files_generated.append({
            "name": f"{nps}_Devis.xlsx",
            "path": xlsx_out,
            "type": "devis"
        })
    except Exception as e:
        errors.append(f"Erreur generation devis : {e}")

    # Enregistrer en BDD
    if poste_id:
        for fg in files_generated:
            db.execute(
                "INSERT INTO fichiers_generes (poste_id, nom_fichier, chemin, type_fichier) VALUES (?, ?, ?, ?)",
                (poste_id, fg["name"], fg["path"], fg["type"])
            )
        db.execute(
            "UPDATE postes SET statut='genere', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (poste_id,)
        )
        db.commit()

    result_files = []
    for fg in files_generated:
        rel = os.path.relpath(fg["path"], OUTPUT_DIR)
        result_files.append({
            "name": fg["name"],
            "url": url_for("telecharger", filename=rel),
            "type": fg["type"],
        })

    return jsonify({
        "success": len(files_generated) > 0,
        "files": result_files,
        "errors": errors,
        "count": len(files_generated),
    })


@app.route("/telecharger/<path:filename>")
@login_required
def telecharger(filename):
    safe = os.path.normpath(filename)
    if ".." in safe:
        return "Acces interdit", 403
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.exists(path):
        return "Fichier introuvable", 404
    return send_file(path, as_attachment=True)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5150)
