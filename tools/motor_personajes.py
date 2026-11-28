#!/usr/bin/env python3
"""Motor de personajes procedurales de Frontier (versión web).

Qué hace distinto a la primera versión (crear_personajes.py):
  * Cada pieza es una forma 2D que se "infla" a volumen con una transformada de distancia, de modo que
    cualquier polígono recibe normales y luz (esfera, cilindro, placa biselada) sin dibujar tonos a mano.
  * Iluminación real (difusa + brillo especular + sombras de contacto entre piezas) desde arriba a la
    izquierda, cuantizada en pocos tonos con umbral ruidoso: así se ve el "pixel art" pintado, no un degradé.
  * Materiales con relieve y color propios: tela con pliegues, metal cepillado con remaches, cuero, piel, pelo.
  * Luz propia (emisión) cian con resplandor, que es la firma visual del juego original.
  * Contorno casi negro de 1 píxel lógico + línea interna donde una pieza se apoya sobre otra.
  * Acabado: se amplía x3, se suaviza un poco y se agrega grano, como las imágenes originales (que no son
    pixel art puro: tienen ~5 px por píxel lógico y decenas de miles de colores).
  * Un generador por semilla (`personaje_aleatorio`) combina especie, cabeza, atuendo, accesorio y paleta.

Uso:  python3 tools/motor_personajes.py              # escribe los WebP de los personajes en docs/img/
      python3 tools/motor_personajes.py --hoja       # además guarda una hoja de muestra en /tmp
      python3 tools/motor_personajes.py --azar 8     # hoja con 8 personajes aleatorios (no escribe en docs/)
"""
import math, sys, pathlib
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFilter

W, H, ESC = 104, 127, 3
DESTINO = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'img'
LUZ = np.array([-0.52, -0.66, 0.54]); LUZ = LUZ / np.linalg.norm(LUZ)
MEDIO = LUZ + np.array([0, 0, 1.0]); MEDIO = MEDIO / np.linalg.norm(MEDIO)
CIAN = np.array([94, 226, 255.0])


def hexa(c):
    c = c.lstrip('#')
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], float)

def mez(a, b, t):
    return np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t


class Ruido:
    """Campos de ruido de valor, reproducibles por semilla."""
    def __init__(self, semilla):
        self.rng = np.random.default_rng(semilla)

    def campo(self, celda, h=H, w=W, aniso=(1.0, 1.0)):
        gy, gx = max(2, int(h / (celda * aniso[0])) + 3), max(2, int(w / (celda * aniso[1])) + 3)
        g = self.rng.random((gy, gx))
        z = ndi.zoom(g, (h / (gy - 1) * 1.0, w / (gx - 1) * 1.0), order=3)[:h, :w]
        if z.shape != (h, w):
            z = np.pad(z, ((0, h - z.shape[0]), (0, w - z.shape[1])), mode='edge')
        return (z - z.min()) / max(1e-6, z.max() - z.min())

    def fino(self, h=H, w=W):
        return self.rng.random((h, w))


