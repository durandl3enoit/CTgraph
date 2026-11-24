"""Vue 3D de la pièce : révolution des contours fermés de l'esquisse autour de l'axe Z.

Incrustée en haut à droite de l'esquisse. Bouton gauche : orbite. Molette : zoom. Bouton du milieu
ou droit : déplacement. Double-clic : recadrer. Poignée en bas à gauche : redimensionner.
Boutons de vues typiques : de côté, de face, de biais (angles réglables, mémorisés dans les préférences).

Repère 3D : l'axe Z de la pièce est porté par l'axe X du monde (horizontal à l'écran), le rayon
tourne dans le plan (Y, Z). Rendu par QOpenGLWidget avec un petit programme de nuanceurs, sans
dépendance à PyOpenGL. Le maillage est à facettes planes : une pièce usinée s'en accommode bien.
"""
from __future__ import annotations

import math
from array import array
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMatrix4x4, QPainter, QPen, QSurfaceFormat, QVector3D
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLVertexArrayObject
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QMenu, QToolButton, QWidget)

GL_LINES = 0x0001
GL_TRIANGLES = 0x0004
GL_DEPTH_BUFFER_BIT = 0x0100
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
GL_BACK = 0x0405
GL_CULL_FACE = 0x0B44
GL_BLEND = 0x0BE2
GL_FLOAT = 0x1406
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT = 0x4000
GL_MULTISAMPLE = 0x809D

SEGMENTS = 96             # facettes sur un tour
ANGLE_PLI_DEG = 30.0      # en deçà, deux segments voisins du profil partagent une normale lissée (arcs, congés)
TAILLE_DEFAUT = QSize(380, 270)
TAILLE_MINI = QSize(180, 130)

# vues typiques : (lacet, tangage) en degrés. Lacet autour de la verticale, tangage autour de l'horizontale.
# De côté : l'axe de la pièce à l'horizontale, comme l'esquisse. De face : on regarde la face avant, Z vers soi.
VUES = {"cote": (0.0, 0.0), "face": (-90.0, 0.0)}
BIAIS_DEFAUT = (-35.0, 22.0)


def angles_de_vue(nom: str, biais: Tuple[float, float] = BIAIS_DEFAUT) -> Tuple[float, float]:
    """Les angles (lacet, tangage) d'une vue typique ; « biais » est la vue oblique réglable."""
    if nom == "biais":
        return (float(biais[0]), float(biais[1]))
    if nom not in VUES:
        raise ValueError(f"vue inconnue : {nom}")
    return VUES[nom]

SOMMETS = """
#version 120
attribute vec3 a_pos;
attribute vec3 a_nrm;
uniform mat4 u_mvp;
uniform mat4 u_nrm;
varying vec3 v_nrm;
void main() {
    v_nrm = normalize(mat3(u_nrm) * a_nrm);
    gl_Position = u_mvp * vec4(a_pos, 1.0);
}
"""

FRAGMENTS = """
#version 120
varying vec3 v_nrm;
uniform vec3 u_couleur;
uniform vec3 u_lumiere;
uniform float u_plat;
uniform float u_alpha;
void main() {
    float d = abs(dot(normalize(v_nrm), normalize(u_lumiere)));
    vec3 c = mix(u_couleur * (0.30 + 0.70 * d), u_couleur, u_plat);
    gl_FragColor = vec4(c, u_alpha);
}
"""

Point2 = Tuple[float, float]


