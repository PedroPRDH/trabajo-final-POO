#!/usr/bin/env python3
"""Dibuja los personajes originales de la versión web (pixel art generado por código).

Uso:  python3 tools/crear_personajes.py            # escribe los WebP en docs/img/
      python3 tools/crear_personajes.py --hoja     # además guarda una hoja de muestra en /tmp

Por cada personaje crea:
  ing_<id>.webp          cuerpo entero (380 px de alto)
  foto_carnet_<id>.webp  busto para el carnet (170 px de alto)
  hue_<id>.webp          huella dactilar (110 px de alto)
Todo con fondo transparente. Se dibuja en una grilla de 64x76 y se amplía x5 sin suavizar.
"""
import math, random, sys, pathlib
from PIL import Image

W, H, ESC = 64, 76, 5
DESTINO = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'img'


def hexa(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

def mezclar(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def claro(c): return mezclar(c, (255, 255, 255), 0.28)
def oscuro(c): return mezclar(c, (10, 5, 25), 0.38)


class Lienzo:
    def __init__(self):
        self.p = [[None] * W for _ in range(H)]

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.p[y][x] = c

    def rect(self, x0, y0, x1, y1, c, sombra=True):
        """Rectángulo [x0,x1) x [y0,y1) con luz a la izquierda y sombra a la derecha."""
        ancho = max(1, x1 - x0)
        for y in range(y0, y1):
            for x in range(x0, x1):
                t = (x - x0) / ancho
                self.px(x, y, claro(c) if (sombra and t < 0.22) else oscuro(c) if (sombra and t > 0.74) else c)

    def elipse(self, cx, cy, rx, ry, c, sombra=True):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                if dx * dx + dy * dy <= 1:
                    t = dx * 0.6 + dy * 0.55
                    self.px(x, y, claro(c) if (sombra and t < -0.38) else oscuro(c) if (sombra and t > 0.42) else c)

    def linea(self, x0, y0, x1, y1, c, grosor=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            for a in range(grosor):
                for b in range(grosor):
                    self.px(x + a, y + b, c)

    def simetrico(self, fn):
        """Ejecuta fn(espejo) dos veces: una normal y otra reflejada respecto al eje central."""
        fn(lambda x: x)
        fn(lambda x: W - 1 - x)

    def contorno(self, c=(20, 12, 24)):
        nuevo = [fila[:] for fila in self.p]
        for y in range(H):
            for x in range(W):
                if self.p[y][x] is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < W and 0 <= yy < H and self.p[yy][xx] is not None:
                            nuevo[y][x] = c
                            break
        self.p = nuevo

    def imagen(self, caja=None):
        x0, y0, x1, y1 = caja or (0, 0, W, H)
        im = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
        for y in range(y0, y1):
            for x in range(x0, x1):
                c = self.p[y][x]
                if c is not None:
                    im.putpixel((x - x0, y - y0), c + (255,))
        return im


# ---------------------------------------------------------------- personajes
def ojos(l, y, sep, c_ojo, c_brillo=(255, 255, 255), tam=2):
    for lado in (-1, 1):
        x = 32 + lado * sep
        l.rect(x - tam // 2 - (0 if lado > 0 else 0), y, x - tam // 2 + tam, y + tam + 1, c_ojo, False)
        l.px(x - tam // 2 + (1 if lado < 0 else 0), y, c_brillo)

def mundo_minero():
    l = Lienzo()
    piel, casco, chaleco, mono, bota = map(hexa, ('#c68a5a', '#f2c230', '#e8741c', '#2f4a7a', '#3a2a22'))
    # piernas y botas
    l.rect(24, 52, 31, 70, mono); l.rect(33, 52, 40, 70, mono)
    l.rect(22, 69, 31, 74, bota); l.rect(33, 69, 42, 74, bota)
    # torso con chaleco y franjas reflectantes
    l.rect(20, 32, 44, 55, mono)
    l.rect(22, 32, 42, 54, chaleco)
    l.rect(22, 40, 42, 43, (235, 235, 215), False); l.rect(22, 47, 42, 50, (235, 235, 215), False)
    l.rect(31, 32, 33, 54, oscuro(chaleco), False)
    # brazos
    l.rect(15, 33, 21, 52, mono); l.rect(43, 33, 49, 52, mono)
    l.elipse(18, 54, 4, 4, piel); l.elipse(46, 54, 4, 4, piel)
    # pico en la mano derecha
    l.rect(53, 28, 55, 62, hexa('#6a4a2b')); l.rect(44, 25, 62, 29, hexa('#9aa3ad')); l.rect(44, 28, 47, 31, hexa('#9aa3ad'))
    # cuello, cabeza, bigote
    l.rect(28, 28, 36, 34, oscuro(piel))
    l.elipse(32, 21, 11, 11, piel)
    l.rect(24, 24, 40, 27, hexa('#5a3a24'), False); l.rect(27, 26, 37, 29, hexa('#5a3a24'), False)
    ojos(l, 19, 4, (30, 20, 20))
    l.rect(30, 21, 34, 23, oscuro(piel), False)
    # casco con linterna
    l.elipse(32, 12, 13, 9, casco)
    l.rect(18, 12, 46, 16, casco); l.rect(16, 15, 48, 18, oscuro(casco))
    l.rect(28, 6, 36, 12, hexa('#d9dde3'), False); l.rect(30, 8, 34, 11, (255, 250, 170), False)
    l.contorno(); return l

def mundo_robot():
    l = Lienzo()
    acero, oscuro_m, cian, naranja = map(hexa, ('#9aa6b4', '#4a5563', '#43e6ff', '#e8741c'))
    # piernas
    l.rect(24, 54, 31, 70, oscuro_m); l.rect(33, 54, 40, 70, oscuro_m)
    l.rect(21, 68, 31, 74, acero); l.rect(33, 68, 43, 74, acero)
    # torso
    l.rect(19, 32, 45, 56, acero)
    l.rect(24, 36, 40, 46, (18, 28, 40), False); l.rect(26, 38, 38, 44, cian, False)
    for x in (28, 31, 34): l.rect(x, 39, x + 2, 43, (18, 28, 40), False)
    l.rect(20, 50, 44, 54, oscuro_m)
    # correa y bolso de mensajero
    l.linea(21, 32, 42, 55, naranja, 3); l.rect(38, 50, 50, 62, naranja); l.rect(38, 50, 50, 53, oscuro(naranja), False)
    l.rect(42, 54, 46, 57, (240, 240, 230), False)
    # brazos
    l.rect(12, 33, 19, 52, acero); l.rect(45, 33, 52, 52, acero)
    l.rect(11, 52, 20, 58, oscuro_m); l.rect(44, 52, 53, 58, oscuro_m)
    # cabeza caja con visor y antena
    l.rect(28, 28, 36, 33, oscuro_m)
    l.rect(20, 10, 44, 29, acero)
    l.rect(22, 15, 42, 24, (18, 28, 40), False); l.rect(24, 17, 40, 22, cian, False)
    l.rect(27, 17, 29, 22, (255, 255, 255), False); l.rect(35, 17, 37, 22, (255, 255, 255), False)
    l.rect(31, 4, 33, 10, oscuro_m, False); l.elipse(32, 4, 3, 3, naranja, False)
    l.rect(16, 15, 20, 23, oscuro_m); l.rect(44, 15, 48, 23, oscuro_m)
    l.contorno(); return l

def mundo_alien3():
    l = Lienzo()
    piel, tunica, oro = map(hexa, ('#3fc7a5', '#6a3fb5', '#f2c230'))
    # piernas delgadas
    l.rect(26, 54, 31, 72, piel); l.rect(33, 54, 38, 72, piel)
    l.elipse(27, 73, 5, 2, oscuro(piel)); l.elipse(37, 73, 5, 2, oscuro(piel))
    # túnica
    l.rect(21, 33, 43, 58, tunica)
    l.rect(21, 33, 43, 36, oro, False); l.rect(21, 55, 43, 58, oro, False)
    l.rect(31, 33, 33, 58, oscuro(tunica), False)
    l.elipse(32, 45, 3, 3, hexa('#43e6ff'), False)
    # brazos largos
    l.rect(15, 34, 21, 56, piel); l.rect(43, 34, 49, 56, piel)
    l.elipse(18, 59, 4, 4, piel); l.elipse(46, 59, 4, 4, piel)
    # cabeza grande y alargada
    l.rect(29, 30, 35, 34, oscuro(piel))
    l.elipse(32, 17, 13, 15, piel)
    # tres ojos amarillos con pupila
    for x, y in ((24, 15), (32, 11), (40, 15)):
        l.elipse(x, y, 3.2, 3.2, hexa('#ffe45c'), False); l.rect(int(x) - 1, int(y) - 1, int(x) + 1, int(y) + 2, (25, 10, 40), False)
        l.px(int(x) - 2, int(y) - 2, (255, 255, 255))
    l.rect(29, 25, 36, 26, oscuro(piel), False)
    # crestas en la cabeza
    for x in (26, 29, 32, 35, 38):
        l.rect(x, 1 if x == 32 else 3, x + 2, 5, oscuro(piel), False)
    l.contorno(); return l

def mundo_guardian():
    l = Lienzo()
    tela, tela_osc, cristal, borde = map(hexa, ('#5b3aa0', '#3a2370', '#6ff0ff', '#c9b8ff'))
    # túnica larga
    l.rect(19, 34, 45, 74, tela)
    l.rect(19, 68, 45, 74, tela_osc); l.rect(31, 34, 33, 74, tela_osc, False)
    l.rect(19, 56, 45, 59, hexa('#f2c230'), False)
    # hombreras de cristal
    for lado in (-1, 1):
        cx = 32 + lado * 15
        l.elipse(cx, 36, 6, 5, cristal); l.rect(int(cx) - 1, 30, int(cx) + 2, 36, claro(cristal), False)
    # brazos y manos
    l.rect(14, 38, 20, 56, tela); l.rect(44, 38, 50, 56, tela)
    l.elipse(17, 58, 3.5, 3.5, hexa('#d9b08c')); l.elipse(47, 58, 3.5, 3.5, hexa('#d9b08c'))
    # bastón con cristal
    l.rect(52, 20, 54, 72, hexa('#6a4a2b')); l.elipse(53, 17, 4, 6, cristal)
    l.px(52, 14, (255, 255, 255))
    # gema pectoral
    l.elipse(32, 42, 4, 5, cristal)
    # capucha y cara en sombra con ojos brillantes
    l.elipse(32, 21, 15, 17, tela)
    l.elipse(32, 24, 9, 11, (12, 8, 28), False)
    for x in (27, 35):
        l.rect(x, 22, x + 3, 25, cristal, False)
    l.rect(26, 33, 38, 36, tela_osc)
    l.rect(30, 2, 34, 6, borde, False)
    l.contorno(); return l

def mundo_viajera():
    l = Lienzo()
    piel, pelo, chaqueta, pant, bufanda = map(hexa, ('#e8b890', '#c4421f', '#3f7a4a', '#4a3a5a', '#f2c230'))
    # piernas y botas
    l.rect(24, 52, 31, 70, pant); l.rect(33, 52, 40, 70, pant)
    l.rect(22, 68, 31, 74, hexa('#5a3a22')); l.rect(33, 68, 42, 74, hexa('#5a3a22'))
    # chaqueta
    l.rect(20, 33, 44, 56, chaqueta)
    l.rect(31, 33, 33, 56, oscuro(chaqueta), False)
    l.rect(20, 50, 44, 53, hexa('#5a3a22'), False); l.rect(30, 50, 34, 54, hexa('#d9b44a'), False)
    # bolso cruzado
    l.linea(21, 33, 42, 54, hexa('#8a5a2b'), 2); l.rect(38, 52, 49, 62, hexa('#8a5a2b'))
    # brazos
    l.rect(15, 34, 21, 53, chaqueta); l.rect(43, 34, 49, 53, chaqueta)
    l.elipse(18, 55, 4, 4, piel); l.elipse(46, 55, 4, 4, piel)
    # bufanda
    l.rect(24, 29, 40, 35, bufanda); l.rect(36, 33, 41, 46, bufanda)
    # cabeza, pelo con rodete, antiparras
    l.elipse(32, 20, 10.5, 11, piel)
    l.elipse(32, 12, 12, 8, pelo); l.rect(20, 12, 24, 24, pelo); l.rect(40, 12, 44, 24, pelo)
    l.elipse(32, 3, 5, 4, pelo)
    l.rect(22, 11, 42, 14, hexa('#8a8f98'), False)
    for x in (26, 36):
        l.elipse(x, 12, 3.2, 2.6, hexa('#43e6ff'), False); l.px(x - 1, 11, (255, 255, 255))
    ojos(l, 19, 4, (40, 25, 20))
    l.rect(30, 23, 34, 24, hexa('#b0604a'), False)
    l.contorno(); return l


# ---------------------------------------------------------------- huellas
def huella(semilla, k=1.0):
    rnd = random.Random(semilla)
    w, h = 82, 110
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    cx, cy = w / 2 + rnd.uniform(-6, 6), h * 0.5 + rnd.uniform(-8, 8)
    ang, freq = rnd.uniform(0, math.pi), rnd.uniform(0.62, 0.78) * k
    fases = [rnd.uniform(0, 6.28) for _ in range(3)]
    for y in range(h):
        for x in range(w):
            if ((x - w / 2) / (w / 2 - 2)) ** 2 + ((y - h / 2) / (h / 2 - 2)) ** 2 > 1:
                continue
            dx, dy = x - cx, (y - cy) * 0.82
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx) + ang
            v = math.sin(r * freq + 1.4 * math.sin(a * 2 + fases[0]) + 0.45 * math.sin(r * 0.15 + fases[1]) + 0.9 * (a / 6.28))
            if v > 0.1 and rnd.random() > 0.035:
                im.putpixel((x, y), (92 + rnd.randint(-8, 8), 38, 38, 255))
    return im


PERSONAJES = {
    'minero':          (mundo_minero,  1),
    'robot_mensajero': (mundo_robot,   2),
    'alien_tres_ojos': (mundo_alien3,  3),
    'guardian_cristal': (mundo_guardian, 4),
    'viajera_naranja': (mundo_viajera, 5),
}
# Recorte del busto para el carnet: 28 columnas x 34 filas (x5 = 140x170)
CAJA_CARNET = (18, 0, 46, 34)


def generar(hoja=False):
    DESTINO.mkdir(parents=True, exist_ok=True)
    imagenes = []
    for nombre, (fn, semilla) in PERSONAJES.items():
        l = fn()
        cuerpo = l.imagen().resize((W * ESC, H * ESC), Image.NEAREST)
        carnet = l.imagen(CAJA_CARNET)
        carnet = carnet.resize((carnet.width * ESC, carnet.height * ESC), Image.NEAREST)
        huel = huella(semilla * 101)
        cuerpo.save(DESTINO / f'ing_{nombre}.webp', 'WEBP', quality=92, method=6)
        carnet.save(DESTINO / f'foto_carnet_{nombre}.webp', 'WEBP', quality=92, method=6)
        huel.save(DESTINO / f'hue_huella_{nombre}.webp', 'WEBP', quality=92, method=6)
        imagenes.append((cuerpo, carnet, huel))
        print('listo:', nombre)
    if hoja:
        ancho = sum(c.width + 20 for c, _, _ in imagenes) + 20
        sh = Image.new('RGBA', (ancho, 380 + 190 + 130), (205, 195, 165, 255)); x = 10
        for c, f, hu in imagenes:
            sh.alpha_composite(c, (x, 5)); sh.alpha_composite(f, (x, 395)); sh.alpha_composite(hu, (x + 150, 395)); x += c.width + 20
        sh.convert('RGB').save('/tmp/claude-0/hoja_personajes.png'); print('hoja en /tmp/claude-0/hoja_personajes.png')


if __name__ == '__main__':
    generar('--hoja' in sys.argv)