class Lienzo:
    def __init__(self, semilla=1):
        self.rn = Ruido(semilla)
        self.sem = semilla
        self.alb = np.zeros((H, W, 3)); self.alpha = np.zeros((H, W), bool)
        self.nx = np.zeros((H, W)); self.ny = np.zeros((H, W)); self.nz = np.ones((H, W))
        self.esp = np.zeros((H, W)); self.bri = np.full((H, W), 12.0)
        self.rim = np.zeros((H, W)); self.ao = np.ones((H, W)); self.emi = np.zeros((H, W, 3)); self.pid = np.zeros((H, W), int)
        self.n = 0
        self.ruido_tela = self.rn.campo(5); self.ruido_grano = self.rn.campo(2)
        self.ruido_x = self.rn.campo(14, aniso=(3, 0.5))

    # ------------------------------------------------------------ máscaras
    @staticmethod
    def _m(dibujar):
        im = Image.new('L', (W, H), 0); dibujar(ImageDraw.Draw(im)); return np.array(im) > 127

    def m_poly(self, pts): return self._m(lambda d: d.polygon([(float(x), float(y)) for x, y in pts], fill=255))
    def m_elipse(self, cx, cy, rx, ry): return self._m(lambda d: d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255))
    def m_rect(self, x0, y0, x1, y1, r=0):
        return self._m(lambda d: d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=r, fill=255) if r else d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255))

    def m_capsula(self, x0, y0, x1, y1, r0, r1):
        def f(d):
            n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 2
            for i in range(n + 1):
                t = i / n; x, y, r = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        return self._m(f)

    # ------------------------------------------------------------ materiales
    def _textura(self, mat, mask, color):
        """Devuelve (bump, factor de color, especular, brillo)."""
        yy, xx = np.mgrid[0:H, 0:W].astype(float)
        g, rt = self.ruido_grano, self.ruido_tela
        if mat == 'tela':
            pliegue = np.sin((xx * 0.55 + rt * 5.0 + yy * 0.05) * 1.0)
            return 0.20 * pliegue + 0.06 * (g - .5), 1 + 0.10 * pliegue + 0.10 * (g - .5), 0.04, 6
        if mat == 'cuero':
            return 0.10 * (g - .5) + 0.05 * (rt - .5), 1 + 0.18 * (g - .5), 0.18, 10
        if mat == 'metal':
            cep = self.ruido_x
            rayas = (self.rn.fino() > 0.985) * 0.5
            return 0.10 * (cep - .5) + 0.08 * (g - .5), 1 + 0.30 * (cep - .5) + 0.16 * (g - .5) + rayas * 0.6, 0.85, 26
        if mat == 'piel':
            return 0.03 * (g - .5), 1 + 0.07 * (g - .5), 0.10, 8
        if mat == 'pelo':
            h = np.sin(xx * 2.3 + rt * 9) * np.sin(yy * 0.7 + rt * 6)
            return 0.20 * h, 1 + 0.30 * (g - .5) + 0.12 * h, 0.10, 8
        if mat == 'cristal':
            return 0.12 * (g - .5), 1 + 0.10 * (g - .5), 0.95, 40
        return 0.0 * g, 1.0 + 0.0 * g, 0.05, 6

    # ------------------------------------------------------------ pieza genérica
    def forma(self, mask, color, mat='tela', R=5.0, perfil='redondo', emis=None, bisel=1.6, brillo=1.0, sombra=True, textura=1.0):
        """Infla la máscara a volumen, la ilumina y la apila sobre lo ya dibujado."""
        if not mask.any():
            return mask
        self.n += 1
        color = np.asarray(color, float)
        dist = ndi.distance_transform_edt(mask)
        if perfil == 'redondo':
            h = np.sqrt(np.clip(dist / R, 0, 1))
        else:  # bisel: meseta con borde suave
            h = np.clip(dist / bisel, 0, 1) ** 0.8 * 0.55
        bump, fcol, esp, bri = self._textura(mat, mask, color)
        h = h + bump * textura * 0.25
        h = ndi.gaussian_filter(h, 0.55)
        gy, gx = np.gradient(h)
        k = 2.6 if perfil == 'redondo' else 4.2
        nx, ny = -gx * k * R * 0.33, -gy * k * R * 0.33
        nz = np.ones_like(nx); nrm = np.sqrt(nx * nx + ny * ny + nz * nz)
        # sombra de contacto sobre lo que queda debajo
        if sombra and self.alpha.any():
            sh = np.zeros_like(mask)
            sh[2:, 1:] = mask[:-2, :-1]; sh[3:, 2:] |= mask[:-3, :-2]
            self.ao[sh & ~mask & self.alpha] *= 0.62
        m = mask
        ul = np.zeros_like(mask); ul[1:, 1:] = mask[:-1, :-1]
        self.rim[m] = (mask & ~ul)[m] * 0.30
        self.alb[m] = np.clip(color * fcol[..., None], 0, 255)[m]
        self.nx[m], self.ny[m], self.nz[m] = (nx / nrm)[m], (ny / nrm)[m], (nz / nrm)[m]
        self.esp[m] = esp * brillo; self.bri[m] = bri
        self.ao[m] = 1.0
        self.emi[m] = 0
        if emis is not None:
            self.emi[m] = np.asarray(emis, float)
        self.alpha |= m; self.pid[m] = self.n
        return mask

    # atajos
    def poly(self, pts, color, **kw): return self.forma(self.m_poly(pts), color, **kw)
    def elipse(self, cx, cy, rx, ry, color, **kw): return self.forma(self.m_elipse(cx, cy, rx, ry), color, **kw)
    def rect(self, x0, y0, x1, y1, color, r=0, **kw): return self.forma(self.m_rect(x0, y0, x1, y1, r), color, **kw)
    def capsula(self, x0, y0, x1, y1, r0, r1, color, **kw): return self.forma(self.m_capsula(x0, y0, x1, y1, r0, r1), color, **kw)

    def pintar(self, mask, color, factor=1.0, emis=None):
        """Pinta color sobre lo existente sin cambiar el volumen (franjas, bordados, líneas)."""
        m = mask & self.alpha
        self.alb[m] = np.asarray(color, float)
        if emis is not None:
            self.emi[m] = np.asarray(emis, float)
        return m

    def linea(self, pts, color, grosor=1, emis=None):
        def f(d): d.line([(float(x), float(y)) for x, y in pts], fill=255, width=grosor)
        return self.pintar(self._m(f), color, emis=emis)

    def luz(self, cx, cy, r, color=CIAN):
        """Gema/lente que emite luz."""
        m = self.m_elipse(cx, cy, r, r)
        self.forma(m, mez(color, (0, 0, 0), 0.35), mat='cristal', R=max(1.5, r * 0.9), emis=color * 0.9, sombra=False)

    def ojo(self, cx, cy, rx, ry, iris=None, pupila=(14, 10, 22)):
        self.forma(self.m_elipse(cx, cy, rx, ry), (236, 232, 222) if iris is not None and iris != 'solo' else pupila, mat='liso', R=max(1.5, ry), sombra=False)
        if iris not in (None, 'solo'):
            self.forma(self.m_elipse(cx, cy + 0.3, max(1, rx * .62), max(1, ry * .78)), iris, mat='liso', R=2, sombra=False)
            self.forma(self.m_elipse(cx, cy + 0.3, max(.8, rx * .32), max(.8, ry * .42)), pupila, mat='liso', R=1, sombra=False)
        self.pintar(self.m_rect(int(cx - rx * .45), int(cy - ry * .55), int(cx - rx * .45) + 1, int(cy - ry * .55) + 1), (255, 255, 255))

    # ------------------------------------------------------------ render final
    def render(self):
        n = np.stack([self.nx, self.ny, self.nz], -1)
        dif = np.clip((n * LUZ).sum(-1), 0, 1)
        esp = np.clip((n * MEDIO).sum(-1), 0, 1) ** self.bri * self.esp
        sombra_total = self.ao
        base = 0.30 + 0.80 * dif + self.rim
        v = base * sombra_total
        # cuantización en tonos con umbral ruidoso (pintura de pixel, no degradé)
        K = 5.0
        umbral = (self.rn.fino() - 0.5) * 0.55
        vq = np.clip(np.floor(v * K + 0.5 + umbral) / K, 0.10, 1.12)
        frio = np.array([0.88, 0.82, 1.06])      # las sombras se enfrían
        calido = np.array([1.06, 1.03, 0.94])    # las luces se calientan
        t = np.clip((vq - 0.3) / 0.8, 0, 1)[..., None]
        tinte = frio * (1 - t) + calido * t
        col = self.alb * vq[..., None] * tinte
        eq = np.floor(np.clip(esp * 1.6, 0, 1) * 3 + 0.5 + umbral * 0.5) / 3
        col = col + eq[..., None] * np.array([255, 250, 236.0]) * 0.55
        # luz propia con resplandor
        e = self.emi.copy()
        glow = np.stack([ndi.gaussian_filter(e[..., i], 1.6) for i in range(3)], -1)
        col = col * (1 - np.clip(e.max(-1, keepdims=True) / 255, 0, 1) * 0.9) + e + glow * 0.55
        col = np.clip(col, 0, 255)
        # contornos
        al = self.alpha
        er = ndi.binary_erosion(al, structure=np.ones((3, 3)), border_value=0)
        dil4 = ndi.binary_dilation(al, structure=ndi.generate_binary_structure(2, 1))
        contorno = dil4 & ~al
        near = ndi.maximum_filter(np.where(al[..., None], col, 0), size=(3, 3, 1))
        out = np.zeros((H, W, 4))
        out[..., :3] = np.where(al[..., None], col, 0)
        # línea interna: píxel de una pieza pegado a otra dibujada después
        p = self.pid
        interior = np.zeros_like(al)
        for dy, dx in ((0, 1), (1, 0), (1, 1)):
            a = p[:H - dy, :W - dx]; b = p[dy:, dx:]
            cond = (b > a) & (a > 0)
            interior[:H - dy, :W - dx] |= cond
        interior &= al & ~(self.emi.max(-1) > 0)
        out[interior, :3] *= 0.38
        out[..., 3] = al * 255
        cc = np.where(contorno[..., None], np.clip(near * 0.10 + 6, 0, 60), 0)
        out[contorno, :3] = cc[contorno]
        out[contorno, 3] = 255
        return out

    def imagen(self, caja=None, esc=ESC, grano=3.0):
        out = self.render()
        im = Image.fromarray(out.astype('uint8'), 'RGBA')
        x0, y0, x1, y1 = caja or (0, 0, W, H)
        im = im.crop((x0, y0, x1, y1))
        im = im.resize((im.width * esc, im.height * esc), Image.NEAREST)
        a = np.array(im).astype(float)
        rng = np.random.default_rng(self.sem + 7)
        a[..., :3] += rng.normal(0, grano, a.shape[:2])[..., None] + rng.normal(0, grano * 0.5, a[..., :3].shape)
        rgb = Image.fromarray(np.clip(a[..., :3], 0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.55))
        al = Image.fromarray(a[..., 3].astype('uint8')).filter(ImageFilter.GaussianBlur(0.7))
        al = al.point(lambda v: 0 if v < 70 else min(255, int((v - 70) * 1.9)))
        im = rgb.convert('RGBA'); im.putalpha(al)
        return im


