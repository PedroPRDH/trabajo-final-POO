#!/usr/bin/env python3
"""Convierte sprites PNG nuevos al formato que usa la versión web y los copia a docs/img/.

Uso:  python3 tools/importar_sprites.py carpeta_con_pngs

Nombres esperados en la carpeta (el "id" es el nombre del personaje en minúsculas, sin espacios):
  ing_<id>.png           cuerpo del ingresante en la ventanilla   -> alto 380 px
  foto_carnet_<id>.png   foto del carnet (DNI y pasaporte)         -> alto 170 px
  hue_<id>.png           huella dactilar                           -> alto 110 px
Todos con fondo transparente. El ancho se calcula solo para no deformar la imagen.
Después se agrega una línea en PERFILES (docs/index.html), ver README.
"""
import sys, pathlib
from PIL import Image

ALTOS = {'ing_': 380, 'foto_carnet_': 170, 'hue_': 110}
DESTINO = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'img'

def main(carpeta):
    hechos = 0
    for png in sorted(pathlib.Path(carpeta).glob('*.png')):
        alto = next((h for pref, h in ALTOS.items() if png.name.startswith(pref)), None)
        if alto is None:
            print('ignorado (nombre no reconocido):', png.name); continue
        im = Image.open(png).convert('RGBA')
        ancho = max(1, round(im.width * alto / im.height))
        im = im.resize((ancho, alto), Image.NEAREST)  # NEAREST conserva el pixel art
        salida = DESTINO / (png.stem + '.webp')
        im.save(salida, 'WEBP', quality=90, method=6)
        print(f'{png.name} -> {salida.name} ({ancho}x{alto})'); hechos += 1
    print(f'{hechos} archivo(s) convertido(s).')

if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