def _sous(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _croix(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norme(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else None


def _normales_profil(poly: Sequence[Point2], angle_pli: float) -> List[Tuple[Point2, Point2, Point2, Point2]]:
    """Pour chaque segment non dégénéré du profil : (début, fin, normale 2D au début, normale 2D à la fin).

    La normale 2D (composantes z, x) est perpendiculaire au segment. Entre deux segments voisins dont
    l'angle est inférieur à `angle_pli`, les normales sont moyennées : un arc échantillonné paraît lisse,
    un épaulement reste net. Un profil refermé sur lui-même lisse aussi la jonction.
    """
    segs = []
    for p, q in zip(poly, poly[1:]):
        dz, dx = q[0] - p[0], q[1] - p[1]
        lg = math.hypot(dz, dx)
        if lg < 1e-9:
            continue
        segs.append((p, q, (dx / lg, -dz / lg)))
    if not segs:
        return []
    ferme = len(poly) > 2 and abs(poly[0][0] - poly[-1][0]) < 1e-9 and abs(poly[0][1] - poly[-1][1]) < 1e-9
    cos_pli = math.cos(math.radians(angle_pli))

    def lissee(n1, n2):
        if n1[0] * n2[0] + n1[1] * n2[1] >= cos_pli:
            sz, sx = n1[0] + n2[0], n1[1] + n2[1]
            lg = math.hypot(sz, sx)
            if lg > 1e-12:
                return (sz / lg, sx / lg)
        return None

    out = []
    n = len(segs)
    for i, (p, q, nrm) in enumerate(segs):
        debut, fin = nrm, nrm
        if i > 0 or ferme:
            voisin = segs[i - 1][2]
            debut = lissee(voisin, nrm) or nrm
        if i < n - 1 or ferme:
            voisin = segs[(i + 1) % n][2]
            fin = lissee(nrm, voisin) or nrm
        out.append((p, q, debut, fin))
    return out


def maillage_revolution(contours: Sequence[Sequence[Point2]], segments: int = SEGMENTS,
                        angle_pli: float = ANGLE_PLI_DEG) -> Tuple[array, int]:
    """Triangles de la révolution des polylignes (z, x) autour de l'axe Z.

    Renvoie (tableau de flottants, nombre de sommets). Chaque sommet : position (3) puis normale (3).
    Les normales sont celles de la surface de révolution exacte, pas des facettes : l'éclairage d'un
    cylindre est continu quel que soit le nombre de facettes. Les triangles dégénérés (sur l'axe) sont omis.
    """
    data = array("f")
    nb = 0
    cos = [math.cos(2.0 * math.pi * j / segments) for j in range(segments)] + [1.0]
    sin = [math.sin(2.0 * math.pi * j / segments) for j in range(segments)] + [0.0]
    for poly in contours:
        for (z1, x1), (z2, x2), (nz1, nx1), (nz2, nx2) in _normales_profil(poly, angle_pli):
            for j in range(segments):
                c0, s0, c1, s1 = cos[j], sin[j], cos[j + 1], sin[j + 1]
                a = ((z1, x1 * c0, x1 * s0), (nz1, nx1 * c0, nx1 * s0))
                b = ((z2, x2 * c0, x2 * s0), (nz2, nx2 * c0, nx2 * s0))
                c = ((z2, x2 * c1, x2 * s1), (nz2, nx2 * c1, nx2 * s1))
                d = ((z1, x1 * c1, x1 * s1), (nz1, nx1 * c1, nx1 * s1))
                for tri in ((a, b, c), (a, c, d)):
                    (p, np_), (q, _), (r, _) = tri
                    g = _norme(_croix(_sous(q, p), _sous(r, p)))
                    if g is None:
                        continue                      # triangle écrasé sur l'axe
                    if g[0] * np_[0] + g[1] * np_[1] + g[2] * np_[2] < 0.0:
                        tri = (tri[0], tri[2], tri[1])   # sens de parcours accordé à la normale (élimination des faces arrière)
                    for pos, nrm in tri:
                        data.extend((pos[0], pos[1], pos[2], nrm[0], nrm[1], nrm[2]))
                    nb += 3
    return data, nb


def maillage_boite_radiale(z1: float, z2: float, r1: float, r2: float, demi_largeur: float,
                           angle: float) -> Tuple[array, int]:
    """Un bloc entre deux rayons, de z1 à z2, de largeur tangentielle 2·demi_largeur, tourné de `angle`
    radians autour de l'axe Z de la pièce : un mors de mandrin. Normales à facettes."""
    c, s = math.cos(angle), math.sin(angle)

    def tourner(z, r, t):
        # repère local : r le long du rayon, t tangentiel ; puis rotation dans le plan (Y, Z) du monde
        return (z, r * c - t * s, r * s + t * c)

    coins = {
        (i, j, k): tourner(z1 if i == 0 else z2, r1 if j == 0 else r2, -demi_largeur if k == 0 else demi_largeur)
        for i in (0, 1) for j in (0, 1) for k in (0, 1)
    }
    faces = [
        ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),   # z1
        ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)),   # z2
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),   # -t
        ((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)),   # +t
        ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)),   # r1
        ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)),   # r2
    ]
    centre = tuple(sum(c[i] for c in coins.values()) / 8.0 for i in range(3))
    data = array("f")
    nb = 0
    for face in faces:
        p, q, r, s4 = (coins[k] for k in face)
        n = _norme(_croix(_sous(q, p), _sous(r, p)))
        if n is None:
            continue
        milieu = tuple((p[i] + r[i]) / 2.0 for i in range(3))
        if sum(n[i] * (milieu[i] - centre[i]) for i in range(3)) < 0.0:
            n = (-n[0], -n[1], -n[2])                   # normale sortante et parcours accordé
            p, q, r, s4 = p, s4, r, q
        for tri in ((p, q, r), (p, r, s4)):
            for v in tri:
                data.extend((v[0], v[1], v[2], n[0], n[1], n[2]))
            nb += 3
    return data, nb