# =========================================================================== piezas reutilizables
CX = 52


def cuerpo_humano(l, piel, ropa_pierna, bota, y_hombro=42, ancho=18):
    """Piernas y botas (devuelve nada; el torso lo pone cada atuendo)."""
    l.capsula(CX - 8, 80, CX - 8.5, 115, 7.5, 6.2, ropa_pierna)
    l.capsula(CX + 8, 80, CX + 8.5, 115, 7.5, 6.2, ropa_pierna)
    for s in (-1, 1):
        x = CX + s * 8.5
        l.poly([(x - 8 + (2 if s > 0 else 0), 112), (x + 8 - (2 if s < 0 else 0), 112), (x + 9.5, 122), (x - 9.5, 122), (x - 9.5, 118)], bota, mat='cuero', R=3.5)
        l.rect(int(x - 10), 121, int(x + 10), 124, mez(bota, (0, 0, 0), 0.55), mat='cuero', perfil='bisel')


def brazo(l, lado, hombro, codo, mano, r0, r1, manga, piel=None, puno=None, r_mano=5.2):
    l.capsula(hombro[0], hombro[1], codo[0], codo[1], r0, (r0 + r1) / 2, manga)
    l.capsula(codo[0], codo[1], mano[0], mano[1], (r0 + r1) / 2, r1, manga)
    if puno is not None:
        l.capsula(mano[0] - (mano[0] - codo[0]) * .22, mano[1] - (mano[1] - codo[1]) * .22, mano[0], mano[1] - 1, r1 + 0.6, r1 + 0.6, puno, mat='cuero')
    if piel is not None:
        l.elipse(mano[0], mano[1] + 3.2, r_mano, r_mano * 1.05, piel, mat='piel', R=4.2)


