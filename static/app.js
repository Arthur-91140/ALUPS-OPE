/* ═══════════════════════════════════════════════════════════════════════
   ALUPS-OPE - Frontend JavaScript
   Recalcul tarifaire, extraction, sauvegarde, generation
   ═══════════════════════════════════════════════════════════════════════ */

// ── Jours / Mois en francais ─────────────────────────────────────────

const JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];
const MOIS_FR = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
                 "juillet", "aout", "septembre", "octobre", "novembre", "decembre"];

// ── Journal ──────────────────────────────────────────────────────────

function log(msg) {
    const box = document.getElementById('log-box');
    if (!box) return;
    const line = document.createElement('div');
    line.textContent = msg;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
}

// ── Utilitaires de calcul (identiques au Python) ─────────────────────

function calcDuration(hde, hfi) {
    try {
        const [h1, m1] = hde.trim().split(':').map(Number);
        const [h2, m2] = hfi.trim().split(':').map(Number);
        if (isNaN(h1) || isNaN(m1) || isNaN(h2) || isNaN(m2)) return 0;
        let delta = (h2 + m2 / 60) - (h1 + m1 / 60);
        if (delta <= 0) delta += 24;
        return Math.ceil(delta);
    } catch (e) {
        return 0;
    }
}

function getPrice(nbSec, dureeH, isPs) {
    const grille = isPs ? TARIFS_PS : TARIFS_NPS;
    const key = String(nbSec);
    if (!(key in grille)) return 0;
    const tarifs = grille[key];
    if (dureeH <= 4) return tarifs['fixe'] || 0;
    const durKey = String(dureeH);
    if (durKey in tarifs) return tarifs[durKey];
    const maxH = Math.max(...Object.keys(tarifs).filter(k => k !== 'fixe').map(Number));
    return dureeH > maxH ? (tarifs[String(maxH)] || 0) : 0;
}

function fmtPrice(amount) {
    const whole = Math.floor(amount);
    const cents = Math.round((amount - whole) * 100);
    const s = whole.toLocaleString('fr-FR');
    return s + ',' + String(cents).padStart(2, '0');
}

function formatDateFull(d) {
    return JOURS_FR[d.getDay() === 0 ? 6 : d.getDay() - 1] + ' ' +
           d.getDate() + ' ' +
           MOIS_FR[d.getMonth()] + ' ' +
           d.getFullYear();
}

function calcSmx(dEdition, dPoste) {
    const delta = Math.floor((dPoste - dEdition) / (1000 * 60 * 60 * 24));
    const smxDays = Math.floor(delta * 3 / 4);
    const result = new Date(dEdition);
    result.setDate(result.getDate() + smxDays);
    return result;
}

function parseDateFR(str) {
    const parts = str.trim().split('/');
    if (parts.length !== 3) return null;
    const d = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10) - 1;
    const y = parseInt(parts[2], 10);
    if (isNaN(d) || isNaN(m) || isNaN(y)) return null;
    return new Date(y, m, d);
}

// ── Gestion de la configuration ──────────────────────────────────────

function isPS() {
    return document.getElementById('ps-oui').checked;
}

function getNbSec() {
    const sel = document.getElementById('nb_sec');
    return parseInt(sel.value, 10) || 2;
}

function getSecType() {
    return document.getElementById('sec-public').checked ? 'Public' : 'Acteurs';
}

function updateNbSecOptions() {
    const sel = document.getElementById('nb_sec');
    const currentVal = sel.value;
    const values = isPS() ? NB_SEC_PS : NB_SEC_NPS;

    sel.innerHTML = '';
    values.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        sel.appendChild(opt);
    });

    // Restaurer la valeur si possible
    if (values.includes(parseInt(currentVal, 10))) {
        sel.value = currentVal;
    } else {
        sel.value = values[0];
    }
}

function onConfigChange() {
    updateNbSecOptions();
    recalculer();
}

// ── Recalcul tarifaire ───────────────────────────────────────────────

function recalculer() {
    const hde = document.getElementById('field-hde').value;
    const hfi = document.getElementById('field-hfi').value;
    const nbSec = getNbSec();
    const ps = isPS();

    const duree = calcDuration(hde, hfi);
    const prixBrut = getPrice(nbSec, duree, ps);
    const remise = ps ? Math.round(prixBrut * 0.25 * 100) / 100 : 0;
    const prixFinal = prixBrut - remise;

    document.getElementById('calc-duree').textContent = duree ? duree + 'H' : '-';
    document.getElementById('calc-brut').textContent = prixBrut ? fmtPrice(prixBrut) + ' EUR' : '-';

    const remiseEl = document.getElementById('calc-remise');
    if (remise) {
        remiseEl.textContent = '-' + fmtPrice(remise) + ' EUR';
        remiseEl.style.color = 'var(--green)';
    } else {
        remiseEl.textContent = 'Aucune';
        remiseEl.style.color = 'var(--g400)';
    }

    const finalEl = document.getElementById('calc-final');
    finalEl.textContent = prixFinal ? fmtPrice(prixFinal) + ' EUR' : '-';

    // Date butoir
    const dte = document.getElementById('field-dte').value;
    const dPoste = parseDateFR(dte);
    const butoirEl = document.getElementById('calc-butoir');
    if (dPoste) {
        const smx = calcSmx(new Date(), dPoste);
        butoirEl.textContent = formatDateFull(smx);
    } else {
        butoirEl.textContent = '-';
    }
}

