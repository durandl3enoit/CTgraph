"""Vue 3D de la pièce : révolution des contours fermés de l'esquisse autour de l'axe Z.

Incrustée en haut à droite de l'esquisse. Bouton gauche : orbite. Molette : zoom. Bouton du milieu
ou droit : déplacement. Double-clic : recadrer. Poignée en bas à gauche : redimensionner.

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
from PySide6.QtWidgets import QFrame, QLabel, QWidget

GL_LINES = 0x0001
GL_TRIANGLES = 0x0004
GL_DEPTH_BUFFER_BIT = 0x0100
GL_FLOAT = 0x1406
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT = 0x4000
GL_MULTISAMPLE = 0x809D

SEGMENTS = 96             # facettes sur un tour
ANGLE_PLI_DEG = 30.0      # en deçà, deux segments voisins du profil partagent une normale lissée (arcs, congés)
TAILLE_DEFAUT = QSize(380, 270)
TAILLE_MINI = QSize(180, 130)

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
void main() {
    float d = abs(dot(normalize(v_nrm), normalize(u_lumiere)));
    vec3 c = mix(u_couleur * (0.30 + 0.70 * d), u_couleur, u_plat);
    gl_FragColor = vec4(c, 1.0);
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
                    (p, _), (q, _), (r, _) = tri
                    if _norme(_croix(_sous(q, p), _sous(r, p))) is None:
                        continue                      # triangle écrasé sur l'axe
                    for pos, nrm in tri:
                        data.extend((pos[0], pos[1], pos[2], nrm[0], nrm[1], nrm[2]))
                    nb += 3
    return data, nb


def _bornes(data: array, nb: int) -> Tuple[QVector3D, float]:
    """Centre et rayon englobant du maillage."""
    if nb == 0:
        return QVector3D(0.0, 0.0, 0.0), 50.0
    xs = data[0::6]
    ys = data[1::6]
    zs = data[2::6]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    r = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2
    return QVector3D(cx, cy, cz), max(r, 1.0)


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
        self._centre = QVector3D(0.0, 0.0, 0.0)
        self._rayon = 50.0
        self._jamais_cadre = True
        self._lacet = -35.0
        self._tangage = 22.0
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

    def _reconstruire_maillage(self) -> None:
        self._donnees, self._nb = maillage_revolution(self._contours)
        self._centre, self._rayon = _bornes(self._donnees, self._nb)
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
        self._distance = self._rayon * 3.2
        self._pan = QVector3D(0.0, 0.0, 0.0)
        self.update()

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
            self._u = {n: self._prog.uniformLocation(n) for n in ("u_mvp", "u_nrm", "u_couleur", "u_lumiere", "u_plat")}
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

    def _matrices(self) -> Tuple[QMatrix4x4, QMatrix4x4]:
        w, h = max(self.width(), 1), max(self.height(), 1)
        proj = QMatrix4x4()
        proj.perspective(32.0, w / h, max(self._distance * 0.02, 0.1), self._distance * 6.0 + self._rayon * 8.0)
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
        if self._a_televerser:
            self._prog.bind()
            self._televerser()
            self._prog.release()
        mvp, mv = self._matrices()
        inv, ok = mv.inverted()
        nrm = inv.transposed() if ok else QMatrix4x4()
        u = self._u
        self._prog.bind()
        self._prog.setUniformValue(u["u_mvp"], mvp)
        self._prog.setUniformValue(u["u_nrm"], nrm)
        self._prog.setUniformValue(u["u_lumiere"], QVector3D(0.35, 0.55, 1.0))
        if self._nb:
            self._prog.setUniformValue(u["u_plat"], 0.0)
            self._prog.setUniformValue(u["u_couleur"], QVector3D(0.62, 0.70, 0.80) if sombre
                                       else QVector3D(0.50, 0.60, 0.72))
            self._vao.bind()
            f.glDrawArrays(GL_TRIANGLES, 0, self._nb)
            self._vao.release()
        self._prog.setUniformValue(u["u_plat"], 1.0)
        self._prog.setUniformValue(u["u_couleur"], QVector3D(0.6, 0.6, 0.6) if sombre else QVector3D(0.45, 0.45, 0.45))
        self._vao_axe.bind()
        f.glDrawArrays(GL_LINES, 0, 2)
        self._vao_axe.release()
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


class Incrustation3D(QFrame):
    """Cadre de la vue 3D : bordure, titre, poignée de redimensionnement. C'est lui que l'esquisse ancre."""

    taille_changee = Signal(QSize)

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
        self.poignee = Poignee(self)
        self.setMinimumSize(TAILLE_MINI)
        self.resize(TAILLE_DEFAUT)

    def definir_contours(self, contours: List[List[Point2]]) -> None:
        self.vue.definir_contours(contours)

    def recadrer(self) -> None:
        self.vue.recadrer()

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
        self.poignee.move(m + 1, self.height() - m - 1 - self.poignee.height())
        self.poignee.raise_()