def cabeza_humana(l, piel, cx=CX, cy=27, rx=11.4, ry=12.6, ojos=(96, 62, 36), sombra_ojos=True, cejas=None, mirada=None):
    l.capsula(cx, cy + 8, cx, cy + 17, 5.2, 5.6, mez(piel, (0, 0, 0), 0.22), mat='piel')
    l.elipse(cx, cy, rx, ry, piel, mat='piel', R=9)
    # orejas
    l.elipse(cx - rx + .4, cy + 1.5, 2.2, 3.2, mez(piel, (0, 0, 0), 0.1), mat='piel', R=2)
    l.elipse(cx + rx - .4, cy + 1.5, 2.2, 3.2, mez(piel, (0, 0, 0), 0.1), mat='piel', R=2)
    # nariz, mejillas, ojos con esclerótica, cejas y boca
    sombra_n = mez(piel, (40, 10, 10), .38)
    l.elipse(cx + .3, cy + 4.2, 2.6, 3.0, mez(piel, (255, 225, 195), .12), mat='piel', R=2.4, sombra=False)
    l.pintar(l.m_rect(int(cx - 2), int(cy + 6.6), int(cx + 3), int(cy + 7.6)), sombra_n)
    for s in (-1, 1):
        l.pintar(l.m_elipse(cx + s * 7.4, cy + 5.6, 2.8, 1.6), mez(piel, (210, 80, 70), .25))
        ex = cx + s * 5.2
        l.pintar(l.m_rect(int(ex - 3.4), int(cy - 2.6), int(ex + 3.4), int(cy - 1.2)), mez(piel, (30, 10, 10), .45))
        l.ojo(ex, cy + .6, 3.2, 2.5, ojos, (18, 12, 14))
        c_ceja = mez(piel, (25, 12, 8), .78) if cejas is None else cejas
        l.linea([(ex - 3.6, cy - 3.6 + (0.6 if s < 0 else 0)), (ex + 3.6, cy - 3.6 + (0.6 if s > 0 else 0))], c_ceja, 2)
    l.linea([(cx - 3, cy + 9.6), (cx + 3, cy + 9.6)], mez(piel, (110, 30, 30), .62), 1)
    l.linea([(cx - 2, cy + 10.7), (cx + 2, cy + 10.7)], mez(piel, (255, 150, 140), .15), 1)