def maillages_montage(montage) -> List[Tuple[array, int, Tuple[float, float, float, float]]]:
    """Mandrin, mors, brut et contre-pointe en maillages (données, nombre de sommets, couleur RGBA)."""
    md, cp = montage.mandrin, montage.contre_pointe
    out = []
    # Les profils fermés sont parcourus dans le sens horaire (Z vers la droite, X vers le haut) : les normales
    # de révolution pointent alors vers l'extérieur et les faces arrière peuvent être éliminées au rendu.
    # corps du mandrin : tube de l'alésage au diamètre extérieur
    za, zf = montage.z_arriere_mandrin(), montage.z_face_mandrin()
    ri, re = md.alesage / 2.0, md.diametre / 2.0
    corps = [(za, re), (za, ri), (zf, ri), (zf, re), (za, re)]
    data, nb = maillage_revolution([corps], 96)
    out.append((data, nb, (0.44, 0.45, 0.49, 1.0)))
    # mors étagés : deux blocs par mors (étage de butée, face de serrage), répartis autour de l'axe
    rb = montage.rayon_brut()
    for k in range(max(md.nb_mors, 1)):
        angle = math.pi / 2 + 2.0 * math.pi * k / max(md.nb_mors, 1)
        for (z1, z2, r1, r2) in montage.blocs_mors():
            if r2 - r1 < 1e-6 or z2 - z1 < 1e-6:
                continue
            data, nb = maillage_boite_radiale(z1, z2, r1, r2, md.largeur_mors / 2.0, angle)
            out.append((data, nb, (0.60, 0.61, 0.64, 1.0)))
    # brut : cylindre ou tube translucide
    zb1, zb2 = montage.z_brut_arriere(), montage.z_brut_avant()
    rbi = montage.rayon_interieur_brut()
    profil = [(zb1, rb), (zb1, rbi), (zb2, rbi), (zb2, rb), (zb1, rb)]
    data, nb = maillage_revolution([profil], 96)
    out.append((data, nb, (0.80, 0.72, 0.45, 0.22)))
    # contre-pointe : cône dont la pointe touche la face avant du brut
    if cp.presente:
        demi = cp.diametre / 2.0
        l_cone = demi / math.tan(math.radians(cp.angle / 2.0))
        lg = max(cp.longueur, l_cone + 1.0)
        zc = zb2
        pointe = [(zc + lg, 0.0), (zc + lg, demi), (zc + l_cone, demi), (zc, 0.0), (zc + lg, 0.0)]
        data, nb = maillage_revolution([pointe], 64)
        out.append((data, nb, (0.52, 0.53, 0.57, 1.0)))
    return out