// ── Upload fichier ───────────────────────────────────────────────────

let uploadedFile = null;

function initFileUpload() {
    const input = document.getElementById('file-input');
    if (!input) return;

    input.addEventListener('change', function () {
        if (this.files.length > 0) {
            uploadedFile = this.files[0];
            document.getElementById('file-upload-text').textContent = uploadedFile.name;
            document.getElementById('btn-extract').disabled = false;
            log('Document charge : ' + uploadedFile.name);
        }
    });
}

// ── Extraction ───────────────────────────────────────────────────────

function extraire() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    if (mode === 'manual') {
        log('Mode manuel selectionne. Remplissez les champs a la main.');
        return;
    }
    if (!uploadedFile) {
        log('Veuillez d\'abord selectionner un document.');
        return;
    }

    const btn = document.getElementById('btn-extract');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Lecture en cours...';

    document.getElementById('extract-status').style.display = 'block';
    document.getElementById('extract-success').style.display = 'none';
    document.getElementById('extract-error').style.display = 'none';

    log('');
    log('Lecture du document en cours...');

    const formData = new FormData();
    formData.append('fichier', uploadedFile);

    fetch(getBaseUrl() + '/api/extraire', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(result => {
        if (result.error) {
            throw new Error(result.error);
        }

        log('Lecture terminee.');
        fillFields(result.data);

        if (result.missing && result.missing.length > 0) {
            log('Information(s) a completer manuellement : ' + result.missing.join(', '));
            const el = document.getElementById('extract-success');
            el.innerHTML = '<i class="bi bi-check-circle"></i> Extraction terminee. ' +
                           result.missing.length + ' champ(s) a completer manuellement.';
            el.style.display = 'flex';
        } else {
            log('Toutes les informations ont ete trouvees.');
            const el = document.getElementById('extract-success');
            el.innerHTML = '<i class="bi bi-check-circle"></i> Extraction terminee avec succes.';
            el.style.display = 'flex';
        }
    })
    .catch(e => {
        log('Erreur lors de la lecture : ' + e.message);
        const el = document.getElementById('extract-error');
        el.innerHTML = '<i class="bi bi-exclamation-circle"></i> ' + e.message;
        el.style.display = 'flex';
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-search"></i> Lire le document';
    });
}

function fillFields(data) {
    const fieldMap = {
        'org': 'org', 'rep': 'rep', 'qlt': 'qlt',
        'adr': 'adr', 'tel': 'tel', 'mel': 'mel',
        'int': 'int', 'dte': 'dte',
        'hde': 'hde', 'hfi': 'hfi', 'loc': 'loc',
        'contact_nom': 'contact_nom', 'contact_tel': 'contact_telephone',
    };

    for (const [fid, dkey] of Object.entries(fieldMap)) {
        const val = data[dkey];
        if (val) {
            const el = document.getElementById('field-' + fid);
            if (el) el.value = String(val);
        }
    }

    // Effectifs
    const effPub = data.effectif_public;
    const effAct = data.effectif_acteurs;
    document.getElementById('eff-public').textContent = effPub || '-';
    document.getElementById('eff-acteurs').textContent = effAct || '-';
    document.getElementById('field-effectif_public').value = effPub || '';
    document.getElementById('field-effectif_acteurs').value = effAct || '';

    // Rep legal (champs caches)
    if (data.rep_legal) document.getElementById('field-rep_legal').value = data.rep_legal;
    if (data.qlt_legal) document.getElementById('field-qlt_legal').value = data.qlt_legal;

    recalculer();
}

// ── Collecte des donnees du formulaire ───────────────────────────────

function collectData() {
    return {
        nps: document.getElementById('field-nps').value.trim(),
        org: document.getElementById('field-org').value.trim(),
        rep: document.getElementById('field-rep').value.trim(),
        qlt: document.getElementById('field-qlt').value.trim(),
        adr: document.getElementById('field-adr').value.trim(),
        tel: document.getElementById('field-tel').value.trim(),
        mel: document.getElementById('field-mel').value.trim(),
        'int': document.getElementById('field-int').value.trim(),
        dte: document.getElementById('field-dte').value.trim(),
        hde: document.getElementById('field-hde').value.trim(),
        hfi: document.getElementById('field-hfi').value.trim(),
        loc: document.getElementById('field-loc').value.trim(),
        contact_nom: document.getElementById('field-contact_nom').value.trim(),
        contact_tel: document.getElementById('field-contact_tel').value.trim(),
        pbq: document.getElementById('field-pbq').value.trim(),
        is_ps: isPS(),
        nb_sec: getNbSec(),
        sec_type: getSecType(),
        effectif_public: document.getElementById('field-effectif_public').value || null,
        effectif_acteurs: document.getElementById('field-effectif_acteurs').value || null,
        rep_legal: document.getElementById('field-rep_legal').value.trim(),
        qlt_legal: document.getElementById('field-qlt_legal').value.trim(),
    };
}

