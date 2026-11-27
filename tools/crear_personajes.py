#!/usr/bin/env python3
"""Dibuja los personajes originales de la versión web (pixel art generado por código).

Uso:  python3 tools/crear_personajes.py            # escribe los WebP en docs/img/
      python3 tools/crear_personajes.py --hoja     # además guarda una hoja de muestra en /tmp

Por cada personaje crea:
  ing_<id>.webp          cuerpo entero (380 px de alto)
  foto_carnet_<id>.webp  busto para el carnet (170 px de alto)
  hue_huella_<id>.webp   huella dactilar (110 px de alto)
Todo con fondo transparente. Se dibuja en una grilla de 80x95 y se amplía x4 sin suavizar.

Técnicas para acercarse al arte original: iluminación desde arriba a la izquierda con 5 tonos y trama
(dithering), textura de tela/metal con ruido, contornos del color de cada zona (no negro puro), líneas
internas donde una pieza se apoya sobre otra, ojos con reflejo y gemas con brillo.
"""
import math, random, sys, pathlib
from PIL import Image

W, H, ESC = 80, 95, 4
DESTINO = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'img'
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def hexa(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

def mez(a, b, t):
    return tuple(max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3))

def rampa(c):
    """5 tonos: sombra profunda, sombra, base, luz, brillo (las sombras se enfrían y las luces se calientan)."""
    return [mez(c, (18, 10, 48), 0.62), mez(c, (30, 20, 70), 0.38), c, mez(c, (255, 244, 210), 0.22), mez(c, (255, 252, 235), 0.55)]