def _bornes(data: array, nb: int) -> Tuple[QVector3D, float]:
    """Centre de la boîte englobante du maillage et sa plus grande demi-étendue (échelle de la scène)."""
    if nb == 0:
        return QVector3D(0.0, 0.0, 0.0), 50.0
    xs = data[0::6]
    ys = data[1::6]
    zs = data[2::6]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    r = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2
    return QVector3D(cx, cy, cz), max(r, 1.0)


def _rayon_englobant(data: array, nb: int, centre: QVector3D) -> float:
    """Rayon de la sphère centrée sur `centre` qui contient tous les sommets : c'est elle qu'il faut cadrer."""
    if nb == 0:
        return 50.0
    cx, cy, cz = centre.x(), centre.y(), centre.z()
    return max(1.0, max(math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
                        for x, y, z in zip(data[0::6], data[1::6], data[2::6])))


CHAMP_DEG = 32.0          # ouverture verticale de la perspective


def distance_de_cadrage(rayon: float, largeur: int, hauteur: int, marge: float = 1.12) -> float:
    """Distance de la caméra pour qu'une sphère de ce rayon tienne entière dans la vue, avec une petite marge.
    La demi-ouverture limitante est la verticale, ou l'horizontale quand la vue est plus haute que large."""
    demi = math.radians(CHAMP_DEG / 2.0)
    if 0 < largeur < hauteur:
        demi = math.atan(math.tan(demi) * largeur / hauteur)
    return rayon * marge / math.sin(demi)