function getBaseUrl() {
    // Detecter le prefixe depuis l'URL actuelle
    const path = window.location.pathname;
    const match = path.match(/^(\/ALUPS-OPE)/);
    return match ? match[1] : '';
}

// ── Sauvegarde ───────────────────────────────────────────────────────

function sauvegarder() {
    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Sauvegarde...';

    const donnees = collectData();

    fetch(getBaseUrl() + '/api/sauvegarder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            id: POSTE_ID,
            donnees: donnees
        })
    })
    .then(r => r.json())
    .then(result => {
        if (result.success) {
            log('Poste sauvegarde (ID: ' + result.id + ')');
            // Rediriger vers la page d'edition si c'etait un nouveau poste
            if (!POSTE_ID) {
                window.location.href = getBaseUrl() + '/editer/' + result.id;
            }
        } else {
            throw new Error('Erreur de sauvegarde');
        }
    })
    .catch(e => {
        log('Erreur : ' + e.message);
        alert('Erreur lors de la sauvegarde : ' + e.message);
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-save"></i> Sauvegarder';
    });
}

// ── Generation ───────────────────────────────────────────────────────

function generer() {
    const btn = document.getElementById('btn-generate');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Generation en cours...';

    const donnees = collectData();
    log('');
    log('Generation des documents...');

    // D'abord sauvegarder si nouveau poste
    const saveFirst = !POSTE_ID
        ? fetch(getBaseUrl() + '/api/sauvegarder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: null, donnees: donnees })
          }).then(r => r.json())
        : Promise.resolve({ id: POSTE_ID, success: true });

    saveFirst
    .then(saveResult => {
        const posteId = saveResult.id || POSTE_ID;

        return fetch(getBaseUrl() + '/api/generer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                poste_id: posteId,
                donnees: donnees
            })
        }).then(r => r.json());
    })
    .then(result => {
        if (result.errors && result.errors.length > 0) {
            result.errors.forEach(e => log(e));
        }

        if (result.success && result.files) {
            result.files.forEach(f => {
                log('Fichier genere : ' + f.name);
            });
            log(result.count + ' fichier(s) genere(s).');

            // Afficher les liens de telechargement
            const container = document.getElementById('generated-files');
            const list = document.getElementById('generated-files-list');
            list.innerHTML = '';
            result.files.forEach(f => {
                const a = document.createElement('a');
                a.href = f.url;
                a.className = 'btn btn-outline';
                a.setAttribute('data-c', 'blue');
                const icon = f.type === 'convention' ? 'file-earmark-word' : 'file-earmark-excel';
                a.innerHTML = '<i class="bi bi-' + icon + '"></i> ' + f.name;
                list.appendChild(a);
            });
            container.style.display = 'block';
        } else if (!result.success) {
            throw new Error(result.errors ? result.errors.join(', ') : 'Erreur inconnue');
        }
    })
    .catch(e => {
        log('Erreur : ' + e.message);
        alert('Erreur lors de la generation : ' + e.message);
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-file-earmark-plus"></i> Generer Convention + Devis';
    });
}

// ── Restauration des donnees ─────────────────────────────────────────

function restaurerDonnees() {
    if (!DONNEES_INIT || Object.keys(DONNEES_INIT).length === 0) return;

    const d = DONNEES_INIT;

    // Champs texte
    const fields = ['nps', 'org', 'rep', 'qlt', 'adr', 'tel', 'mel', 'int', 'dte',
                     'hde', 'hfi', 'loc', 'contact_nom', 'contact_tel', 'pbq',
                     'rep_legal', 'qlt_legal', 'effectif_public', 'effectif_acteurs'];
    fields.forEach(fid => {
        const el = document.getElementById('field-' + fid);
        if (el && d[fid] !== undefined && d[fid] !== null) {
            el.value = String(d[fid]);
        }
    });

    // Configuration
    if (d.is_ps === true) {
        document.getElementById('ps-oui').checked = true;
    } else {
        document.getElementById('ps-non').checked = true;
    }

    updateNbSecOptions();

    if (d.nb_sec) {
        document.getElementById('nb_sec').value = d.nb_sec;
    }

    if (d.sec_type === 'Acteurs') {
        document.getElementById('sec-acteurs').checked = true;
    } else {
        document.getElementById('sec-public').checked = true;
    }

    // Effectifs
    document.getElementById('eff-public').textContent = d.effectif_public || '-';
    document.getElementById('eff-acteurs').textContent = d.effectif_acteurs || '-';

    recalculer();
    log('Donnees du poste restaurees.');
}

// ── Initialisation ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    updateNbSecOptions();
    initFileUpload();

    if (POSTE_ID) {
        restaurerDonnees();
    } else {
        log('Pret. Selectionnez un document ou remplissez les champs manuellement.');
    }
});