class Lienzo:
    def __init__(self, semilla=1):
        self.p = [[None] * W for _ in range(H)]
        self.parte = [[0] * W for _ in range(H)]
        self.n = 0
        self.rnd = random.Random(semilla)

    # -- primitivas -------------------------------------------------
    def _poner(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.p[y][x] = c
            self.parte[y][x] = self.n

    def _tono(self, r, luz, x, y, ruido):
        v = (luz + 1) / 2 * 4 + (BAYER[y % 4][x % 4] / 16 - 0.5) * 0.5 + self.rnd.uniform(-ruido, ruido)
        return r[max(0, min(4, int(round(v))))]

    def elipse(self, cx, cy, rx, ry, c, ruido=0.07, luz_extra=0.0):
        """Volumen esférico."""
        self.n += 1
        r = rampa(c)
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                d2 = dx * dx + dy * dy
                if d2 <= 1:
                    nz = math.sqrt(1 - d2)
                    luz = -0.55 * dx - 0.62 * dy + 0.56 * nz - 0.42 + luz_extra
                    self._poner(x, y, self._tono(r, luz * 1.5, x, y, ruido))

    def cilindro(self, x0, y0, x1, y1, c, ruido=0.07, radio=2, luz_extra=0.0):
        """Volumen cilíndrico vertical (la luz cambia de izquierda a derecha) con esquinas redondeadas."""
        self.n += 1
        r = rampa(c)
        cx, ancho = (x0 + x1) / 2, (x1 - x0) / 2
        for y in range(y0, y1):
            for x in range(x0, x1):
                if radio and (x - x0 + y - y0 < radio or x1 - 1 - x + y - y0 < radio or x - x0 + y1 - 1 - y < radio or x1 - 1 - x + y1 - 1 - y < radio):
                    continue
                dx = (x + 0.5 - cx) / ancho
                luz = -0.9 * dx + 0.25 - 0.18 * (y - y0) / max(1, y1 - y0) + luz_extra
                self._poner(x, y, self._tono(r, luz * 1.35, x, y, ruido))

    def placa(self, x0, y0, x1, y1, c, ruido=0.1, radio=1):
        """Placa plana (metal, cuero): luz en el borde superior/izquierdo, sombra abajo/derecha."""
        self.n += 1
        r = rampa(c)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if radio and (x - x0 + y - y0 < radio or x1 - 1 - x + y - y0 < radio or x - x0 + y1 - 1 - y < radio or x1 - 1 - x + y1 - 1 - y < radio):
                    continue
                i = 2
                if y == y0 or x == x0: i = 3
                if y >= y1 - 2 or x >= x1 - 2: i = 1
                if y == y0 and x < x0 + (x1 - x0) // 2: i = 4
                t = self.rnd.uniform(-ruido, ruido)
                self._poner(x, y, r[max(0, min(4, int(round(i + t * 3))))])

    def linea(self, x0, y0, x1, y1, c, grosor=2, ruido=0.1):
        self.n += 1
        r = rampa(c)
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            for a in range(grosor):
                for b in range(grosor):
                    k = 3 if (a == 0 and b == 0) else 1 if (a == grosor - 1 and b == grosor - 1) else 2
                    self._poner(int(x) + a, int(y) + b, r[max(0, min(4, k + (1 if self.rnd.random() < ruido else 0)))])

    def punto(self, x, y, c):
        self.n += 1
        self._poner(x, y, c)

    def brillo(self, x, y, c=(255, 255, 255)):
        self._poner(x, y, c)

    def gema(self, cx, cy, rx, ry, c):
        """Gema luminosa: núcleo claro, borde saturado y un reflejo."""
        self.elipse(cx, cy, rx, ry, mez(c, (0, 0, 0), 0.25), ruido=0.05)
        self.elipse(cx, cy, rx - 1, ry - 1, c, ruido=0.0, luz_extra=0.5)
        self.brillo(int(cx - rx / 2), int(cy - ry / 2))

    def ojo(self, cx, cy, rx, ry, iris, pupila=(12, 8, 24)):
        self.elipse(cx, cy, rx, ry, pupila, ruido=0.0)
        if iris:
            self.elipse(cx, cy + 0.6, rx - 1.2, ry - 1.2, iris, ruido=0.0, luz_extra=0.2)
            self.elipse(cx, cy + 0.6, max(1, rx - 2.4), max(1, ry - 2.4), pupila, ruido=0.0)
        self.brillo(int(cx - rx * 0.4), int(cy - ry * 0.5))
        self.brillo(int(cx - rx * 0.4) + 1, int(cy - ry * 0.5))
        self.brillo(int(cx + rx * 0.35), int(cy + ry * 0.4), (210, 235, 255))

    # -- acabado ----------------------------------------------------
    def acabado(self):
        # 1) línea interna: el borde de una pieza que queda debajo de otra se oscurece
        res = [fila[:] for fila in self.p]
        for y in range(H):
            for x in range(W):
                c = self.p[y][x]
                if c is None:
                    continue
                for dx, dy in ((1, 0), (0, 1)):
                    xx, yy = x + dx, y + dy
                    if xx < W and yy < H and self.p[yy][xx] is not None and self.parte[yy][xx] > self.parte[y][x] + 0:
                        if self.parte[yy][xx] != self.parte[y][x]:
                            res[y][x] = mez(c, (15, 8, 30), 0.5)
        self.p = res
        # 2) contorno exterior del color de la zona (no negro puro)
        out = [fila[:] for fila in self.p]
        for y in range(H):
            for x in range(W):
                if self.p[y][x] is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < W and 0 <= yy < H and self.p[yy][xx] is not None:
                            out[y][x] = mez(self.p[yy][xx], (10, 4, 20), 0.78)
                            break
        self.p = out
        return self

    def imagen(self, caja=None):
        x0, y0, x1, y1 = caja or (0, 0, W, H)
        im = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
        for y in range(y0, y1):
            for x in range(x0, x1):
                c = self.p[y][x]
                if c is not None:
                    im.putpixel((x - x0, y - y0), c + (255,))
        return im


# ---------------------------------------------------------------- personajes (centro x = 40)
def minero():
    l = Lienzo(11)
    piel, casco, chaleco, mono, cuero, metal = map(hexa, ('c98e5e', 'f4c52e', 'ec7a1c', '35507e', '6a4128', 'a7b0bd'))
    # botas y piernas
    l.cilindro(29, 66, 38, 88, mono); l.cilindro(42, 66, 51, 88, mono)
    l.placa(26, 85, 39, 93, cuero, radio=2); l.placa(41, 85, 54, 93, cuero, radio=2)
    l.placa(26, 90, 39, 93, hexa('2b1a12')); l.placa(41, 90, 54, 93, hexa('2b1a12'))
    # pico (detrás del brazo derecho)
    l.cilindro(64, 34, 67, 82, cuero, radio=1)
    l.placa(52, 31, 76, 36, metal, radio=2); l.placa(52, 34, 57, 41, metal, radio=1); l.placa(71, 34, 76, 41, metal, radio=1)
    # torso
    l.cilindro(25, 40, 55, 70, mono, radio=3)
    l.cilindro(27, 40, 53, 66, chaleco, radio=3)
    l.placa(27, 50, 53, 54, hexa('e8e8d0'), radio=0); l.placa(27, 58, 53, 62, hexa('e8e8d0'), radio=0)
    l.placa(39, 40, 41, 66, mez(chaleco, (0, 0, 0), 0.4), radio=0)
    l.placa(25, 64, 55, 69, cuero, radio=1); l.placa(37, 64, 43, 69, hexa('d9b44a'), radio=1)
    l.placa(30, 55, 36, 61, mez(mono, (0, 0, 0), 0.2), radio=1)  # bolsillo
    # brazos y manos
    l.cilindro(17, 41, 26, 64, mono, radio=3); l.cilindro(54, 41, 63, 64, mono, radio=3)
    l.placa(17, 58, 26, 62, hexa('e8e8d0'), radio=0); l.placa(54, 58, 63, 62, hexa('e8e8d0'), radio=0)
    l.elipse(21.5, 67, 5, 5, piel); l.elipse(58.5, 67, 5, 5, piel)
    # cuello, cabeza, barba y bigote
    l.cilindro(35, 33, 45, 42, mez(piel, (0, 0, 0), 0.25), radio=1)
    l.elipse(40, 26, 13, 13.5, piel)
    l.elipse(40, 36, 11, 6.5, hexa('5a3a24'), ruido=0.2)
    l.elipse(40, 32, 8.5, 3, hexa('6a4228'), ruido=0.2)
    l.ojo(34, 27.5, 3, 2.8, None, (30, 20, 20)); l.ojo(46, 27.5, 3, 2.8, None, (30, 20, 20))
    l.placa(31, 24, 38, 26, hexa('4a2e1c'), radio=0); l.placa(42, 24, 49, 26, hexa('4a2e1c'), radio=0)
    # casco
    l.elipse(40, 16, 16, 12, casco, ruido=0.1)
    l.placa(22, 17, 58, 22, casco, radio=2)
    l.placa(21, 21, 59, 24, mez(casco, (60, 20, 0), 0.4), radio=1)
    l.placa(35, 6, 45, 15, hexa('d4d9e0'), radio=1); l.gema(40, 10.5, 3.5, 3, hexa('fff7a8'))
    l.placa(29, 11, 31, 20, mez(casco, (255, 255, 255), 0.3), radio=0)
    return l.acabado()


def robot():
    l = Lienzo(22)
    acero, osc, cian, nar, cuero = map(hexa, ('9fabba', '4b5766', '47e8ff', 'ee7a1c', '8a4f25'))
    # piernas y pies
    l.cilindro(30, 68, 38, 86, osc); l.cilindro(42, 68, 50, 86, osc)
    l.placa(26, 84, 39, 93, acero, radio=2); l.placa(41, 84, 54, 93, acero, radio=2)
    l.placa(30, 66, 38, 70, hexa('d6dde6'), radio=1); l.placa(42, 66, 50, 70, hexa('d6dde6'), radio=1)
    # torso
    l.placa(22, 40, 58, 70, acero, radio=3)
    l.placa(27, 44, 53, 58, hexa('141c28'), radio=2)
    l.gema(40, 51, 10, 4.5, cian)
    for x in (33, 38, 43): l.placa(x, 47, x + 2, 55, hexa('141c28'), radio=0)
    for i in range(4): l.placa(26 + i * 7, 62, 30 + i * 7, 66, osc, radio=0)
    l.placa(22, 66, 58, 70, osc, radio=1)
    # tornillos
    for x, y in ((25, 43), (55, 43), (25, 66), (55, 66)): l.punto(x, y, hexa('d6dde6'))
    # brazos
    l.placa(11, 42, 22, 64, acero, radio=3); l.placa(58, 42, 69, 64, acero, radio=3)
    l.placa(10, 62, 23, 74, osc, radio=3); l.placa(57, 62, 70, 74, osc, radio=3)
    l.placa(12, 47, 21, 50, cian, radio=0); l.placa(59, 47, 68, 50, cian, radio=0)
    # correa y bolso de mensajero
    l.linea(26, 41, 52, 68, cuero, 3)
    l.placa(46, 62, 64, 80, nar, radio=2); l.placa(46, 62, 64, 68, mez(nar, (0, 0, 0), 0.35), radio=1)
    l.placa(53, 66, 57, 70, hexa('d9b44a'), radio=0)
    l.placa(50, 73, 60, 77, hexa('f4eee0'), radio=0)
    # cuello y cabeza
    l.cilindro(34, 34, 46, 42, osc, radio=1)
    l.placa(22, 11, 58, 36, acero, radio=4)
    l.placa(26, 17, 54, 29, hexa('141c28'), radio=3)
    l.gema(34, 23, 4.5, 3.5, cian); l.gema(46, 23, 4.5, 3.5, cian)
    l.placa(28, 31, 52, 33, osc, radio=0)
    for x in (30, 35, 40, 45, 50): l.punto(x, 32, hexa('d6dde6'))
    l.placa(16, 18, 22, 30, osc, radio=1); l.placa(58, 18, 64, 30, osc, radio=1)
    l.cilindro(38, 4, 42, 12, osc, radio=0); l.gema(40, 4, 3.5, 3.5, nar)
    return l.acabado()


def alien3():
    l = Lienzo(33)
    piel, tun, oro, cian = map(hexa, ('3cc9a6', '6d42b8', 'f4c52e', '47e8ff'))
    # piernas y pies
    l.cilindro(32, 68, 38, 90, piel, radio=2); l.cilindro(42, 68, 48, 90, piel, radio=2)
    l.elipse(33, 91, 7, 3, mez(piel, (0, 0, 0), 0.2)); l.elipse(47, 91, 7, 3, mez(piel, (0, 0, 0), 0.2))
    # túnica con ribetes dorados
    l.cilindro(25, 44, 55, 72, tun, radio=3)
    l.placa(25, 44, 55, 48, oro, radio=1); l.placa(25, 68, 55, 72, oro, radio=1)
    l.placa(39, 48, 41, 68, mez(tun, (0, 0, 0), 0.4), radio=0)
    l.linea(28, 50, 38, 66, mez(tun, (255, 255, 255), 0.15), 1); l.linea(52, 50, 42, 66, mez(tun, (255, 255, 255), 0.15), 1)
    l.placa(25, 58, 55, 61, hexa('3a2370'), radio=0)
    l.gema(40, 59.5, 4, 4, cian)
    # brazos largos y manos de tres dedos
    l.cilindro(16, 45, 25, 66, piel, radio=3); l.cilindro(55, 45, 64, 66, piel, radio=3)
    l.placa(16, 62, 25, 66, oro, radio=0); l.placa(55, 62, 64, 66, oro, radio=0)
    for x0 in (14, 59):
        l.elipse(x0 + 4, 70, 5, 5, piel)
        for k in range(3): l.cilindro(x0 + k * 3, 72, x0 + k * 3 + 2, 79, mez(piel, (0, 0, 0), 0.1), radio=0)
    # cuello y cabeza alargada
    l.cilindro(36, 38, 44, 46, mez(piel, (0, 0, 0), 0.25), radio=1)
    l.elipse(40, 22, 17, 20, piel)
    # crestas
    for i, x in enumerate((30, 34, 38, 42, 46, 50)):
        l.cilindro(x - 1, 1 if i in (2, 3) else 4, x + 2, 9, mez(piel, (0, 0, 0), 0.18), radio=1)
    # tres ojos
    for x, y in ((29, 20), (40, 13), (51, 20)):
        l.elipse(x, y, 4.6, 4.6, hexa('ffe65c'), ruido=0.05)
        l.ojo(x, y + 0.5, 2.6, 3.2, None, (25, 10, 40))
    l.placa(36, 32, 44, 33, mez(piel, (0, 0, 0), 0.45), radio=0)
    l.punto(39, 26, mez(piel, (0, 0, 0), 0.3)); l.punto(41, 26, mez(piel, (0, 0, 0), 0.3))
    return l.acabado()


def guardian():
    l = Lienzo(44)
    tela, osc, cristal, oro, piel = map(hexa, ('5d3ca3', '36206e', '70f0ff', 'f4c52e', 'd9b08c'))
    # túnica larga
    l.cilindro(22, 44, 58, 93, tela, radio=3)
    l.placa(22, 86, 58, 93, osc, radio=2)
    l.placa(39, 44, 41, 93, osc, radio=0)
    for x in (28, 33, 47, 52): l.linea(x, 52, x + (-1 if x < 40 else 1), 88, mez(tela, (0, 0, 0), 0.25), 1)
    l.placa(22, 70, 58, 74, oro, radio=0)
    for x in range(26, 56, 6): l.punto(x, 72, hexa('fff2b0'))
    # brazos, mangas y manos
    l.cilindro(13, 48, 23, 70, tela, radio=3); l.cilindro(57, 48, 67, 70, tela, radio=3)
    l.placa(13, 66, 23, 70, oro, radio=0); l.placa(57, 66, 67, 70, oro, radio=0)
    l.elipse(18, 73, 4.6, 4.6, piel); l.elipse(62, 73, 4.6, 4.6, piel)
    # bastón con cristal
    l.cilindro(66, 24, 69, 92, hexa('6e4a2a'), radio=1)
    l.elipse(67.5, 17, 5, 9, cristal)
    l.linea(63, 26, 72, 26, oro, 2)
    # hombreras de cristal
    for cx in (22, 58):
        l.elipse(cx, 45, 8, 6.5, cristal); l.elipse(cx, 44, 4.5, 3.5, mez(cristal, (255, 255, 255), 0.5), ruido=0.0)
    # gema pectoral con engarce
    l.placa(34, 50, 46, 66, oro, radio=3); l.gema(40, 58, 4, 6.5, cristal)
    # capucha y rostro en sombra
    l.elipse(40, 27, 20, 23, tela)
    l.elipse(40, 31, 12.5, 14, hexa('0c0820'), ruido=0.0)
    l.placa(26, 38, 54, 45, osc, radio=2)
    # ojos brillantes
    for x in (34, 46):
        l.placa(x - 3, 29, x + 3, 33, cristal, radio=1, ruido=0.0); l.brillo(x - 2, 29, (240, 255, 255))
    l.placa(37, 3, 43, 9, oro, radio=1); l.gema(40, 6, 2.5, 2.5, cristal)
    return l.acabado()


def viajera():
    l = Lienzo(55)
    piel, pelo, chaq, pant, bufanda, cuero = map(hexa, ('ebbb92', 'c84620', '3f7d4c', '4c3b5e', 'f4c52e', '8a5328'))
    # piernas y botas
    l.cilindro(29, 66, 38, 88, pant); l.cilindro(42, 66, 51, 88, pant)
    l.placa(26, 84, 39, 93, hexa('5c3a20'), radio=2); l.placa(41, 84, 54, 93, hexa('5c3a20'), radio=2)
    l.placa(26, 80, 39, 85, hexa('7a4e2c'), radio=1); l.placa(41, 80, 54, 85, hexa('7a4e2c'), radio=1)
    # chaqueta
    l.cilindro(25, 42, 55, 70, chaq, radio=3)
    l.placa(39, 42, 41, 70, mez(chaq, (0, 0, 0), 0.4), radio=0)
    l.placa(25, 62, 55, 66, cuero, radio=1); l.placa(37, 61, 43, 67, hexa('e0b84a'), radio=1)
    l.placa(28, 52, 35, 58, mez(chaq, (0, 0, 0), 0.25), radio=1)
    # brazos y guantes
    l.cilindro(16, 43, 26, 64, chaq, radio=3); l.cilindro(54, 43, 64, 64, chaq, radio=3)
    l.placa(16, 60, 26, 64, cuero, radio=0); l.placa(54, 60, 64, 64, cuero, radio=0)
    l.elipse(21, 68, 5, 5, piel); l.elipse(59, 68, 5, 5, piel)
    # bolso cruzado
    l.linea(28, 42, 52, 66, cuero, 3)
    l.placa(48, 62, 66, 78, cuero, radio=2); l.placa(48, 62, 66, 67, mez(cuero, (0, 0, 0), 0.3), radio=1)
    l.placa(55, 65, 59, 69, hexa('e0b84a'), radio=0)
    # bufanda
    l.cilindro(30, 36, 50, 44, bufanda, radio=2); l.cilindro(46, 40, 53, 58, bufanda, radio=2)
    l.placa(46, 56, 53, 59, mez(bufanda, (150, 60, 0), 0.4), radio=0)
    # cabeza, pelo con rodete, antiparras
    l.elipse(40, 27, 12.5, 13, piel)
    l.elipse(40, 17, 15, 11, pelo, ruido=0.2)
    l.cilindro(24, 18, 29, 36, pelo, ruido=0.2, radio=2); l.cilindro(51, 18, 56, 36, pelo, ruido=0.2, radio=2)
    l.elipse(40, 5, 7, 5.5, pelo, ruido=0.2)
    l.placa(26, 15, 54, 19, hexa('8b929c'), radio=1)
    for x in (33, 47):
        l.elipse(x, 17, 5, 4.2, hexa('3a4250'), ruido=0.0); l.elipse(x, 17, 3.6, 3, hexa('47e8ff'), ruido=0.0, luz_extra=0.4)
        l.brillo(x - 2, 16)
    l.ojo(34, 27, 2.6, 3, None, (40, 24, 18)); l.ojo(46, 27, 2.6, 3, None, (40, 24, 18))
    l.placa(37, 33, 43, 34, hexa('b4604a'), radio=0)
    l.punto(38, 30, mez(piel, (0, 0, 0), 0.25)); l.punto(42, 30, mez(piel, (0, 0, 0), 0.25))
    return l.acabado()


# ---------------------------------------------------------------- huellas
def _ruido_suave(rnd, w, h, celda):
    gw, gh = w // celda + 3, h // celda + 3
    g = [[rnd.uniform(-1, 1) for _ in range(gw)] for _ in range(gh)]
    def f(x, y):
        gx, gy = x / celda, y / celda
        i, j = int(gx), int(gy)
        tx, ty = gx - i, gy - j
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = g[j][i] * (1 - tx) + g[j][i + 1] * tx
        b = g[j + 1][i] * (1 - tx) + g[j + 1][i + 1] * tx
        return a * (1 - ty) + b * ty
    return f


def huella(semilla):
    """Huella con crestas finas, remolino desplazado y bordes irregulares, como las del juego original."""
    rnd = random.Random(semilla)
    w, h = 84, 110
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    r1, r2 = _ruido_suave(rnd, w, h, 22), _ruido_suave(rnd, w, h, 9)
    cx, cy = w / 2 + rnd.uniform(-7, 7), h * 0.46 + rnd.uniform(-8, 8)
    periodo = rnd.uniform(3.9, 4.6)
    estiramiento = rnd.uniform(1.05, 1.35)
    giro = rnd.uniform(-0.5, 0.5)
    for y in range(h):
        for x in range(w):
            ex, ey = (x - w / 2) / (w / 2 - 1.5), (y - h / 2) / (h / 2 - 1.5)
            borde = 1 + 0.07 * r2(x, y)
            if ex * ex + ey * ey > borde * borde:
                continue
            dx, dy = x - cx, (y - cy) * estiramiento
            r = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            fase = r / periodo + 1.7 * r1(x, y) + 0.5 * r2(x, y) + giro * ang / 6.28 * (r / 14) + 0.35 * math.sin(ang * 3) * min(1, r / 18)
            v = math.cos(fase * 6.28)
            if v > 0.12 and rnd.random() > 0.025:
                t = rnd.randint(-10, 10)
                im.putpixel((x, y), (96 + t, 42 + t // 2, 40 + t // 2, 255))
    return im


PERSONAJES = {
    'minero': (minero, 1),
    'robot_mensajero': (robot, 2),
    'alien_tres_ojos': (alien3, 3),
    'guardian_cristal': (guardian, 4),
    'viajera_naranja': (viajera, 5),
}
# Recorte del busto para el carnet: 34 columnas x 43 filas, que luego se ajusta a 170 px de alto.
CAJA_CARNET = (23, 0, 57, 43)


def a_altura(im, alto):
    ancho = max(1, round(im.width * alto / im.height))
    return im.resize((ancho, alto), Image.NEAREST)


def generar(hoja=False):
    DESTINO.mkdir(parents=True, exist_ok=True)
    imagenes = []
    for nombre, (fn, semilla) in PERSONAJES.items():
        l = fn()
        cuerpo = l.imagen().resize((W * ESC, H * ESC), Image.NEAREST)
        carnet = a_altura(l.imagen(CAJA_CARNET), 170)
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