class Vue3D(QOpenGLWidget):
    """Le rendu OpenGL seul : maillage, axe, orbite, zoom, déplacement."""

    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        self.setFormat(fmt)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._contours: List[List[Point2]] = []
        self._donnees = array("f")
        self._nb = 0
        self._a_televerser = False
        self._montage_maillages: List[Tuple[array, int, Tuple[float, float, float, float]]] = []
        self._montage_gl: List[Tuple[QOpenGLVertexArrayObject, QOpenGLBuffer, int, Tuple[float, ...]]] = []
        self._montage_a_televerser = False
        self._centre = QVector3D(0.0, 0.0, 0.0)
        self._rayon = 50.0
        self._rayon_sphere = 50.0
        self._jamais_cadre = True
        self._lacet, self._tangage = BIAIS_DEFAUT
        self._biais: Tuple[float, float] = BIAIS_DEFAUT
        self._distance = 220.0
        self._pan = QVector3D(0.0, 0.0, 0.0)
        self._dernier: Optional[QPoint] = None
        self._mode: Optional[str] = None
        self._gl_pret = False
        self.erreur = ""

        self.message = QLabel("Fermez un contour pour voir la pièce", self)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: rgba(128, 128, 128, 200); background: transparent;")
        self.message.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reconstruire_maillage)

    # -- données ---------------------------------------------------------------------

    def definir_contours(self, contours: List[List[Point2]]) -> None:
        """Nouveaux contours fermés (z, x). Le maillage est refait un peu plus tard, pour grouper les changements."""
        self._contours = [list(c) for c in contours]
        self._timer.start(40)

    def definir_montage(self, maillages: List[Tuple[array, int, Tuple[float, float, float, float]]]) -> None:
        """Mandrin, mors, brut, contre-pointe (voir `maillages_montage`) ; liste vide pour ne rien montrer."""
        self._montage_maillages = list(maillages)
        self._montage_a_televerser = True
        self.update()

    def _reconstruire_maillage(self) -> None:
        self._donnees, self._nb = maillage_revolution(self._contours)
        self._centre, self._rayon = _bornes(self._donnees, self._nb)
        self._rayon_sphere = _rayon_englobant(self._donnees, self._nb, self._centre)
        if self._nb and self._jamais_cadre:
            self._jamais_cadre = False
            self.recadrer()
        self._a_televerser = True
        self._rafraichir_message()
        self.update()

    def _rafraichir_message(self) -> None:
        if self.erreur:
            self.message.setText("OpenGL indisponible\n" + self.erreur)
            self.message.show()
        elif self._nb == 0:
            self.message.setText("Fermez un contour pour voir la pièce")
            self.message.show()
        else:
            self.message.hide()

    def recadrer(self) -> None:
        """La pièce entière dans la vue, quelle que soit l'orientation : on cadre sa sphère englobante."""
        self._distance = distance_de_cadrage(self._rayon_sphere, self.width(), self.height())
        self._pan = QVector3D(0.0, 0.0, 0.0)
        self.update()

    # -- vues typiques -------------------------------------------------------------------

    def angles(self) -> Tuple[float, float]:
        return (self._lacet, self._tangage)

    def definir_angles(self, lacet: float, tangage: float) -> None:
        self._lacet = float(lacet) % 360.0
        self._tangage = max(-89.0, min(89.0, float(tangage)))
        self.update()

    def montrer_vue(self, nom: str) -> None:
        """Vue de côté, de face, ou de biais (la vue oblique réglable) ; recadre au passage."""
        self.definir_angles(*angles_de_vue(nom, self._biais))
        self.recadrer()

    def biais(self) -> Tuple[float, float]:
        return self._biais

    def definir_biais(self, lacet: float, tangage: float) -> None:
        self._biais = (float(lacet), max(-89.0, min(89.0, float(tangage))))

    # -- OpenGL ---------------------------------------------------------------------

    def initializeGL(self) -> None:
        try:
            self._prog = QOpenGLShaderProgram(self)
            if not self._prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, SOMMETS) \
                    or not self._prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENTS) \
                    or not self._prog.link():
                self.erreur = "nuanceurs refusés : " + self._prog.log()
                self._rafraichir_message()
                return
            # PySide6 n'adresse uniformes et attributs que par emplacement numérique
            self._u = {n: self._prog.uniformLocation(n)
                       for n in ("u_mvp", "u_nrm", "u_couleur", "u_lumiere", "u_plat", "u_alpha")}
            self._a_pos = self._prog.attributeLocation("a_pos")
            self._a_nrm = self._prog.attributeLocation("a_nrm")
            self._vao = QOpenGLVertexArrayObject()
            self._vao.create()
            self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo.create()
            self._vao_axe = QOpenGLVertexArrayObject()
            self._vao_axe.create()
            self._vbo_axe = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo_axe.create()
            self._gl_pret = True
            self._a_televerser = True
        except Exception as exc:  # pas d'OpenGL utilisable : la vue reste vide avec un message
            self.erreur = str(exc)
            self._rafraichir_message()

    def resizeGL(self, w: int, h: int) -> None:
        self.message.setGeometry(8, 8, max(w - 16, 10), max(h - 16, 10))

    def _charger(self, vao: QOpenGLVertexArrayObject, vbo: QOpenGLBuffer, donnees: array) -> None:
        vao.bind()
        vbo.bind()
        octets = donnees.tobytes()
        vbo.allocate(octets, len(octets))
        self._prog.enableAttributeArray(self._a_pos)
        self._prog.setAttributeBuffer(self._a_pos, GL_FLOAT, 0, 3, 24)
        self._prog.enableAttributeArray(self._a_nrm)
        self._prog.setAttributeBuffer(self._a_nrm, GL_FLOAT, 12, 3, 24)
        vbo.release()
        vao.release()

    def _televerser(self) -> None:
        self._charger(self._vao, self._vbo, self._donnees)
        lg = self._rayon * 1.6
        cx = self._centre.x()
        self._charger(self._vao_axe, self._vbo_axe, array("f", [cx - lg, 0, 0, 1, 0, 0, cx + lg, 0, 0, 1, 0, 0]))
        self._a_televerser = False

    def _televerser_montage(self) -> None:
        for vao, vbo, _, _ in self._montage_gl:
            vbo.destroy()
            vao.destroy()
        self._montage_gl = []
        for data, nb, couleur in self._montage_maillages:
            if nb == 0:
                continue
            vao = QOpenGLVertexArrayObject()
            vao.create()
            vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            vbo.create()
            self._charger(vao, vbo, data)
            self._montage_gl.append((vao, vbo, nb, couleur))
        self._montage_a_televerser = False

    def _matrices(self) -> Tuple[QMatrix4x4, QMatrix4x4]:
        w, h = max(self.width(), 1), max(self.height(), 1)
        proj = QMatrix4x4()
        proj.perspective(CHAMP_DEG, w / h, max(self._distance * 0.02, 0.1), self._distance * 6.0 + self._rayon * 8.0)
        vue = QMatrix4x4()
        vue.lookAt(QVector3D(0.0, 0.0, self._distance), QVector3D(0.0, 0.0, 0.0), QVector3D(0.0, 1.0, 0.0))
        modele = QMatrix4x4()
        modele.translate(self._pan)
        modele.rotate(self._tangage, 1.0, 0.0, 0.0)
        modele.rotate(self._lacet, 0.0, 1.0, 0.0)
        modele.translate(-self._centre)
        return proj * vue * modele, vue * modele

    def paintGL(self) -> None:
        pal = self.palette()
        fond = pal.color(pal.ColorGroup.Active, pal.ColorRole.Base)
        sombre = fond.lightness() < 128
        f = self.context().functions()
        f.glClearColor(fond.redF(), fond.greenF(), fond.blueF(), 1.0)
        f.glEnable(GL_DEPTH_TEST)
        f.glEnable(GL_MULTISAMPLE)
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not self._gl_pret:
            return
        self._prog.bind()
        if self._a_televerser:
            self._televerser()
        if self._montage_a_televerser:
            self._televerser_montage()
        mvp, mv = self._matrices()
        inv, ok = mv.inverted()
        nrm = inv.transposed() if ok else QMatrix4x4()
        u = self._u
        self._prog.setUniformValue(u["u_mvp"], mvp)
        self._prog.setUniformValue(u["u_nrm"], nrm)
        self._prog.setUniformValue(u["u_lumiere"], QVector3D(0.35, 0.55, 1.0))
        self._prog.setUniformValue1f(u["u_alpha"], 1.0)   # flottant explicite : la surcharge générique peut partir sur l'entier
        # d'abord l'opaque : mandrin, mors, contre-pointe (faces arrière éliminées : on voit au travers quand la
        # caméra entre dans le mandrin), puis la pièce, enfin le brut translucide
        translucides = []
        self._prog.setUniformValue1f(u["u_plat"], 0.0)
        f.glEnable(GL_CULL_FACE)
        f.glCullFace(GL_BACK)
        for vao, vbo, nb, couleur in self._montage_gl:
            if couleur[3] < 1.0:
                translucides.append((vao, nb, couleur))
                continue
            self._prog.setUniformValue(u["u_couleur"], QVector3D(*couleur[:3]))
            vao.bind()
            f.glDrawArrays(GL_TRIANGLES, 0, nb)
            vao.release()
        f.glDisable(GL_CULL_FACE)
        if self._nb:
            self._prog.setUniformValue(u["u_couleur"], QVector3D(0.62, 0.70, 0.80) if sombre
                                       else QVector3D(0.50, 0.60, 0.72))
            self._vao.bind()
            f.glDrawArrays(GL_TRIANGLES, 0, self._nb)
            self._vao.release()
        self._prog.setUniformValue1f(u["u_plat"], 1.0)
        self._prog.setUniformValue(u["u_couleur"], QVector3D(0.6, 0.6, 0.6) if sombre else QVector3D(0.45, 0.45, 0.45))
        self._vao_axe.bind()
        f.glDrawArrays(GL_LINES, 0, 2)
        self._vao_axe.release()
        if translucides:
            f.glEnable(GL_BLEND)
            # la couleur se mélange, mais l'opacité du tampon reste à 1 : sinon le fond de la fenêtre transparaîtrait
            f.glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, 0, 1)
            f.glEnable(GL_CULL_FACE)                    # seule la paroi avant du brut se voit : un voile léger
            self._prog.setUniformValue1f(u["u_plat"], 0.0)
            for vao, nb, couleur in translucides:
                self._prog.setUniformValue(u["u_couleur"], QVector3D(*couleur[:3]))
                self._prog.setUniformValue1f(u["u_alpha"], float(couleur[3]))
                vao.bind()
                f.glDrawArrays(GL_TRIANGLES, 0, nb)
                vao.release()
            f.glDisable(GL_CULL_FACE)
            f.glDisable(GL_BLEND)
        self._prog.release()

    # -- souris --------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        self._dernier = event.position().toPoint()
        self._mode = "orbite" if event.button() == Qt.MouseButton.LeftButton else "pan"
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._mode is None or self._dernier is None:
            return
        pos = event.position().toPoint()
        d = pos - self._dernier
        self._dernier = pos
        if self._mode == "orbite":
            self._lacet = (self._lacet + d.x() * 0.5) % 360.0
            self._tangage = max(-89.0, min(89.0, self._tangage + d.y() * 0.5))
        else:
            k = self._distance * 0.0016
            self._pan += QVector3D(d.x() * k, -d.y() * k, 0.0)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._mode = None
        self._dernier = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self.recadrer()
        event.accept()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta:
            self._distance = max(self._rayon * 0.3, min(self._rayon * 40.0, self._distance * (1.15 ** (-delta / 120.0))))
            self.update()
        event.accept()