# =========================================================================== personajes preseteados
def alien_tres_ojos():
    l = Lienzo(31)
    piel, morado, oro, gema = hexa('3fb89a'), hexa('6c3fb0'), hexa('f0c64a'), hexa('5ee2ff')
    # piernas largas y finas con pies anchos
    for s in (-1, 1):
        x = CX + s * 7.5
        l.capsula(x, 82, x + s * .5, 114, 4.4, 3.4, mez(piel, (0, 0, 0), .08))
        l.elipse(x + s * 1.5, 120, 8.5, 4.4, mez(piel, (0, 0, 0), .15), R=4)
    # brazos largos (detrás del torso)
    for s in (-1, 1):
        l.capsula(CX + s * 17, 46, CX + s * 23, 66, 4.2, 3.6, piel)
        l.capsula(CX + s * 23, 66, CX + s * 25, 91, 3.6, 3.0, piel)
        l.elipse(CX + s * 25.5, 96, 5, 5.5, mez(piel, (0, 0, 0), .05), R=4)
        for d in (-3, 0, 3):
            l.capsula(CX + s * 25.5 + d, 98, CX + s * 25.5 + d * 1.5, 105, 1.5, 1.2, mez(piel, (0, 0, 0), .1))
    # torso morado con bandas doradas
    l.poly([(CX - 17, 44), (CX + 17, 44), (CX + 14, 84), (CX - 14, 84)], morado, R=11)
    for yb in (47, 66, 82):
        l.rect(CX - 17 + (yb - 44) // 7, yb, CX + 17 - (yb - 44) // 7, yb + 4, oro, mat='metal', perfil='bisel')
    l.linea([(CX - 10, 52), (CX, 62), (CX + 10, 52)], mez(morado, (255, 255, 255), .25), 1)
    l.linea([(CX - 10, 76), (CX, 66), (CX + 10, 76)], mez(morado, (255, 255, 255), .25), 1)
    l.luz(CX, 65, 4.2, gema)
    # cuello y cabeza alargada con cresta
    l.capsula(CX, 36, CX, 46, 4.2, 5, mez(piel, (0, 0, 0), .2))
    for i, dx in enumerate((-9, -4.5, 0, 4.5, 9)):
        l.poly([(CX + dx - 2.5, 14), (CX + dx + 2.5, 14), (CX + dx * 1.15, 3 + abs(dx) * .35)], mez(piel, (0, 0, 0), .1 + .05 * i % 3), R=2.5)
    l.elipse(CX, 24, 15.5, 17, piel, mat='piel', R=12)
    l.pintar(l.m_elipse(CX - 4, 14, 8, 4), mez(piel, (255, 255, 255), .18))
    for (ex, ey, er) in ((CX - 9, 24, 4.6), (CX + 9, 24, 4.6), (CX, 14.5, 4.2)):
        l.forma(l.m_elipse(ex, ey, er + 1.5, er + 1.5), oro, mat='metal', R=er + 1, perfil='bisel', sombra=False)
        l.ojo(ex, ey, er, er, 'solo', (18, 12, 24))
    l.pintar(l.m_rect(CX - 4, 33, CX + 4, 34), mez(piel, (20, 60, 50), .6))
    l.pintar(l.m_elipse(CX, 29, 1, 1.5), mez(piel, (10, 50, 40), .5))
    return l


def guardian_cristal():
    l = Lienzo(32)
    tela, borde, oro, cristal = hexa('4a2a8a'), hexa('2e1a5c'), hexa('e6b84a'), hexa('5ee2ff')
    # bastón con orbe (detrás)
    l.capsula(CX + 31, 40, CX + 31.5, 120, 1.9, 1.9, hexa('6b4a2e'), mat='cuero')
    l.poly([(CX + 31, 18), (CX + 36, 28), (CX + 31, 40), (CX + 26, 28)], mez(cristal, (0, 0, 0), .25), mat='cristal', R=5, emis=cristal * .75)
    # túnica: silueta cónica con pliegues
    l.poly([(CX - 20, 46), (CX + 20, 46), (CX + 27, 122), (CX - 27, 122)], tela, R=14)
    l.poly([(CX - 3, 48), (CX + 3, 48), (CX + 6, 122), (CX - 6, 122)], borde, R=4)
    l.rect(CX - 27, 116, CX + 27, 124, oro, mat='metal', perfil='bisel')
    l.rect(CX - 20, 78, CX + 20, 83, oro, mat='metal', perfil='bisel')
    # mangas y manos
    for s in (-1, 1):
        l.capsula(CX + s * 21, 47, CX + s * 27, 76, 7.5, 5.5, tela)
        l.rect(CX + s * 27 - 6, 73, CX + s * 27 + 6, 78, oro, mat='metal', perfil='bisel')
        l.elipse(CX + s * 28, 83, 4.6, 4.8, hexa('c98e5e'), mat='piel', R=4)
    l.capsula(CX + 31, 78, CX + 31, 90, 2.6, 2.6, hexa('b07848'), mat='piel')
    # hombreras de cristal
    for s in (-1, 1):
        l.poly([(CX + s * 12, 44), (CX + s * 27, 48), (CX + s * 29, 58), (CX + s * 17, 55)], mez(cristal, (20, 40, 80), .3), mat='cristal', R=6, emis=cristal * .30)
    # capucha
    l.poly([(CX - 21, 50), (CX - 17, 20), (CX - 8, 4), (CX + 8, 4), (CX + 17, 20), (CX + 21, 50), (CX + 10, 43), (CX - 10, 43)], tela, R=10)
    l.elipse(CX, 27, 12.5, 15, hexa('0d0818'), R=8, sombra=False)
    l.elipse(CX - 5, 29, 3.2, 1.9, cristal, mat='cristal', R=1.5, emis=cristal, sombra=False)
    l.elipse(CX + 5, 29, 3.2, 1.9, cristal, mat='cristal', R=1.5, emis=cristal, sombra=False)
    l.rect(CX - 17, 41, CX + 17, 45, oro, mat='metal', perfil='bisel')
    l.luz(CX, 43, 3.6, cristal)
    # broche de cristal en el pecho
    l.poly([(CX, 56), (CX + 6, 66), (CX, 78), (CX - 6, 66)], oro, mat='metal', R=5)
    l.poly([(CX, 59), (CX + 4, 66), (CX, 75), (CX - 4, 66)], mez(cristal, (0, 0, 0), .2), mat='cristal', R=4, emis=cristal * .9, sombra=False)
    return l


def minero():
    l = Lienzo(33)
    piel, casco, chaleco, mono, cuero, metal = map(hexa, ('c98e5e', 'f4c52e', 'ec7a1c', '35507e', '6a4128', 'a7b0bd'))
    # pico (detrás)
    l.capsula(CX + 33, 38, CX + 33.5, 112, 2.0, 2.0, hexa('7a5232'), mat='cuero')
    l.poly([(CX + 20, 36), (CX + 46, 36), (CX + 50, 42), (CX + 42, 39), (CX + 33, 38), (CX + 24, 39), (CX + 16, 42)], metal, mat='metal', R=3)
    cuerpo_humano(l, piel, mono, hexa('5a3a24'))
    l.poly([(CX - 18, 44), (CX + 18, 44), (CX + 16, 84), (CX - 16, 84)], mono, R=12)
    l.poly([(CX - 15, 45), (CX + 15, 45), (CX + 13, 82), (CX - 13, 82)], chaleco, R=9)
    l.rect(CX - 14, 56, CX + 14, 60, hexa('e8e8d0'), mat='metal', perfil='bisel')
    l.rect(CX - 14, 68, CX + 14, 72, hexa('e8e8d0'), mat='metal', perfil='bisel')
    l.rect(CX - 1, 45, CX + 1, 82, mez(chaleco, (0, 0, 0), .45), perfil='bisel')
    l.rect(CX - 17, 79, CX + 17, 86, cuero, mat='cuero', perfil='bisel')
    l.rect(CX - 4, 79, CX + 4, 86, hexa('d9b44a'), mat='metal', perfil='bisel')
    l.rect(CX - 13, 62, CX - 5, 68, mez(chaleco, (0, 0, 0), .25), mat='tela', perfil='bisel')
    for s in (-1, 1):
        brazo(l, s, (CX + s * 18, 47), (CX + s * 22, 64), (CX + s * 22, 80), 6.4, 5.3, mono, piel=piel, puno=cuero)
        l.rect(CX + s * 22 - 6, 66, CX + s * 22 + 6, 70, hexa('e8e8d0'), mat='metal', perfil='bisel')
    cabeza_humana(l, piel, ojos=(70, 44, 24))
    l.elipse(CX, 38.5, 10.5, 6.5, hexa('5a3a24'), mat='pelo', R=5)
    l.elipse(CX, 33.2, 7.5, 2.2, hexa('6a4228'), mat='pelo', R=2, sombra=False)
    l.pintar(l.m_rect(CX - 3, 36, CX + 3, 37), hexa('3a1c10'))
    # casco con lámpara
    l.poly([(CX - 17, 21), (CX - 15, 11), (CX - 7, 4), (CX + 7, 4), (CX + 15, 11), (CX + 17, 21), (CX + 21, 22), (CX + 21, 25), (CX - 21, 25), (CX - 21, 22)], casco, mat='metal', R=9, brillo=.6)
    l.rect(CX - 21, 22, CX + 21, 26, mez(casco, (80, 40, 0), .35), mat='metal', perfil='bisel')
    l.rect(CX - 5, 6, CX + 5, 15, hexa('d4d9e0'), mat='metal', perfil='bisel')
    l.luz(CX, 10.5, 3.2, hexa('fff7b0'))
    return l


def robot_mensajero():
    l = Lienzo(34)
    chapa, oscuro, naranja = hexa('9aa3b2'), hexa('5b6474'), hexa('e8731c')
    for s in (-1, 1):  # piernas y pies
        x = CX + s * 11
        l.capsula(x, 82, x, 110, 5.2, 4.6, oscuro, mat='metal')
        l.rect(int(x - 9), 109, int(x + 9), 123, chapa, r=3, mat='metal', perfil='bisel')
        l.rect(int(x - 9), 118, int(x + 9), 124, oscuro, mat='metal', perfil='bisel')
    # brazos
    for s in (-1, 1):
        l.rect(CX + s * 26 - 6, 47, CX + s * 26 + 6, 52, chapa, r=2, mat='metal', perfil='bisel')
        l.capsula(CX + s * 26, 52, CX + s * 27, 76, 5.2, 4.6, oscuro, mat='metal')
        l.rect(CX + s * 27 - 7, 72, CX + s * 27 + 7, 90, chapa, r=3, mat='metal', perfil='bisel')
        l.rect(CX + s * 27 - 7, 76, CX + s * 27 + 7, 79, mez(CIAN, (0, 40, 80), .25), perfil='bisel', emis=CIAN * .55)
        for d in (-5, 0, 5):
            l.capsula(CX + s * 27 + d, 90, CX + s * 27 + d, 97, 2.2, 1.8, oscuro, mat='metal')
    # torso
    l.rect(CX - 21, 44, CX + 21, 84, chapa, r=5, mat='metal', perfil='bisel', bisel=2.4)
    l.rect(CX - 15, 52, CX + 15, 70, hexa('0c1722'), r=3, perfil='bisel')
    for i, xx in enumerate((CX - 9, CX - 1, CX + 7)):
        l.pintar(l.m_rect(xx, 57, xx + 5, 65), CIAN * (.9 - .1 * i), emis=CIAN * (.8 - .1 * i))
    l.pintar(l.m_poly([(CX + 9, 57), (CX + 13, 61), (CX + 9, 65)]), (200, 250, 255), emis=CIAN)
    for xx in (CX - 17, CX + 17):
        for yy in (47, 80):
            l.pintar(l.m_elipse(xx, yy, 1.2, 1.2), (60, 66, 78))
    l.rect(CX - 19, 76, CX + 19, 82, oscuro, mat='metal', perfil='bisel')
    # cabeza y visor
    l.rect(CX - 5, 36, CX + 5, 44, oscuro, mat='metal', perfil='bisel')
    l.rect(CX - 19, 12, CX + 19, 38, chapa, r=5, mat='metal', perfil='bisel', bisel=2.4)
    for s in (-1, 1):
        l.rect(CX + s * 20 - 3, 20, CX + s * 20 + 3, 31, oscuro, r=2, mat='metal', perfil='bisel')
    l.rect(CX - 15, 17, CX + 15, 30, hexa('0b1620'), r=3, perfil='bisel')
    for s in (-1, 1):
        l.forma(l.m_rect(CX + s * 7 - 4, 20, CX + s * 7 + 4, 26, 2), CIAN, perfil='bisel', emis=CIAN * .95, sombra=False)
    l.pintar(l.m_rect(CX - 6, 28, CX + 6, 29), CIAN * .6, emis=CIAN * .4)
    l.capsula(CX, 6, CX, 12, 1.2, 1.2, oscuro, mat='metal')
    l.luz(CX, 5, 2.8, hexa('ff9a3c'))
    # bandolera y bolso
    l.poly([(CX - 21, 44), (CX - 14, 44), (CX + 22, 88), (CX + 15, 88)], hexa('6a3f22'), mat='cuero', perfil='bisel')
    l.rect(CX + 12, 84, CX + 33, 106, naranja, r=2, mat='cuero', R=3)
    l.rect(CX + 12, 84, CX + 33, 91, mez(naranja, (0, 0, 0), .35), mat='cuero', perfil='bisel')
    l.rect(CX + 17, 95, CX + 28, 99, hexa('f2e6c8'), perfil='bisel')
    return l


def viajera_naranja():
    l = Lienzo(35)
    piel, gorro, chaqueta, bufanda, cuero, pantalon = map(hexa, ('d8a07a', 'd2552b', '5f9a5a', 'f2c94c', '7a4a28', '5b4f68'))
    cuerpo_humano(l, piel, pantalon, hexa('4a2e1c'))
    for s in (-1, 1):
        brazo(l, s, (CX + s * 17, 47), (CX + s * 21, 64), (CX + s * 20, 80), 6.2, 5.2, chaqueta, piel=piel, puno=mez(chaqueta, (0, 0, 0), .25))
    l.poly([(CX - 17, 44), (CX + 17, 44), (CX + 16, 84), (CX - 16, 84)], chaqueta, R=11)
    l.rect(CX - 17, 80, CX + 17, 86, cuero, mat='cuero', perfil='bisel')
    l.rect(CX - 3, 80, CX + 3, 86, hexa('d9b44a'), mat='metal', perfil='bisel')
    l.rect(CX - 14, 62, CX - 6, 69, mez(chaqueta, (0, 0, 0), .25), mat='tela', perfil='bisel')
    l.rect(CX - 1, 46, CX + 1, 80, mez(chaqueta, (0, 0, 0), .4), perfil='bisel')
    l.capsula(CX - 6, 46.5, CX + 6, 46.5, 4.2, 4.2, bufanda, mat='tela')
    l.capsula(CX + 4, 49, CX + 6, 60, 3.2, 3.0, bufanda, mat='tela')
    cabeza_humana(l, piel, ojos=(60, 120, 90), cejas=mez(piel, (60, 30, 20), .7))
        # gorro de aviadora con orejeras y googles
    l.poly([(CX - 15, 26), (CX - 14, 11), (CX - 6, 2), (CX + 6, 2), (CX + 14, 11), (CX + 15, 26), (CX + 12, 19), (CX, 17), (CX - 12, 19)], gorro, mat='tela', R=8)
    l.elipse(CX, 6, 5, 4, mez(gorro, (255, 200, 150), .2), mat='tela', R=4)
    for s in (-1, 1):
        l.poly([(CX + s * 12.5, 19), (CX + s * 16.5, 24), (CX + s * 17, 38), (CX + s * 13, 38), (CX + s * 12, 24)], gorro, mat='tela', R=3)
    l.rect(CX - 14, 15, CX + 14, 19, hexa('4a2e1c'), mat='cuero', perfil='bisel')
    for s in (-1, 1):
        l.forma(l.m_elipse(CX + s * 6.5, 14.5, 5, 4), hexa('b0b8c4'), mat='metal', R=3.5, perfil='bisel')
        l.forma(l.m_elipse(CX + s * 6.5, 14.5, 3.6, 2.8), hexa('5ee2ff'), mat='cristal', R=2.5, emis=CIAN * .35, sombra=False)
    # bolso cruzado
    l.poly([(CX - 15, 44), (CX - 9, 44), (CX + 17, 90), (CX + 11, 90)], cuero, mat='cuero', perfil='bisel')
    l.rect(CX + 7, 82, CX + 28, 103, hexa('8a5a32'), r=2, mat='cuero', R=3)
    l.rect(CX + 7, 82, CX + 28, 90, mez(hexa('8a5a32'), (0, 0, 0), .3), mat='cuero', perfil='bisel')
    l.rect(CX + 15, 88, CX + 20, 93, hexa('d9b44a'), mat='metal', perfil='bisel')
    return l


PERSONAJES = {
    'minero': minero,
    'robot_mensajero': robot_mensajero,
    'alien_tres_ojos': alien_tres_ojos,
    'guardian_cristal': guardian_cristal,
    'viajera_naranja': viajera_naranja,
}


# =========================================================================== generador por semilla
def personaje_aleatorio(semilla):
    """Combina especie, atuendo, cabeza, accesorio y paleta de forma reproducible."""
    import random
    r = random.Random(semilla)
    l = Lienzo(semilla)
    pieles = ['c98e5e', 'd8a07a', 'a8764a', 'e8bd9a', '7d5535', '3fb89a', '8fb6d8', 'b86fa0']
    ropas = ['35507e', '5f9a5a', '6c3fb0', '8a2f2f', '2f6b6b', '6b5a3a', '444b5a']
    piel, ropa = hexa(r.choice(pieles)), hexa(r.choice(ropas))
    oro, cuero = hexa(r.choice(['e6b84a', 'd9b44a', 'c9783b'])), hexa(r.choice(['6a4128', '7a4a28', '5a3a24']))
    cuerpo_humano(l, piel, mez(ropa, (0, 0, 0), .25), hexa('4a2e1c'))
    ancho = r.choice([15, 17, 19])
    for s in (-1, 1):
        brazo(l, s, (CX + s * (ancho + 1), 47), (CX + s * (ancho + 4), 64), (CX + s * (ancho + 3), 80), 6.3, 5.2, ropa, piel=piel, puno=cuero)
    if r.random() < 0.5:   # armadura
        l.poly([(CX - ancho, 44), (CX + ancho, 44), (CX + ancho - 2, 84), (CX - ancho + 2, 84)], hexa('8a929e'), mat='metal', R=10, brillo=1)
        l.luz(CX, 62, 4, CIAN)
        for s in (-1, 1):
            l.elipse(CX + s * (ancho + 2), 48, 8, 6, hexa('9aa3b0'), mat='metal', R=5)
    else:                   # túnica / chaqueta
        l.poly([(CX - ancho, 44), (CX + ancho, 44), (CX + ancho + 2, 96), (CX - ancho - 2, 96)], ropa, R=11)
        l.rect(CX - ancho - 2, 78, CX + ancho + 2, 84, cuero, mat='cuero', perfil='bisel')
        l.rect(CX - 3, 78, CX + 3, 84, oro, mat='metal', perfil='bisel')
    cabeza_humana(l, piel, ojos=r.choice([(96, 62, 36), (60, 120, 90), (70, 110, 170)]))
    forma = r.choice(['capucha', 'gorro', 'casco', 'pelo'])
    if forma == 'capucha':
        c = hexa(r.choice(['6b5a3a', '4a2a8a', '2f4a6b']))
        l.poly([(CX - 18, 46), (CX - 16, 20), (CX - 8, 6), (CX + 8, 6), (CX + 16, 20), (CX + 18, 46), (CX + 9, 36), (CX - 9, 36)], c, R=9)
        l.elipse(CX, 28, 10.5, 13, hexa('0d0818'), R=8, sombra=False)
        l.elipse(CX - 4.5, 29, 2.4, 1.5, CIAN, mat='cristal', R=1.2, emis=CIAN, sombra=False); l.elipse(CX + 4.5, 29, 2.4, 1.5, CIAN, mat='cristal', R=1.2, emis=CIAN, sombra=False)
    elif forma == 'gorro':
        c = hexa(r.choice(['d2552b', '2f6b6b', '8a2f2f']))
        l.poly([(CX - 14, 22), (CX - 13, 10), (CX, 4), (CX + 13, 10), (CX + 14, 22), (CX + 11, 16), (CX - 11, 16)], c, R=7)
    elif forma == 'casco':
        l.poly([(CX - 14, 24), (CX - 12, 10), (CX, 5), (CX + 12, 10), (CX + 14, 24), (CX + 11, 17), (CX - 11, 17)], hexa('8a929e'), mat='metal', R=7)
        l.luz(CX, 14, 2.4)
    else:
        c = hexa(r.choice(['3a2418', '7a5232', 'b8864a', 'd8d0c0']))
        l.poly([(CX - 13, 24), (CX - 12, 10), (CX, 4), (CX + 12, 10), (CX + 13, 24), (CX + 10, 15), (CX - 10, 15)], c, mat='pelo', R=6)
    acc = r.choice(['baston', 'bolso', 'nada'])
    if acc == 'bolso':
        l.poly([(CX - 15, 44), (CX - 9, 44), (CX + 17, 90), (CX + 11, 90)], cuero, mat='cuero', perfil='bisel')
        l.rect(CX + 7, 82, CX + 28, 103, mez(cuero, (255, 255, 255), .12), r=2, mat='cuero', R=3)
    elif acc == 'baston':
        l.capsula(CX + 31, 36, CX + 31.5, 118, 1.9, 1.9, hexa('7a5232'), mat='cuero')
        l.luz(CX + 31, 32, 4.4, CIAN)
    return l


# =========================================================================== exportación
CAJA_CARNET = (CX - 19, 0, CX + 19, 46)


def a_altura(im, alto):
    ancho = max(1, round(im.width * alto / im.height))
    return im.resize((ancho, alto), Image.LANCZOS)


def generar(hoja=False, escribir=True):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from crear_personajes import huella
    DESTINO.mkdir(parents=True, exist_ok=True)
    out = []
    for i, (nombre, fn) in enumerate(PERSONAJES.items(), 1):
        l = fn()
        cuerpo = a_altura(l.imagen(), 380)
        carnet = a_altura(l.imagen(CAJA_CARNET), 170)
        if escribir:
            cuerpo.save(DESTINO / f'ing_{nombre}.webp', 'WEBP', quality=92, method=6)
            carnet.save(DESTINO / f'foto_carnet_{nombre}.webp', 'WEBP', quality=92, method=6)
            huella(i * 101).save(DESTINO / f'hue_huella_{nombre}.webp', 'WEBP', quality=92, method=6)
        out.append((nombre, cuerpo, carnet)); print('listo:', nombre)
    if hoja:
        guardar_hoja([c for _, c, _ in out], [f for _, _, f in out], '/tmp/claude-0/hoja_nueva.png')


def guardar_hoja(cuerpos, carnets, ruta):
    ancho = sum(c.width + 16 for c in cuerpos) + 16
    sh = Image.new('RGBA', (ancho, 380 + 190), (60, 45, 38, 255)); x = 8
    for c, f in zip(cuerpos, carnets):
        sh.alpha_composite(c, (x, 4)); sh.alpha_composite(f, (x, 390)); x += c.width + 16
    sh.convert('RGB').save(ruta); print('hoja en', ruta)


if __name__ == '__main__':
    if '--azar' in sys.argv:
        n = int(sys.argv[sys.argv.index('--azar') + 1])
        ls = [personaje_aleatorio(100 + i) for i in range(n)]
        guardar_hoja([a_altura(l.imagen(), 380) for l in ls], [a_altura(l.imagen(CAJA_CARNET), 170) for l in ls], '/tmp/claude-0/hoja_azar.png')
    else:
        generar('--hoja' in sys.argv, escribir='--probar' not in sys.argv)