class Poignee(QWidget):
    """Coin inférieur gauche de l'incrustation : le tirer redimensionne la vue, ancrée en haut à droite."""

    def __init__(self, incrustation: "Incrustation3D"):
        super().__init__(incrustation)
        self.incrustation = incrustation
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        self._depart: Optional[Tuple[QPoint, QSize]] = None

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.palette().color(self.palette().ColorRole.WindowText)
        p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 170), 1.4))
        h = self.height()
        for i in (4, 9, 14):
            p.drawLine(1, h - 1 - i, i, h - 2)
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._depart = (event.globalPosition().toPoint(), self.incrustation.size())
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._depart is None:
            return
        origine, taille = self._depart
        d = event.globalPosition().toPoint() - origine
        self.incrustation.redimensionner(taille.width() - d.x(), taille.height() + d.y())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._depart = None
        event.accept()


class DialogueBiais(QDialog):
    """Les deux angles de la vue de biais."""

    def __init__(self, lacet: float, tangage: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vue de biais")
        f = QFormLayout(self)
        self.lacet = QDoubleSpinBox()
        self.lacet.setRange(-180.0, 360.0)
        self.lacet.setDecimals(0)
        self.lacet.setSuffix("°")
        self.lacet.setValue(lacet)
        self.tangage = QDoubleSpinBox()
        self.tangage.setRange(-89.0, 89.0)
        self.tangage.setDecimals(0)
        self.tangage.setSuffix("°")
        self.tangage.setValue(tangage)
        f.addRow("Lacet (autour de la verticale ; 0 = de côté, -90 = de face)", self.lacet)
        f.addRow("Tangage (vu d'au-dessus si positif)", self.tangage)
        boutons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        f.addRow(boutons)

    def angles(self) -> Tuple[float, float]:
        return (self.lacet.value(), self.tangage.value())


STYLE_BOUTON_3D = ("QToolButton { background: rgba(0, 0, 0, 110); color: white; padding: 1px 6px; border: none; "
                   "border-radius: 3px; } QToolButton:hover { background: rgba(0, 0, 0, 170); } "
                   "QToolButton::menu-button { border: none; width: 12px; } "
                   "QToolButton::menu-arrow { image: none; width: 0; }")


class Incrustation3D(QFrame):
    """Cadre de la vue 3D : bordure, titre, boutons de vues typiques, poignée de redimensionnement.
    C'est lui que l'esquisse ancre."""

    taille_changee = Signal(QSize)
    biais_change = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setAutoFillBackground(True)
        self.vue = Vue3D(self)
        self.titre = QLabel("3D", self)
        self.titre.setStyleSheet("background: rgba(0, 0, 0, 110); color: white; padding: 1px 6px; border-radius: 3px;")
        self.titre.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.titre.adjustSize()
        # vues typiques : de côté, de face, de biais (réglable par le petit menu du bouton)
        self.barre = QWidget(self)
        h = QHBoxLayout(self.barre)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(3)
        self.boutons_vues = {}
        for nom, texte, aide in (("cote", "Côté", "Vue de côté : l'axe à l'horizontale, comme l'esquisse"),
                                 ("face", "Face", "Vue de face : la face avant de la pièce vers soi"),
                                 ("biais", "Biais", "Vue de biais ; la flèche règle ses angles")):
            b = QToolButton(self.barre)
            b.setText(texte)
            b.setToolTip(aide)
            b.setStyleSheet(STYLE_BOUTON_3D)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, n=nom: self.vue.montrer_vue(n))
            h.addWidget(b)
            self.boutons_vues[nom] = b
        menu = QMenu(self.boutons_vues["biais"])
        menu.addAction("Mémoriser la vue actuelle comme vue de biais", self.memoriser_biais)
        menu.addAction("Angles de la vue de biais…", self.regler_biais)
        self.boutons_vues["biais"].setMenu(menu)
        self.boutons_vues["biais"].setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.boutons_vues["biais"].setText("Biais ▾")
        self.barre.adjustSize()
        self.poignee = Poignee(self)
        self.setMinimumSize(TAILLE_MINI)
        self.resize(TAILLE_DEFAUT)

    def definir_contours(self, contours: List[List[Point2]]) -> None:
        self.vue.definir_contours(contours)

    def definir_montage(self, maillages) -> None:
        self.vue.definir_montage(maillages)

    def recadrer(self) -> None:
        self.vue.recadrer()

    def montrer_vue(self, nom: str) -> None:
        self.vue.montrer_vue(nom)

    def definir_biais(self, lacet: float, tangage: float) -> None:
        self.vue.definir_biais(lacet, tangage)

    def memoriser_biais(self) -> None:
        lacet, tangage = self.vue.angles()
        self.vue.definir_biais(lacet, tangage)
        self.biais_change.emit(*self.vue.biais())

    def regler_biais(self) -> None:
        dlg = DialogueBiais(*self.vue.biais(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vue.definir_biais(*dlg.angles())
            self.biais_change.emit(*self.vue.biais())
            self.vue.montrer_vue("biais")

    def redimensionner(self, w: int, h: int) -> None:
        parent = self.parentWidget()
        w = max(TAILLE_MINI.width(), w)
        h = max(TAILLE_MINI.height(), h)
        if parent is not None:
            w = min(w, max(parent.width() - 20, TAILLE_MINI.width()))
            h = min(h, max(parent.height() - 20, TAILLE_MINI.height()))
        if QSize(w, h) != self.size():
            self.resize(w, h)
            self.taille_changee.emit(self.size())
            if parent is not None and hasattr(parent, "placer_superposition"):
                parent.placer_superposition()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        m = self.frameWidth()
        self.vue.setGeometry(m, m, self.width() - 2 * m, self.height() - 2 * m)
        self.titre.move(m + 6, m + 6)
        self.titre.raise_()
        self.barre.move(self.titre.x() + self.titre.width() + 8, m + 6)
        self.barre.raise_()
        self.poignee.move(m + 1, self.height() - m - 1 - self.poignee.height())
        self.poignee.raise_()
